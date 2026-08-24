"""Chat model factory — OpenAI or Ollama."""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from tradenet_chat.settings import get_settings


def create_chat_model() -> BaseChatModel:
    settings = get_settings()
    provider = settings.resolved_llm_provider()
    if provider == "openai":
        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.require_openai_api_key(),
            temperature=0,
        )
    if provider == "ollama":
        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=0,
        )
    raise RuntimeError(f"Unsupported LLM provider: {provider}")
