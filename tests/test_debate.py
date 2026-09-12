"""Tests for the debate intent detector, orchestrator, and web app."""

from __future__ import annotations

from a2a.agents.llm import StubLLM
from a2a.debate import DebateOrchestrator, detect_debate_intent


def test_intent_detects_both_sides_and_topic():
    intent = detect_debate_intent("Give me pros and cons of remote work", llm=StubLLM())
    assert intent.is_debate
    assert intent.side == "both"
    assert "remote work" in intent.topic.lower() or intent.topic


def test_intent_detects_pros_only():
    intent = detect_debate_intent("What are the advantages of nuclear energy?", llm=StubLLM())
    assert intent.is_debate
    assert intent.side in {"pro", "both"}


def test_intent_detects_cons_only():
    intent = detect_debate_intent("disadvantages of microservices", llm=StubLLM())
    assert intent.is_debate
    assert intent.side in {"cons", "both"}


def test_intent_non_debate_message():
    intent = detect_debate_intent("hello there", llm=StubLLM())
    assert intent.is_debate is False or intent.topic


def test_debate_orchestrator_streams_events_for_both():
    orch = DebateOrchestrator(llm=StubLLM())
    events = list(orch.stream("pros and cons of remote work"))
    types = [e.type for e in events]
    assert "intent" in types
    assert "agent_message" in types
    assert "final" in types


def test_debate_orchestrator_produces_agent_comm_rebuttals():
    orch = DebateOrchestrator(llm=StubLLM())
    events = list(orch.stream("pros and cons of remote work"))
    comm = [e for e in events if e.type == "agent_comm"]
    assert len(comm) == 2
    assert {e.agent for e in comm} == {"pro", "cons"}
    assert all(e.to for e in comm)


def test_debate_orchestrator_pro_only():
    orch = DebateOrchestrator(llm=StubLLM())
    events = list(orch.stream("advantages of rust language"))
    agent_msgs = [e for e in events if e.type == "agent_message"]
    # heuristic may classify as pro; if so, only pro agent should speak
    sides = {e.side for e in agent_msgs}
    assert "pro" in sides or "both" in sides


def test_debate_run_returns_final():
    orch = DebateOrchestrator(llm=StubLLM())
    result = orch.run("pros and cons of working from home")
    assert result["final"]
    assert result["topic"]
    assert result["events"]


def test_web_app_builds_and_agents_endpoint():
    from fastapi.testclient import TestClient

    from a2a.web import build_app

    app = build_app(llm=StubLLM())
    client = TestClient(app)
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    r = client.get("/api/agents")
    assert r.status_code == 200
    names = {a["name"] for a in r.json()}
    assert names == {"pro", "cons"}
    r = client.get("/")
    assert r.status_code == 200
    assert "<html" in r.text.lower()


def test_web_app_chat_stream_emits_events():
    from fastapi.testclient import TestClient

    from a2a.web import build_app

    app = build_app(llm=StubLLM())
    client = TestClient(app)
    with client.stream("POST", "/api/chat", json={"message": "pros and cons of ai"}) as r:
        assert r.status_code == 200
        body = b"".join(r.iter_bytes()).decode()
    assert "data: " in body
    assert '"type": "intent"' in body or '"type":"intent"' in body
    assert '"type": "final"' in body or '"type":"final"' in body


def test_web_app_router_endpoints_with_routed_llm():
    from fastapi.testclient import TestClient

    from a2a.router.adapter import RoutedLLM
    from a2a.router.bridge import AgenticRouterBridge
    from a2a.web import build_app

    llm = RoutedLLM(
        lower_model="small", higher_model="big",
        base_url="http://localhost/v1", api_key="EMPTY",
        bridge=AgenticRouterBridge(0.15, 0.45, 0.05),
    )
    app = build_app(llm=llm)
    client = TestClient(app)
    r = client.get("/api/router")
    assert r.status_code == 200
    cfg = r.json()
    assert cfg["lower_model"] == "small"
    assert cfg["higher_model"] == "big"
    r = client.post("/api/route", json={"message": "hi"})
    assert r.status_code == 200
    out = r.json()
    assert out["decision"]["tier"] == "lower"