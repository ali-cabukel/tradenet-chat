"""Async SQLAlchemy engine and session factory."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from tradenet_chat.db.models import Base
from tradenet_chat.settings import get_settings

_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        url = settings.database_url
        kwargs: dict = {"echo": False}
        if settings.is_sqlite:
            settings.resolved_db_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            kwargs["pool_pre_ping"] = True
        _engine = create_async_engine(url, **kwargs)
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    global _session_maker
    if _session_maker is None:
        _session_maker = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_maker


def ensure_chat_message_columns(connection: Connection) -> None:
    """Add feedback/regenerate columns on existing databases.

    ``create_all`` does not alter tables, so a running SQLite or Postgres database
    would otherwise keep the original ``chat_messages`` shape.
    """
    inspector = inspect(connection)
    if "chat_messages" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("chat_messages")}
    timestamp_type = (
        "TIMESTAMP WITH TIME ZONE" if connection.dialect.name == "postgresql" else "DATETIME"
    )
    additions: list[str] = []
    if "feedback" not in existing:
        additions.append("feedback VARCHAR(8)")
    if "feedback_at" not in existing:
        additions.append(f"feedback_at {timestamp_type}")
    if "regenerate_count" not in existing:
        additions.append("regenerate_count INTEGER DEFAULT 0 NOT NULL")
    if "regenerated_at" not in existing:
        additions.append(f"regenerated_at {timestamp_type}")
    if "queries" not in existing:
        query_type = "JSONB" if connection.dialect.name == "postgresql" else "JSON"
        additions.append(f"queries {query_type}")
    for column_def in additions:
        connection.execute(text(f"ALTER TABLE chat_messages ADD COLUMN {column_def}"))


async def init_db() -> None:
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(ensure_chat_message_columns)


async def get_async_session() -> AsyncGenerator[AsyncSession]:
    async with get_session_maker()() as session:
        yield session


async def dispose_engine() -> None:
    global _engine, _session_maker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_maker = None
