"""Health check."""

from __future__ import annotations

from fastapi import APIRouter

from tradenet_chat.settings import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    settings = get_settings()
    scheme = settings.database_url.split(":", 1)[0]
    database = "postgres" if "postgres" in scheme else "sqlite"
    return {
        "status": "ok",
        "llm_provider": settings.resolved_llm_provider(),
        "neo4j_uri": settings.neo4j_uri,
        "database": database,
        "news_api": "configured" if settings.news_api_key else "missing",
    }
