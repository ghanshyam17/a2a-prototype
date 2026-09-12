"""LLM client factory (Ollama by default)."""

from __future__ import annotations

import logging
from typing import Any

from a2a.agents.base import LLMClient
from a2a.config import settings

logger = logging.getLogger(__name__)


class OllamaLLM:
    """Adapter around langchain_ollama.ChatOllama implementing LLMClient."""

    def __init__(self, model: str | None = None, base_url: str | None = None) -> None:
        from langchain_ollama import ChatOllama

        self._model = ChatOllama(
            model=model or settings.ollama_model,
            base_url=base_url or settings.ollama_base_url,
            temperature=0.2,
        )

    def invoke(self, messages: list[dict[str, str]]) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage

        lc_msgs: list[Any] = []
        for m in messages:
            if m["role"] == "system":
                lc_msgs.append(SystemMessage(content=m["content"]))
            else:
                lc_msgs.append(HumanMessage(content=m["content"]))
        try:
            return str(self._model.invoke(lc_msgs).content)
        except Exception as exc:  # pragma: no cover - network dependent
            logger.warning("Ollama invoke failed (%s); using stub fallback.", exc)
            return StubLLM().invoke(messages)


class StubLLM:
    """Deterministic stub used when no LLM is available (tests / offline demos)."""

    def invoke(self, messages: list[dict[str, str]]) -> str:
        user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        return f"[stub] Echo: {user[:200]}"


def make_llm(provider: str | None = None) -> LLMClient:
    provider = provider or settings.model_provider
    if provider == "ollama":
        try:
            return OllamaLLM()
        except Exception as exc:  # pragma: no cover - env dependent
            logger.warning("Falling back to StubLLM (%s)", exc)
            return StubLLM()
    return StubLLM()