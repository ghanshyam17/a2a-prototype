"""Router integration: routes each LLM call to a small or large model.

Wraps ``agentic_router``'s hybrid router (heuristic scorer + LLM-as-judge
classifier) and adapts it to:

  * work synchronously over Ollama's OpenAI-compatible ``/v1`` endpoint
  * implement our ``LLMClient`` protocol so any ``BaseAgent`` can use it
  * emit ``RouteDecision`` events the UI can surface

Routing logic (mirrors ``agentic_router.router.Router``):
  * score <= lower_threshold          -> LOWER  (small / fast model)
  * score >= higher_threshold         -> HIGHER (large / capable model)
  * in between (or within `band` of a threshold) -> LLM classifier on the
    LOWER model; falls back to HIGHER on any error.
"""

from a2a.router.adapter import RouteDecision, RoutedLLM, make_routed_llm
from a2a.router.bridge import AgenticRouterBridge

__all__ = ["RouteDecision", "RoutedLLM", "make_routed_llm", "AgenticRouterBridge"]