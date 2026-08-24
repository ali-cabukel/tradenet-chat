"""LangGraph ReAct agent that generates and runs read-only Cypher."""

from __future__ import annotations

import re

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langgraph.types import interrupt

from tradenet_chat.agents.approval import (
    gated_tool_calls,
    pending_payload,
    rejection_messages,
)
from tradenet_chat.agents.llm import create_chat_model
from tradenet_chat.agents.tools import build_tools

SYSTEM_PROMPT = """You are Tradenet Chat, an assistant that answers questions about a \
Neo4j trade graph by writing and running read-only Cypher.

The default graph is tradenet: Country and Category nodes, with \
(Country)-[:TRADES_WITH]->(Country) edges from exporter to importer. \
Relationship properties include year, supplyCategory, tradeValueUsd, \
netWeightKg, and flowCount.

You can:
- Call get_default_schema for the expected Country / Category / TRADES_WITH shape
- Call get_live_schema to see labels and relationship types actually in Neo4j
- Call run_cypher to execute a MATCH/RETURN query (writes are rejected)
- Call wikipedia_lookup for country background (population, GDP, capital, geography)
- Call newsapi_search for recent headlines (NewsAPI.org)
- Call search_engine_news for DuckDuckGo / Google News headlines

Workflow:
1. Trade questions: use schema tools if needed, then write and run read-only Cypher
2. Country facts (GDP, population, capital, etc.): call wikipedia_lookup
3. Recent news: try newsapi_search; if the key is missing or it fails, use search_engine_news
4. If a question needs both trade data and news, query Neo4j and a news tool
5. Do not paste Cypher in the answer body — the UI shows executed queries separately
6. Cite article titles as markdown links when you use news or Wikipedia

Format every answer as GitHub-flavored Markdown:
- Lead with a short sentence or heading
- Put trade query results in a markdown table (columns left-aligned, numbers \
with thousands separators). Do not dump raw JSON from tools
- Use bullet lists for news: `- [title](url) — outlet, date`
- Bold country names and key figures

Never attempt CREATE, MERGE, DELETE, DETACH, SET, REMOVE, DROP, LOAD CSV, \
FOREACH, or ALTER. If a query is rejected, rewrite it as a read.

Be concise. If Neo4j is unreachable, say so and still propose the Cypher.

Cypher, NewsAPI, and web news searches pause for the user to approve before they run."""


def review_tool_calls(state: dict) -> dict:
    """Pause before Cypher, NewsAPI, or web news tools until the user approves."""
    messages = state["messages"]
    if not messages:
        return {}
    last = messages[-1]
    if not isinstance(last, AIMessage):
        return {}
    gated = gated_tool_calls(last)
    if not gated:
        return {}

    decision = interrupt(pending_payload(gated))
    if decision == "reject":
        return {"messages": rejection_messages(gated)}
    return {}


def create_cypher_agent(checkpointer: BaseCheckpointSaver | None = None):
    model = create_chat_model()
    tools = build_tools()
    return create_react_agent(
        model,
        tools,
        prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer or MemorySaver(),
        post_model_hook=review_tool_calls,
    )


def extract_reply_text(messages: list) -> str:
    for message in reversed(messages):
        if isinstance(message, AIMessage) and not message.tool_calls:
            content = message.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, str):
                        parts.append(block)
                    elif isinstance(block, dict) and block.get("type") == "text":
                        parts.append(str(block.get("text", "")))
                return "\n".join(part for part in parts if part)
    return "I couldn't generate a response."


_CYPHER_FENCE = re.compile(r"```(?:cypher)\s*\n.*?```", re.IGNORECASE | re.DOTALL)


def strip_cypher_fences(text: str) -> str:
    """Remove ```cypher blocks so the query is only shown in the UI guardrail."""
    cleaned = _CYPHER_FENCE.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def extract_run_cypher_queries(messages: list) -> list[str]:
    """Collect Cypher from ``run_cypher`` tool calls after the last user turn."""
    start = 0
    for index, message in enumerate(messages):
        if isinstance(message, HumanMessage):
            start = index
    queries: list[str] = []
    seen: set[str] = set()
    for message in messages[start:]:
        if not isinstance(message, AIMessage) or not message.tool_calls:
            continue
        for call in message.tool_calls:
            name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
            if name != "run_cypher":
                continue
            args = call.get("args") if isinstance(call, dict) else getattr(call, "args", None)
            if not isinstance(args, dict):
                continue
            cypher = args.get("cypher")
            if not isinstance(cypher, str):
                continue
            text = cypher.strip()
            if text and text not in seen:
                seen.add(text)
                queries.append(text)
    return queries
