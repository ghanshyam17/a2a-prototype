"""Tests that the debate orchestrator emits route events with a RoutedLLM.

These avoid live model calls by stubbing the model invocation layer while still
exercising the real heuristic router and route-event plumbing.
"""

from __future__ import annotations

from a2a.agents.cons import ConsAgent
from a2a.agents.pro import ProAgent
from a2a.debate.orchestrator import DebateOrchestrator
from a2a.memory import AgentMemory
from a2a.memory.embeddings import HashingEmbedder
from a2a.router.adapter import RoutedLLM
from a2a.router.bridge import AgenticRouterBridge


class _StubInvoke:
    """Stand-in for _OpenAIChat that returns canned content per model."""

    def __init__(self, model: str, base_url: str, api_key: str) -> None:
        self.model = model

    def invoke(self, messages: list[dict[str, str]]) -> str:
        return f"[{self.model}] " + messages[-1]["content"][:60]


def _stub_memory(agent_id: str) -> AgentMemory:
    mem = AgentMemory(agent_id)
    mem.long_term._embedder = HashingEmbedder()
    return mem


def _make_stub_routed_llm() -> RoutedLLM:
    llm = RoutedLLM(
        lower_model="small",
        higher_model="big",
        base_url="http://localhost/v1",
        api_key="EMPTY",
        bridge=AgenticRouterBridge(0.15, 0.45, 0.05),
    )
    llm._classifier_llm = _StubInvoke("small", "", "")  # type: ignore[attr-defined]
    llm._clients = {"small": _StubInvoke("small", "", ""), "big": _StubInvoke("big", "", "")}
    return llm


def _make_orchestrator() -> DebateOrchestrator:
    llm = _make_stub_routed_llm()
    return DebateOrchestrator(
        pro=ProAgent(llm=llm, memory=_stub_memory("pro")),
        cons=ConsAgent(llm=llm, memory=_stub_memory("cons")),
        llm=llm,
    )


def test_debate_emits_route_events():
    orch = _make_orchestrator()
    events = list(orch.stream("pros and cons of remote work"))
    routes = [e for e in events if e.type == "route"]
    assert len(routes) >= 3
    tiers = {e.metadata["tier"] for e in routes}
    assert "lower" in tiers or "higher" in tiers


def test_intent_detection_uses_lower_model():
    orch = _make_orchestrator()
    events = list(orch.stream("pros and cons of remote work"))
    intent_route = next(e for e in events if e.type == "route" and e.agent == "intent")
    assert intent_route.metadata["tier"] == "lower"
    assert intent_route.metadata["method"] == "override"


def test_rebuttals_force_higher():
    orch = _make_orchestrator()
    events = list(orch.stream("pros and cons of remote work"))
    comm_routes = [e for e in events if e.type == "route" and e.agent in {"pro", "cons"}]
    higher_overrides = [
        e for e in comm_routes
        if e.metadata.get("tier") == "higher" and e.metadata.get("method") == "override"
    ]
    assert len(higher_overrides) >= 2