"""Chat endpoints for the Cypher agent."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from tradenet_chat.agents.service import ApprovalRequired, get_agent_service
from tradenet_chat.api.schemas import (
    ApprovalDecision,
    ChatMessageCreate,
    ChatMessageOut,
    ChatReplyOut,
    ChatThreadCreate,
    ChatThreadOut,
    MessageFeedbackUpdate,
    PendingApproval,
)
from tradenet_chat.auth.deps import current_active_user
from tradenet_chat.auth.models import User
from tradenet_chat.db.chat import fetch_chat_messages, fetch_chat_thread, fetch_chat_threads
from tradenet_chat.db.engine import get_async_session

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/threads", response_model=ChatThreadOut, status_code=status.HTTP_201_CREATED)
async def create_thread(
    payload: ChatThreadCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> ChatThreadOut:
    agent = get_agent_service()
    thread_id = await agent.create_thread(user.id, title=payload.title)
    thread = await fetch_chat_thread(session, thread_id, user.id)
    if thread is None:
        raise HTTPException(status_code=500, detail="Failed to create chat thread")
    return ChatThreadOut.model_validate(thread)


@router.get("/threads", response_model=list[ChatThreadOut])
async def list_threads(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> list[ChatThreadOut]:
    threads = await fetch_chat_threads(session, user.id)
    return [ChatThreadOut.model_validate(thread) for thread in threads]


@router.get("/threads/{thread_id}", response_model=ChatThreadOut)
async def get_thread(
    thread_id: str,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> ChatThreadOut:
    thread = await fetch_chat_thread(session, thread_id, user.id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Chat thread not found")
    return ChatThreadOut.model_validate(thread)


@router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(
    thread_id: str,
    user: User = Depends(current_active_user),
) -> Response:
    agent = get_agent_service()
    try:
        await agent.delete_thread(user.id, thread_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/threads/{thread_id}/messages", response_model=list[ChatMessageOut])
async def list_messages(
    thread_id: str,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> list[ChatMessageOut]:
    thread = await fetch_chat_thread(session, thread_id, user.id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Chat thread not found")
    messages = await fetch_chat_messages(session, thread_id)
    return [ChatMessageOut.model_validate(message) for message in messages]


@router.post("/threads/{thread_id}/messages", response_model=ChatReplyOut)
async def send_message(
    thread_id: str,
    payload: ChatMessageCreate,
    user: User = Depends(current_active_user),
) -> ChatReplyOut:
    agent = get_agent_service()
    try:
        user_message, assistant_message, pending = await agent.send_message(
            user.id, thread_id, payload.content
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ApprovalRequired as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Agent failed: {exc}") from exc

    return ChatReplyOut(
        thread_id=thread_id,
        message=ChatMessageOut.model_validate(user_message),
        reply=ChatMessageOut.model_validate(assistant_message) if assistant_message else None,
        pending_approval=PendingApproval.model_validate(pending) if pending else None,
    )


@router.get("/threads/{thread_id}/approval", response_model=PendingApproval | None)
async def get_approval(
    thread_id: str,
    user: User = Depends(current_active_user),
) -> PendingApproval | None:
    agent = get_agent_service()
    try:
        pending = await agent.pending_approval(user.id, thread_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if pending is None:
        return None
    return PendingApproval.model_validate(pending)


@router.post("/threads/{thread_id}/approvals", response_model=ChatReplyOut)
async def resolve_approval(
    thread_id: str,
    payload: ApprovalDecision,
    user: User = Depends(current_active_user),
) -> ChatReplyOut:
    agent = get_agent_service()
    try:
        assistant_message, pending = await agent.resolve_approval(
            user.id, thread_id, payload.decision
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Agent failed: {exc}") from exc

    return ChatReplyOut(
        thread_id=thread_id,
        reply=ChatMessageOut.model_validate(assistant_message) if assistant_message else None,
        pending_approval=PendingApproval.model_validate(pending) if pending else None,
    )


@router.patch("/threads/{thread_id}/messages/{message_id}/feedback", response_model=ChatMessageOut)
async def update_message_feedback(
    thread_id: str,
    message_id: int,
    payload: MessageFeedbackUpdate,
    user: User = Depends(current_active_user),
) -> ChatMessageOut:
    agent = get_agent_service()
    try:
        message = await agent.set_feedback(user.id, thread_id, message_id, payload.rating)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ChatMessageOut.model_validate(message)


@router.post("/threads/{thread_id}/messages/{message_id}/regenerate", response_model=ChatReplyOut)
async def regenerate_message(
    thread_id: str,
    message_id: int,
    user: User = Depends(current_active_user),
) -> ChatReplyOut:
    agent = get_agent_service()
    try:
        assistant_message, pending = await agent.regenerate(user.id, thread_id, message_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ApprovalRequired as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Agent failed: {exc}") from exc

    return ChatReplyOut(
        thread_id=thread_id,
        reply=ChatMessageOut.model_validate(assistant_message) if assistant_message else None,
        pending_approval=PendingApproval.model_validate(pending) if pending else None,
    )
