"""Bridge to the ``agentic_router`` package's heuristic + classifier.

We reuse ``agentic_router.router.heuristic.score_task`` directly (it's a pure
function with no I/O). For the LLM-as-judge classifier we re-implement the
prompt/parse logic synchronously against our Ollama-backed client, so we don't
need AsyncOpenAI or a running vLLM server.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

from a2a.router.models import RouteDecision, RouteMethod, RouteTier

if TYPE_CHECKING:
    from agentic_router.router.heuristic import score_task as _score_task  # noqa: F401

logger = logging.getLogger(__name__)


_CLASSIFIER_SYSTEM = """You are a routing classifier. Decide whether a task needs a SMALL/FAST model
or a LARGE/CAPABLE model.

Reply with a JSON object ONLY, no prose:
{"tier": "lower" | "higher", "reason": "<= 12 words"}

Rules of thumb:
- lower: greetings, simple Q&A, summaries, formatting, short translations, list/count tasks.
- higher: multi-step reasoning, coding, debugging, math/proofs, planning, tool use, long context.
When unsure, choose "higher"."""

_CLASSIFIER_RE = re.compile(r'\{[^{}]*"tier"[^{}]*\}', re.DOTALL)


class AgenticRouterBridge:
    """Synchronous adapter around agentic_router's heuristic + classifier."""

    def __init__(
        self,
        lower_threshold: float,
        higher_threshold: float,
        classifier_band: float,
    ) -> None:
        self.lower_threshold = lower_threshold
        self.higher_threshold = higher_threshold
        self.classifier_band = classifier_band

    # -- heuristic --------------------------------------------------------
    def score(self, task: str) -> tuple[float, dict[str, float]]:
        from agentic_router.router.heuristic import score_task

        return score_task(task)

    def needs_classifier(self, score: float) -> bool:
        if self.lower_threshold < score < self.higher_threshold:
            return True
        near_lower = abs(score - self.lower_threshold) < self.classifier_band
        near_higher = abs(score - self.higher_threshold) < self.classifier_band
        return near_lower or near_higher

    # -- decision ---------------------------------------------------------
    def decide(
        self,
        task: str,
        lower_model_name: str,
        higher_model_name: str,
        classifier_llm=None,
    ) -> RouteDecision:
        """Return a routing decision. ``classifier_llm`` (optional) is any
        object with ``invoke(messages: list[dict]) -> str`` used to break
        ties in the uncertain band; if absent the heuristic decision stands.
        """
        score, signals = self.score(task)

        if not self.needs_classifier(score):
            if score <= self.lower_threshold:
                return RouteDecision(
                    tier=RouteTier.LOWER,
                    model=lower_model_name,
                    score=score,
                    method=RouteMethod.HEURISTIC,
                    reason="below_lower_threshold",
                    signals=signals,
                )
            return RouteDecision(
                tier=RouteTier.HIGHER,
                model=higher_model_name,
                score=score,
                method=RouteMethod.HEURISTIC,
                reason="above_higher_threshold",
                signals=signals,
            )

        # Ambiguous -> ask the classifier (runs on the small model).
        tier, reason = self._classify(task, classifier_llm)
        model = lower_model_name if tier is RouteTier.LOWER else higher_model_name
        return RouteDecision(
            tier=tier,
            model=model,
            score=score,
            method=RouteMethod.CLASSIFIER,
            reason=reason,
            signals=signals,
        )

    def _classify(self, task: str, classifier_llm=None) -> tuple[RouteTier, str]:
        if classifier_llm is None:
            # No classifier available: default to higher (safer).
            return RouteTier.HIGHER, "classifier_unavailable"
        try:
            content = classifier_llm.invoke([
                {"role": "system", "content": _CLASSIFIER_SYSTEM},
                {"role": "user", "content": task[:2000]},
            ])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Classifier call failed (%s); defaulting to higher.", exc)
            return RouteTier.HIGHER, f"classifier_error: {exc}"

        m = _CLASSIFIER_RE.search(content or "")
        if not m:
            if re.search(r"\bhigher\b", content or "", re.IGNORECASE):
                return RouteTier.HIGHER, "classifier_keyword"
            if re.search(r"\blower\b", content or "", re.IGNORECASE):
                return RouteTier.LOWER, "classifier_keyword"
            return RouteTier.HIGHER, "classifier_unparseable"

        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            return RouteTier.HIGHER, "classifier_unparseable"

        tier = str(obj.get("tier", "higher")).lower()
        reason = str(obj.get("reason", ""))[:120]
        if tier not in ("lower", "higher"):
            tier = "higher"
        return (RouteTier.LOWER if tier == "lower" else RouteTier.HIGHER,
                reason or "classifier_decision")