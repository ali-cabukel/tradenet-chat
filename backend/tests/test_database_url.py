from __future__ import annotations

import pytest

from tradenet_chat.settings import Settings, async_database_url


def test_async_database_url_postgres_schemes() -> None:
    assert (
        async_database_url("postgres://u:p@localhost:5432/db")
        == "postgresql+asyncpg://u:p@localhost:5432/db"
    )
    assert (
        async_database_url("postgresql://u:p@localhost/db")
        == "postgresql+asyncpg://u:p@localhost/db"
    )
    assert (
        async_database_url("postgresql+asyncpg://u:p@localhost/db")
        == "postgresql+asyncpg://u:p@localhost/db"
    )


def test_async_database_url_sqlite() -> None:
    assert async_database_url("sqlite:///./x.db") == "sqlite+aiosqlite:///./x.db"
    assert async_database_url("sqlite+aiosqlite:///./x.db") == "sqlite+aiosqlite:///./x.db"


def test_settings_postgres_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://tradenet:tradenet@postgres:5432/tradenet_chat"
    )
    settings = Settings(_env_file=None)
    assert settings.is_postgres
    assert not settings.is_sqlite
    assert settings.database_url == (
        "postgresql+asyncpg://tradenet:tradenet@postgres:5432/tradenet_chat"
    )


def test_settings_default_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DB_PATH", raising=False)
    settings = Settings(_env_file=None)
    assert settings.is_sqlite
    assert not settings.is_postgres
    assert settings.database_url.startswith("sqlite+aiosqlite:///")
