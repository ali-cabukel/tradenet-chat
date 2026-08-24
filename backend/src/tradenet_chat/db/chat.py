"""Chat thread and message persistence."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tradenet_chat.db.models import ChatMessage, ChatThread


def _now() -> datetime:
    return datetime.now(UTC)


async def create_chat_thread(
    session: AsyncSession,
    *,
    thread_id: str,
    user_id: uuid.UUID,
    title: str | None = None,
) -> ChatThread:
    thread = ChatThread(id=thread_id, user_id=user_id, title=title)
    session.add(thread)
    await session.commit()
    await session.refresh(thread)
    return thread


async def fetch_chat_threads(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int = 50,
) -> list[ChatThread]:
    result = await session.execute(
        select(ChatThread)
        .where(ChatThread.user_id == user_id)
        .order_by(ChatThread.updated_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def fetch_chat_thread(
    session: AsyncSession,
    thread_id: str,
    user_id: uuid.UUID,
) -> ChatThread | None:
    result = await session.execute(
        select(ChatThread).where(ChatThread.id == thread_id, ChatThread.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def fetch_chat_messages(session: AsyncSession, thread_id: str) -> list[ChatMessage]:
    result = await session.execute(
        select(ChatMessage)
        .where(ChatMessage.thread_id == thread_id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
    )
    return list(result.scalars().all())


async def add_chat_message(
    session: AsyncSession,
    *,
    thread_id: str,
    role: str,
    content: str,
    queries: list[str] | None = None,
) -> ChatMessage:
    message = ChatMessage(
        thread_id=thread_id,
        role=role,
        content=content,
        queries=queries or None,
    )
    session.add(message)
    await session.commit()
    await session.refresh(message)
    return message


async def fetch_chat_message_for_user(
    session: AsyncSession,
    *,
    message_id: int,
    thread_id: str,
    user_id: uuid.UUID,
) -> ChatMessage | None:
    result = await session.execute(
        select(ChatMessage)
        .join(ChatThread)
        .where(
            ChatMessage.id == message_id,
            ChatMessage.thread_id == thread_id,
            ChatThread.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def set_message_feedback(
    session: AsyncSession,
    *,
    message_id: int,
    thread_id: str,
    user_id: uuid.UUID,
    rating: str | None,
) -> ChatMessage | None:
    message = await fetch_chat_message_for_user(
        session, message_id=message_id, thread_id=thread_id, user_id=user_id
    )
    if message is None:
        return None
    if message.role != "assistant":
        raise ValueError("Feedback can only be stored on assistant messages")
    if rating not in {None, "up", "down"}:
        raise ValueError("rating must be up, down, or null")
    message.feedback = rating
    message.feedback_at = _now() if rating is not None else None
    await session.commit()
    await session.refresh(message)
    return message


async def update_assistant_reply(
    session: AsyncSession,
    *,
    message_id: int,
    content: str,
    regenerated: bool = False,
    queries: list[str] | None = None,
) -> ChatMessage | None:
    message = await session.get(ChatMessage, message_id)
    if message is None or message.role != "assistant":
        return None
    message.content = content
    message.queries = queries or None
    message.feedback = None
    message.feedback_at = None
    if regenerated:
        message.regenerate_count = (message.regenerate_count or 0) + 1
        message.regenerated_at = _now()
    await session.commit()
    await session.refresh(message)
    return message


async def delete_chat_thread(
    session: AsyncSession,
    thread_id: str,
    user_id: uuid.UUID,
) -> bool:
    result = await session.execute(
        select(ChatThread)
        .options(selectinload(ChatThread.messages))
        .where(ChatThread.id == thread_id, ChatThread.user_id == user_id)
    )
    thread = result.scalar_one_or_none()
    if thread is None:
        return False
    await session.delete(thread)
    await session.commit()
    return True


async def touch_chat_thread(session: AsyncSession, thread_id: str) -> None:
    thread = await session.get(ChatThread, thread_id)
    if thread is not None:
        thread.updated_at = _now()
        await session.commit()
