"""Human-in-the-loop approval for gated tool calls."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, ToolMessage

GATED_TOOLS: dict[str, str] = {
    "run_cypher": "Run a Cypher query against Neo4j",
    "newsapi_search": "Search NewsAPI for headlines",
    "search_engine_news": "Search the web for news",
}


def tool_label(name: str) -> str:
    return GATED_TOOLS.get(name, name)


def _as_dict(tool_call: Any) -> dict[str, Any]:
    if isinstance(tool_call, dict):
        return tool_call
    return {
        "id": getattr(tool_call, "id", ""),
        "name": getattr(tool_call, "name", ""),
        "args": getattr(tool_call, "args", {}) or {},
    }


def gated_tool_calls(message: AIMessage) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for raw in message.tool_calls or []:
        call = _as_dict(raw)
        name = str(call.get("name") or "")
        if name in GATED_TOOLS:
            calls.append(
                {
                    "id": str(call.get("id") or ""),
                    "name": name,
                    "label": tool_label(name),
                    "args": dict(call.get("args") or {}),
                }
            )
    return calls


def pending_payload(calls: list[dict[str, Any]]) -> dict[str, Any]:
    return {"kind": "tool_approval", "tools": calls}


def pending_from_interrupt_value(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict) or value.get("kind") != "tool_approval":
        return None
    tools = value.get("tools")
    if not isinstance(tools, list) or not tools:
        return None
    return {"tools": tools}


def rejection_messages(calls: list[dict[str, Any]]) -> list[ToolMessage]:
    return [
        ToolMessage(
            content="The user declined this tool call. Continue without it.",
            tool_call_id=str(call["id"]),
        )
        for call in calls
        if call.get("id")
    ]


def extract_pending_from_result(result: Any) -> dict[str, Any] | None:
    interrupts = ()
    if hasattr(result, "get"):
        interrupts = result.get("__interrupt__") or ()
    if not interrupts:
        return None
    first = interrupts[0]
    value = first.value if hasattr(first, "value") else None
    if value is None and isinstance(first, dict):
        value = first.get("value")
    return pending_from_interrupt_value(value)


def extract_pending_from_state(state: Any) -> dict[str, Any] | None:
    interrupts = getattr(state, "interrupts", ()) or ()
    if not interrupts:
        tasks = getattr(state, "tasks", ()) or ()
        collected: list[Any] = []
        for task in tasks:
            collected.extend(getattr(task, "interrupts", ()) or ())
        interrupts = tuple(collected)
    if not interrupts:
        return None
    first = interrupts[0]
    value = first.value if hasattr(first, "value") else None
    return pending_from_interrupt_value(value)
