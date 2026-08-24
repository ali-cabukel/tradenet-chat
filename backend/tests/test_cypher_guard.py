from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from tradenet_chat.agents.graph import extract_run_cypher_queries, strip_cypher_fences
from tradenet_chat.neo4j_client import CypherWriteRejected, assert_read_only


def test_assert_read_only_allows_match_return() -> None:
    assert_read_only("MATCH (n:Country) RETURN n.name LIMIT 10")
    assert_read_only(
        "MATCH (a:Country)-[r:TRADES_WITH]->(b:Country) "
        "WHERE r.supplyCategory = 'energy' "
        "RETURN a.name, b.name, r.tradeValueUsd"
    )
    assert_read_only("CALL db.labels() YIELD label RETURN label")


def test_assert_read_only_rejects_create() -> None:
    with pytest.raises(CypherWriteRejected):
        assert_read_only("CREATE (n:Country {iso3: 'XXX'})")


def test_assert_read_only_rejects_delete() -> None:
    with pytest.raises(CypherWriteRejected):
        assert_read_only("MATCH (n) DELETE n")


def test_assert_read_only_rejects_merge() -> None:
    with pytest.raises(CypherWriteRejected):
        assert_read_only("MERGE (c:Country {iso3: 'DEU'})")


def test_assert_read_only_rejects_set() -> None:
    with pytest.raises(CypherWriteRejected):
        assert_read_only("MATCH (n:Country {iso3: 'DEU'}) SET n.name = 'Germany'")


def test_extract_run_cypher_queries_from_last_turn() -> None:
    older = "MATCH (n) RETURN n"
    latest = "MATCH (a:Country)-[r:TRADES_WITH]->(b) RETURN a.name"
    messages = [
        HumanMessage(content="old"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "run_cypher",
                    "args": {"cypher": older},
                    "id": "1",
                    "type": "tool_call",
                }
            ],
        ),
        HumanMessage(content="new"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "run_cypher",
                    "args": {"cypher": latest},
                    "id": "2",
                    "type": "tool_call",
                },
                {
                    "name": "wikipedia_lookup",
                    "args": {"query": "DEU"},
                    "id": "3",
                    "type": "tool_call",
                },
            ],
        ),
    ]
    assert extract_run_cypher_queries(messages) == [latest]


def test_strip_cypher_fences() -> None:
    text = "Here is the answer.\n\n```cypher\nMATCH (n) RETURN n\n```\n\nDone."
    assert strip_cypher_fences(text) == "Here is the answer.\n\nDone."
