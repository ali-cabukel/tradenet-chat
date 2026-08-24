"""Application settings loaded from environment and .env."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def async_database_url(url: str) -> str:
    """Normalize a database URL to an async SQLAlchemy driver."""
    value = url.strip()
    if value.startswith("postgres://"):
        return "postgresql+asyncpg://" + value.removeprefix("postgres://")
    if value.startswith("postgresql://") and not value.startswith("postgresql+"):
        return "postgresql+asyncpg://" + value.removeprefix("postgresql://")
    if value.startswith("sqlite://") and not value.startswith("sqlite+"):
        return "sqlite+aiosqlite://" + value.removeprefix("sqlite://")
    return value


class AppEnvironment(StrEnum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: AppEnvironment = Field(
        default=AppEnvironment.DEVELOPMENT,
        validation_alias="ENVIRONMENT",
    )
    app_title: str = Field(default="Tradenet Chat API", validation_alias="APP_TITLE")
    app_version: str = Field(default="0.1.0", validation_alias="APP_VERSION")

    secret_key: SecretStr = Field(
        default=SecretStr("dev-only-change-me"),
        validation_alias="SECRET_KEY",
    )
    jwt_lifetime_seconds: int = Field(default=3600, validation_alias="JWT_LIFETIME_SECONDS")

    db_path: Path | None = Field(default=None, validation_alias="DB_PATH")
    database_url_override: str | None = Field(default=None, validation_alias="DATABASE_URL")

    cors_origins_raw: str = Field(
        default=(
            "http://localhost:5173,http://127.0.0.1:5173,"
            "http://localhost:8080,http://127.0.0.1:8080"
        ),
        validation_alias="CORS_ORIGINS",
    )

    api_host: str = Field(default="0.0.0.0", validation_alias="API_HOST")
    api_port: int = Field(default=8000, validation_alias="API_PORT")
    api_reload: bool | None = Field(default=None, validation_alias="API_RELOAD")

    llm_provider: str = Field(default="openai", validation_alias="LLM_PROVIDER")
    openai_api_key: SecretStr | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", validation_alias="OPENAI_MODEL")
    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434",
        validation_alias="OLLAMA_BASE_URL",
    )
    ollama_model: str = Field(default="llama3.2", validation_alias="OLLAMA_MODEL")

    neo4j_uri: str = Field(default="bolt://127.0.0.1:7687", validation_alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", validation_alias="NEO4J_USER")
    neo4j_password: SecretStr = Field(default=SecretStr("neo4j"), validation_alias="NEO4J_PASSWORD")
    neo4j_database: str = Field(default="neo4j", validation_alias="NEO4J_DATABASE")

    news_api_key: SecretStr | None = Field(default=None, validation_alias="NEWS_API_KEY")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == AppEnvironment.PRODUCTION

    @property
    def is_development(self) -> bool:
        return self.environment == AppEnvironment.DEVELOPMENT

    @property
    def enable_api_docs(self) -> bool:
        return not self.is_production

    @property
    def resolved_db_path(self) -> Path:
        return self.db_path or PROJECT_ROOT / "data" / "tradenet-chat.db"

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return async_database_url(self.database_url_override)
        return f"sqlite+aiosqlite:///{self.resolved_db_path}"

    @property
    def is_postgres(self) -> bool:
        scheme = self.database_url.split(":", 1)[0]
        return "postgres" in scheme

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def should_reload(self) -> bool:
        if self.api_reload is not None:
            return self.api_reload
        return self.is_development

    def resolved_llm_provider(self) -> str:
        provider = self.llm_provider.strip().lower()
        if provider in {"openai", "ollama"}:
            return provider
        if self.openai_api_key and self.openai_api_key.get_secret_value():
            return "openai"
        return "ollama"

    def require_openai_api_key(self) -> str:
        if not self.openai_api_key or not self.openai_api_key.get_secret_value():
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        return self.openai_api_key.get_secret_value()

    @model_validator(mode="after")
    def validate_production_config(self) -> Settings:
        if not self.is_production:
            return self
        secret = self.secret_key.get_secret_value()
        if not secret or secret in {"dev-only-change-me", "change-me-in-production"}:
            raise ValueError("SECRET_KEY must be a strong value when ENVIRONMENT=production")
        if "*" in self.cors_origins_raw:
            raise ValueError("CORS_ORIGINS must not use '*' in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
