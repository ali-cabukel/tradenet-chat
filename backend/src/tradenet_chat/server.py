"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tradenet_chat.api.routers import chat, health
from tradenet_chat.auth.deps import auth_backend, fastapi_users
from tradenet_chat.auth.models import User  # noqa: F401 — register user table
from tradenet_chat.auth.schemas import UserCreate, UserRead, UserUpdate
from tradenet_chat.db.engine import dispose_engine, init_db
from tradenet_chat.settings import get_settings


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_title,
        description="Conversational agent that generates Cypher queries for Neo4j.",
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs" if settings.enable_api_docs else None,
        redoc_url="/redoc" if settings.enable_api_docs else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(
        fastapi_users.get_auth_router(auth_backend),
        prefix="/api/auth/jwt",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_register_router(UserRead, UserCreate),
        prefix="/api/auth",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_users_router(UserRead, UserUpdate),
        prefix="/api/users",
        tags=["users"],
    )
    app.include_router(health.router)
    app.include_router(health.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")

    return app


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "tradenet_chat.server:create_app",
        factory=True,
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.should_reload,
    )


if __name__ == "__main__":
    run()
