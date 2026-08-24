"""Agent runtime that persists chat threads and invokes the Cypher agent."""

from __future__ import annotations

import uuid
from contextlib import suppress
from typing import Any

from langchain_core.messages import HumanMessage, RemoveMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from tradenet_chat.agents.approval import extract_pending_from_result, extract_pending_from_state
from tradenet_chat.agents.graph import (
    create_cypher_agent,
    extract_reply_text,
    extract_run_cypher_queries,
    strip_cypher_fences,
)
from tradenet_chat.db.chat import (
    add_chat_message,
    create_chat_thread,
    delete_chat_thread,
    fetch_chat_message_for_user,
    fetch_chat_messages,
    fetch_chat_thread,
    set_message_feedback,
    touch_chat_thread,
    update_assistant_reply,
)
from tradenet_chat.db.engine import get_session_maker


class ApprovalRequired(Exception):
    def __init__(self) -> None:
        super().__init__("This thread is waiting for tool approval")


class AgentService:
    def __init__(self) -> None:
        self.checkpointer = MemorySaver()
        self._agent = create_cypher_agent(self.checkpointer)
        self._regen_targets: dict[str, int] = {}

    def _config(self, thread_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": thread_id}}

    async def create_thread(
        self,
        user_id: uuid.UUID,
        *,
        title: str | None = None,
    ) -> str:
        thread_id = str(uuid.uuid4())
        async with get_session_maker()() as session:
            await create_chat_thread(
                session,
                thread_id=thread_id,
                user_id=user_id,
                title=title or "New chat",
            )
        return thread_id

    async def delete_thread(self, user_id: uuid.UUID, thread_id: str) -> None:
        async with get_session_maker()() as session:
            deleted = await delete_chat_thread(session, thread_id, user_id)
        if not deleted:
            raise LookupError("Chat thread not found")
        self._regen_targets.pop(thread_id, None)
        with suppress(Exception):
            await self.checkpointer.adelete_thread(thread_id)

    async def pending_approval(self, user_id: uuid.UUID, thread_id: str) -> dict[str, Any] | None:
        async with get_session_maker()() as session:
            thread = await fetch_chat_thread(session, thread_id, user_id)
            if thread is None:
                raise LookupError("Chat thread not found")
        state = await self._agent.aget_state(self._config(thread_id))
        return extract_pending_from_state(state)

    async def send_message(
        self,
        user_id: uuid.UUID,
        thread_id: str,
        content: str,
    ) -> tuple[object, object | None, dict[str, Any] | None]:
        text = content.strip()
        async with get_session_maker()() as session:
            thread = await fetch_chat_thread(session, thread_id, user_id)
            if thread is None:
                raise LookupError("Chat thread not found")
            if thread.title in {None, "", "New chat"}:
                thread.title = text[:80]
                await session.commit()

        if await self.pending_approval(user_id, thread_id):
            raise ApprovalRequired()

        self._regen_targets.pop(thread_id, None)
        user_message = await self._persist_message(thread_id, "user", text)

        result = await self._agent.ainvoke(
            {"messages": [HumanMessage(content=text)]},
            config=self._config(thread_id),
        )
        pending = extract_pending_from_result(result) or extract_pending_from_state(
            await self._agent.aget_state(self._config(thread_id))
        )
        if pending:
            return user_message, None, pending

        reply_text = extract_reply_text(result["messages"])
        assistant_message = await self._persist_assistant_reply(
            thread_id, reply_text, result["messages"]
        )
        return user_message, assistant_message, None

    async def resolve_approval(
        self,
        user_id: uuid.UUID,
        thread_id: str,
        decision: str,
    ) -> tuple[object | None, dict[str, Any] | None]:
        if decision not in {"accept", "reject"}:
            raise ValueError("decision must be accept or reject")

        pending = await self.pending_approval(user_id, thread_id)
        if pending is None:
            raise LookupError("No pending tool approval")

        result = await self._agent.ainvoke(
            Command(resume=decision),
            config=self._config(thread_id),
        )
        next_pending = extract_pending_from_result(result) or extract_pending_from_state(
            await self._agent.aget_state(self._config(thread_id))
        )
        if next_pending:
            return None, next_pending

        reply_text = extract_reply_text(result["messages"])
        assistant_message = await self._persist_assistant_reply(
            thread_id, reply_text, result["messages"]
        )
        return assistant_message, None

    async def set_feedback(
        self,
        user_id: uuid.UUID,
        thread_id: str,
        message_id: int,
        rating: str | None,
    ):
        async with get_session_maker()() as session:
            thread = await fetch_chat_thread(session, thread_id, user_id)
            if thread is None:
                raise LookupError("Chat thread not found")
            message = await set_message_feedback(
                session,
                message_id=message_id,
                thread_id=thread_id,
                user_id=user_id,
                rating=rating,
            )
        if message is None:
            raise LookupError("Chat message not found")
        return message

    async def regenerate(
        self,
        user_id: uuid.UUID,
        thread_id: str,
        message_id: int,
    ) -> tuple[object | None, dict[str, Any] | None]:
        if await self.pending_approval(user_id, thread_id):
            raise ApprovalRequired()

        async with get_session_maker()() as session:
            message = await fetch_chat_message_for_user(
                session, message_id=message_id, thread_id=thread_id, user_id=user_id
            )
            if message is None:
                raise LookupError("Chat message not found")
            if message.role != "assistant":
                raise ValueError("Only assistant replies can be regenerated")
            messages = await fetch_chat_messages(session, thread_id)

        if not messages or messages[-1].id != message.id:
            raise ValueError("Only the latest assistant reply can be regenerated")

        last_user = next((item for item in reversed(messages) if item.role == "user"), None)
        if last_user is None:
            raise ValueError("No user prompt to regenerate from")

        self._regen_targets[thread_id] = message.id
        try:
            result = await self._rerun_last_turn(thread_id, last_user.content)
            pending = extract_pending_from_result(result) or extract_pending_from_state(
                await self._agent.aget_state(self._config(thread_id))
            )
            if pending:
                return None, pending

            reply_text = extract_reply_text(result["messages"])
            assistant_message = await self._persist_assistant_reply(
                thread_id, reply_text, result["messages"]
            )
            return assistant_message, None
        except Exception:
            self._regen_targets.pop(thread_id, None)
            raise

    async def _checkpoint_after_last_human(self, thread_id: str) -> dict[str, Any] | None:
        async for snapshot in self._agent.aget_state_history(self._config(thread_id)):
            messages = (snapshot.values or {}).get("messages") or []
            if not messages or not snapshot.next:
                continue
            if isinstance(messages[-1], HumanMessage):
                return snapshot.config
        return None

    async def _rerun_last_turn(self, thread_id: str, user_text: str) -> dict[str, Any]:
        config = self._config(thread_id)
        replay_config = await self._checkpoint_after_last_human(thread_id)
        if replay_config is not None:
            return await self._agent.ainvoke(None, replay_config)

        state = await self._agent.aget_state(config)
        messages = list((state.values or {}).get("messages") or [])
        if not messages:
            return await self._agent.ainvoke(
                {"messages": [HumanMessage(content=user_text)]},
                config=config,
            )

        to_remove: list[RemoveMessage] = []
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                break
            msg_id = getattr(msg, "id", None)
            if msg_id:
                to_remove.append(RemoveMessage(id=msg_id))
        if to_remove:
            await self._agent.aupdate_state(config, {"messages": to_remove})
        return await self._agent.ainvoke(Command(goto="agent"), config)

    async def _persist_assistant_reply(self, thread_id: str, reply_text: str, messages: list):
        queries = extract_run_cypher_queries(messages)
        content = strip_cypher_fences(reply_text)
        target_id = self._regen_targets.pop(thread_id, None)
        async with get_session_maker()() as session:
            if target_id is not None:
                updated = await update_assistant_reply(
                    session,
                    message_id=target_id,
                    content=content,
                    regenerated=True,
                    queries=queries,
                )
                if updated is not None:
                    await touch_chat_thread(session, thread_id)
                    return updated
            message = await add_chat_message(
                session,
                thread_id=thread_id,
                role="assistant",
                content=content,
                queries=queries,
            )
            await touch_chat_thread(session, thread_id)
            return message

    async def _persist_message(self, thread_id: str, role: str, content: str):
        async with get_session_maker()() as session:
            return await add_chat_message(
                session,
                thread_id=thread_id,
                role=role,
                content=content,
            )


_agent_service: AgentService | None = None


def get_agent_service() -> AgentService:
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service
