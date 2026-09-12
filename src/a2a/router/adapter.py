"""``RoutedLLM`` — an ``LLMClient`` that routes each call to a small or large
Ollama model via the agentic_router hybrid router.

Usage::

    llm = make_routed_llm()
    agent = ProAgent(llm=llm)
    llm.on_route = lambda decision: print(decision.to_dict())
    agent.run("...")

The last ``RouteDecision`` for each ``invoke`` is stored on
``llm.last_decision`` and forwarded to ``on_route`` if set. The orchestrator
uses this hook to emit ``route`` events into the SSE stream.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from a2a.agents.base import LLMClient
from a2a.agents.llm import StubLLM
from a2a.config import settings
from a2a.router.bridge import AgenticRouterBridge
from a2a.router.models import RouteDecision, RouteMethod, RouteTier

logger = logging.getLogger(__name__)


class RoutedLLM:
    """LLM client that routes each invoke to a lower or higher Ollama model."""

    def __init__(
        self,
        lower_model: str,
        higher_model: str,
        base_url: str,
        api_key: str = "EMPTY",
        bridge: AgenticRouterBridge | None = None,
        fallback_llm: LLMClient | None = None,
    ) -> None:
        self.lower_model = lower_model
        self.higher_model = higher_model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.bridge = bridge or AgenticRouterBridge(
            lower_threshold=settings.router_lower_threshold,
            higher_threshold=settings.router_higher_threshold,
            classifier_band=settings.router_classifier_band,
        )
        self.fallback = fallback_llm or StubLLM()
        self.last_decision: RouteDecision | None = None
        self.on_route: Callable[[RouteDecision], None] | None = None
        self._clients: dict[str, Any] = {}  # model name -> openai client
        # The lower model doubles as the classifier (cheap tie-breaker).
        self._classifier_llm = _OpenAIChat(
            model=lower_model, base_url=self.base_url, api_key=api_key
        )
        # When set, the next invoke() uses this tier regardless of routing.
        self._force_tier: RouteTier | None = None

    # -- tier forcing -----------------------------------------------------
    def force_tier(self, tier: RouteTier | None) -> None:
        """Force the next ``invoke`` to use the given tier (or auto if None).

        Useful for explicit control: e.g. intent detection -> LOWER, rebuttals
        -> HIGHER, while normal agent calls let the router decide.
        """
        self._force_tier = tier

    # -- LLMClient protocol ----------------------------------------------
    def invoke(self, messages: list[dict[str, str]]) -> str:
        task = _task_from_messages(messages)
        if self._force_tier is not None:
            tier = self._force_tier
            model = self.lower_model if tier is RouteTier.LOWER else self.higher_model
            score, signals = self.bridge.score(task)
            decision = RouteDecision(
                tier=tier,
                model=model,
                score=score,
                method=RouteMethod.OVERRIDE,
                reason=f"forced:{tier.value}",
                signals=signals,
            )
            self._force_tier = None
        else:
            decision = self.bridge.decide(
                task=task,
                lower_model_name=self.lower_model,
                higher_model_name=self.higher_model,
                classifier_llm=self._classifier_llm,
            )
        self.last_decision = decision
        if self.on_route:
            try:
                self.on_route(decision)
            except Exception:  # noqa: BLE001
                logger.exception("on_route callback raised")
        return self._invoke_model(decision.model, messages)

    # -- helpers ----------------------------------------------------------
    def _client_for(self, model: str):
        if model not in self._clients:
            self._clients[model] = _OpenAIChat(
                model=model, base_url=self.base_url, api_key=self.api_key
            )
        return self._clients[model]

    def _invoke_model(self, model: str, messages: list[dict[str, str]]) -> str:
        client = self._client_for(model)
        try:
            return client.invoke(messages)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Model %s invoke failed (%s); using fallback.", model, exc)
            return self.fallback.invoke(messages)

    def describe(self) -> dict[str, Any]:
        return {
            "lower_model": self.lower_model,
            "higher_model": self.higher_model,
            "base_url": self.base_url,
            "thresholds": {
                "lower": self.bridge.lower_threshold,
                "higher": self.bridge.higher_threshold,
                "classifier_band": self.bridge.classifier_band,
            },
        }


class _OpenAIChat:
    """Synchronous wrapper over the OpenAI-compatible /v1 endpoint (Ollama)."""

    def __init__(self, model: str, base_url: str, api_key: str) -> None:
        self.model = model
        from openai import OpenAI

        self._client = OpenAI(base_url=base_url, api_key=api_key)

    def invoke(self, messages: list[dict[str, str]]) -> str:
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=0.2,
        )
        return resp.choices[0].message.content or ""


def _task_from_messages(messages: list[dict[str, str]]) -> str:
    """Use the last user message as the routing signal; fall back to the
    concatenation of all non-system content."""
    for m in reversed(messages):
        if m.get("role") == "user" and m.get("content"):
            return m["content"]
    return " ".join(m.get("content", "") for m in messages if m.get("role") != "system")


def make_routed_llm() -> RoutedLLM:
    """Build a ``RoutedLLM`` from ``settings`` (defaults from .env)."""
    base = settings.lower_vllm_base_url or settings.higher_vllm_base_url
    return RoutedLLM(
        lower_model=settings.lower_model,
        higher_model=settings.higher_model,
        base_url=base,
        api_key=settings.vllm_api_key,
    )