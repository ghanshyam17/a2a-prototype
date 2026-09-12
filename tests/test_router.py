"""Tests for the router integration (no live model calls)."""

from __future__ import annotations

from a2a.router.bridge import AgenticRouterBridge
from a2a.router.models import RouteMethod, RouteTier


def test_heuristic_scores_simple_task_low():
    bridge = AgenticRouterBridge(0.15, 0.45, 0.05)
    score, signals = bridge.score("hi")
    assert score <= 0.15
    assert round(score, 3) == signals["total"]


def test_heuristic_scores_complex_task_high():
    bridge = AgenticRouterBridge(0.15, 0.45, 0.05)
    score, _ = bridge.score("Debug this stack trace and refactor the algorithm step by step")
    assert score > 0.15


def test_bridge_decides_lower_for_simple():
    bridge = AgenticRouterBridge(0.15, 0.45, 0.05)
    decision = bridge.decide("hi", "small-model", "big-model", classifier_llm=None)
    assert decision.tier is RouteTier.LOWER
    assert decision.model == "small-model"
    assert decision.method is RouteMethod.HEURISTIC


def test_bridge_decides_higher_for_complex():
    bridge = AgenticRouterBridge(0.15, 0.45, 0.05)
    decision = bridge.decide(
        "Debug this stack trace, refactor the algorithm, and optimize it step by step.",
        "small-model", "big-model", classifier_llm=None,
    )
    assert decision.tier is RouteTier.HIGHER
    assert decision.model == "big-model"


def test_bridge_defaults_to_higher_without_classifier_in_band():
    # score within `band` of a threshold -> needs classifier; with no
    # classifier available it defaults to HIGHER (safer).
    bridge = AgenticRouterBridge(0.15, 0.45, 0.05)
    decision = bridge.decide(
        "plan the migration strategy", "small-model", "big-model", classifier_llm=None
    )
    assert decision.tier is RouteTier.HIGHER
    assert decision.method is RouteMethod.CLASSIFIER
    assert decision.reason == "classifier_unavailable"


def test_route_decision_to_dict_serialises_enums():
    from a2a.router.models import RouteDecision

    d = RouteDecision(
        tier=RouteTier.LOWER, model="m", score=0.1,
        method=RouteMethod.HEURISTIC, reason="r",
    )
    out = d.to_dict()
    assert out["tier"] == "lower"
    assert out["method"] == "heuristic"