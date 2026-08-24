from __future__ import annotations

from langchain_core.messages import AIMessage

from tradenet_chat.agents.approval import (
    gated_tool_calls,
    pending_from_interrupt_value,
    pending_payload,
    rejection_messages,
)


def test_gated_tool_calls_keeps_news_search_and_cypher() -> None:
    message = AIMessage(
        content="",
        tool_calls=[
            {"name": "get_live_schema", "args": {}, "id": "1", "type": "tool_call"},
            {
                "name": "run_cypher",
                "args": {"cypher": "MATCH (n) RETURN n"},
                "id": "2",
                "type": "tool_call",
            },
            {
                "name": "newsapi_search",
                "args": {"query": "Turkey wheat"},
                "id": "3",
                "type": "tool_call",
            },
            {
                "name": "search_engine_news",
                "args": {"query": "US China trade"},
                "id": "4",
                "type": "tool_call",
            },
            {
                "name": "wikipedia_lookup",
                "args": {"query": "Germany"},
                "id": "5",
                "type": "tool_call",
            },
        ],
    )
    gated = gated_tool_calls(message)
    assert [call["name"] for call in gated] == [
        "run_cypher",
        "newsapi_search",
        "search_engine_news",
    ]
    assert gated[0]["label"] == "Run a Cypher query against Neo4j"


def test_pending_payload_roundtrip() -> None:
    calls = [
        {
            "id": "2",
            "name": "run_cypher",
            "label": "Run a Cypher query against Neo4j",
            "args": {"cypher": "MATCH (n) RETURN n"},
        }
    ]
    payload = pending_payload(calls)
    parsed = pending_from_interrupt_value(payload)
    assert parsed == {"tools": calls}
    assert pending_from_interrupt_value({"kind": "other"}) is None


def test_extract_pending_from_result() -> None:
    from tradenet_chat.agents.approval import extract_pending_from_result

    class FakeInterrupt:
        def __init__(self, value: object) -> None:
            self.value = value

    calls = [
        {
            "id": "2",
            "name": "run_cypher",
            "label": "Run a Cypher query against Neo4j",
            "args": {"cypher": "RETURN 1"},
        }
    ]
    result = {"__interrupt__": (FakeInterrupt(pending_payload(calls)),)}
    assert extract_pending_from_result(result) == {"tools": calls}


def test_rejection_messages_match_tool_ids() -> None:
    messages = rejection_messages(
        [{"id": "abc", "name": "run_cypher", "label": "query", "args": {}}]
    )
    assert len(messages) == 1
    assert messages[0].tool_call_id == "abc"
    assert "declined" in messages[0].content.lower()
