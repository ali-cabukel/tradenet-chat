"""LangGraph tools for schema lookup and read-only Cypher."""

from __future__ import annotations

import json

from langchain_core.tools import tool

from tradenet_chat.neo4j_client import (
    DEFAULT_GRAPH_SCHEMA,
    CypherWriteRejected,
    fetch_live_schema,
    run_read_cypher,
)
from tradenet_chat.news import newsapi_search as fetch_newsapi_headlines
from tradenet_chat.news import search_engine_news as fetch_search_engine_news
from tradenet_chat.wikipedia import lookup_wikipedia


def build_tools():
    @tool
    async def get_default_schema() -> str:
        """Return the default tradenet graph schema (Country, Category, TRADES_WITH)."""
        return DEFAULT_GRAPH_SCHEMA

    @tool
    async def get_live_schema() -> str:
        """Fetch live node labels and relationship types from the connected Neo4j database."""
        try:
            return await fetch_live_schema()
        except Exception as exc:
            return f"Failed to fetch live schema: {exc}"

    @tool
    async def run_cypher(cypher: str) -> str:
        """Run a read-only Cypher query against Neo4j. Write clauses are rejected."""
        try:
            rows = await run_read_cypher(cypher)
        except CypherWriteRejected as exc:
            return f"Rejected: {exc}"
        except Exception as exc:
            return f"Query failed: {exc}"
        if not rows:
            return "No rows returned."
        return json.dumps(rows, indent=2, default=str)

    @tool
    async def wikipedia_lookup(query: str) -> str:
        """Look up a country or topic on Wikipedia.

        Use this for background facts that are not in the trade graph: population,
        GDP, capital, area, language, government, or a short country overview.
        Pass a country name or ISO3 code (USA, TUR, DEU).
        """
        return await lookup_wikipedia(query)

    @tool
    async def newsapi_search(query: str) -> str:
        """Search recent news via NewsAPI.org (requires NEWS_API_KEY).

        Use for trade, country, commodity, or policy headlines. Pass a country
        name, ISO3 code, or topic such as 'Türkiye wheat exports'.
        """
        return await fetch_newsapi_headlines(query)

    @tool
    async def search_engine_news(query: str) -> str:
        """Search news via DuckDuckGo, with Google News RSS as fallback.

        Use when NewsAPI is unavailable or you want extra web headlines.
        """
        return await fetch_search_engine_news(query)

    return [
        get_default_schema,
        get_live_schema,
        run_cypher,
        wikipedia_lookup,
        newsapi_search,
        search_engine_news,
    ]
