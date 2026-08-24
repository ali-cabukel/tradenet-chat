"""Pydantic schemas for the HTTP API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatThreadCreate(BaseModel):
    title: str | None = None


class ChatThreadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str | None
    created_at: datetime
    updated_at: datetime


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1)


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    thread_id: str
    role: str
    content: str
    created_at: datetime
    feedback: Literal["up", "down"] | None = None
    feedback_at: datetime | None = None
    regenerate_count: int = 0
    regenerated_at: datetime | None = None
    queries: list[str] = Field(default_factory=list)

    @field_validator("queries", mode="before")
    @classmethod
    def empty_queries(cls, value: object) -> object:
        return value or []


class MessageFeedbackUpdate(BaseModel):
    rating: Literal["up", "down"] | None = None


class PendingToolCall(BaseModel):
    id: str
    name: str
    label: str
    args: dict[str, Any] = Field(default_factory=dict)


class PendingApproval(BaseModel):
    tools: list[PendingToolCall]


class ApprovalDecision(BaseModel):
    decision: Literal["accept", "reject"]


class ChatReplyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    thread_id: str
    message: ChatMessageOut | None = None
    reply: ChatMessageOut | None = None
    pending_approval: PendingApproval | None = None
