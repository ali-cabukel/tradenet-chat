"""Read-only Neo4j helpers."""

from __future__ import annotations

import re
from typing import Any

from neo4j import AsyncGraphDatabase
from neo4j.graph import Node, Path, Relationship
from neo4j.time import Date, DateTime, Duration, Time

from tradenet_chat.settings import get_settings

WRITE_PATTERN = re.compile(
    r"\b(?:CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|LOAD\s+CSV|FOREACH|ALTER)\b",
    re.IGNORECASE,
)

DEFAULT_GRAPH_SCHEMA = """\
Tradenet trade graph (Country / Category / TRADES_WITH)

Node labels:
- Country {iso3: STRING, name: STRING}
- Category {id: STRING, name: STRING}

Relationships:
- (exporter:Country)-[r:TRADES_WITH]->(importer:Country)
  r.year: INTEGER
  r.supplyCategory: STRING  // energy, food, metals, chemicals, textiles,
                            // machinery, transport, wood, minerals, all
  r.tradeValueUsd: FLOAT
  r.netWeightKg: FLOAT
  r.flowCount: INTEGER

Edges point from exporter to importer. Category nodes exist in the graph
but TRADES_WITH uses supplyCategory as a relationship property.

Example:
  MATCH (a:Country {iso3: "DEU"})-[r:TRADES_WITH {supplyCategory: "energy"}]->(b:Country)
  RETURN a.name, b.name, r.tradeValueUsd, r.year
  ORDER BY r.tradeValueUsd DESC
  LIMIT 20
"""


class CypherWriteRejected(ValueError):
    """Raised when a Cypher statement contains write clauses."""


def assert_read_only(cypher: str) -> None:
    """Reject Cypher that would mutate the graph."""
    if WRITE_PATTERN.search(cypher or ""):
        raise CypherWriteRejected(
            "Write Cypher is not allowed. Use MATCH / RETURN / WITH / CALL "
            "(read procedures) only; CREATE, MERGE, DELETE, DETACH, SET, "
            "REMOVE, DROP, LOAD CSV, FOREACH, and ALTER are rejected."
        )


def _serialize(value: Any) -> Any:
    """Convert Neo4j driver values into JSON-friendly Python types."""
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_serialize(item) for item in value]
    if isinstance(value, Node):
        return {
            "element_id": value.element_id,
            "labels": list(value.labels),
            "properties": _serialize(dict(value)),
        }
    if isinstance(value, Relationship):
        return {
            "element_id": value.element_id,
            "type": value.type,
            "start": value.start_node.element_id if value.start_node is not None else None,
            "end": value.end_node.element_id if value.end_node is not None else None,
            "properties": _serialize(dict(value)),
        }
    if isinstance(value, Path):
        return {
            "nodes": [_serialize(node) for node in value.nodes],
            "relationships": [_serialize(rel) for rel in value.relationships],
        }
    if isinstance(value, DateTime | Date | Time | Duration):
        return value.iso_format()
    return str(value)


async def run_read_cypher(
    cypher: str,
    parameters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Execute a read-only Cypher query and return serialized records."""
    assert_read_only(cypher)
    settings = get_settings()
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
    )
    try:
        async with driver.session(database=settings.neo4j_database) as session:
            result = await session.run(cypher, parameters or {})
            rows = [record.data() async for record in result]
            return [_serialize(row) for row in rows]
    finally:
        await driver.close()


async def fetch_live_schema() -> str:
    """Describe live node labels and relationship types from Neo4j."""
    label_rows = await run_read_cypher("CALL db.labels() YIELD label RETURN label ORDER BY label")
    rel_rows = await run_read_cypher(
        "CALL db.relationshipTypes() YIELD relationshipType "
        "RETURN relationshipType ORDER BY relationshipType"
    )
    labels = [str(row.get("label", "")) for row in label_rows if row.get("label")]
    rel_types = [
        str(row.get("relationshipType", "")) for row in rel_rows if row.get("relationshipType")
    ]
    label_list = ", ".join(labels) if labels else "(none)"
    rel_list = ", ".join(rel_types) if rel_types else "(none)"
    return f"Live Neo4j schema\nNode labels: {label_list}\nRelationship types: {rel_list}\n"
