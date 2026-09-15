"""a2a_foundry.py — Foundry SDK + Azure Functions adapter for the a2a project.

Exposes the A2A multi-agent orchestration (LangGraph supervisor + pro/cons
debate) to Azure AI Foundry:

  - handle_foundry_request(payload) → hosted-agent entrypoint
    {"message": topic} → {"reply": debate transcript / agent answer, "agents": [...]}
  - Also bridges Foundry's native A2A protocol: exposes AgentCard discovery
    at /.well-known/agent.json matching the in-repo protocol client.

Runs the StubLLM offline fallback by default (no model cost at idle); set
A2A_LLM_BACKEND=ollama|azure to enable live LLM routing.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

_pkg_parents = [
    Path(__file__).resolve().parent,            # wwwroot/ (same as azure_functions/ when deployed)
    Path(__file__).resolve().parent / "src",    # src/ is inside the deployed wwwroot
]
for _p in _pkg_parents:
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

_SRC = Path(__file__).resolve().parent / "src"
if _SRC.exists() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


# ── Lazy engine import (keeps cold start fast) ────────────────────────

def _get_orchestrator():
    from a2a.agents.intent import route  # noqa: F401  (existence check)
    from a2a.orchestrator import Orchestrator
    return Orchestrator()


def _get_agents():
    from a2a.agents.researcher import ResearcherAgent
    from a2a.agents.writer import WriterAgent
    from a2a.agents.coder import CoderAgent
    from a2a.agents.pro import ProAgent
    from a2a.agents.cons import ConsAgent
    return [ResearcherAgent, WriterAgent, CoderAgent, ProAgent, ConsAgent]


# ── Core operations ───────────────────────────────────────────────────

def debate(topic: str, rounds: int = 2) -> Dict[str, Any]:
    """Run a pro/cons debate on a topic via DebateOrchestrator."""
    try:
        from a2a.debate.orchestrator import DebateOrchestrator
        orch = DebateOrchestrator()
        result = orch.run(topic)
        return {
            "ok": True,
            "mode": "debate",
            "topic": topic,
            "transcript": result,
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "topic": topic}


def ask(agent_name: str, message: str) -> Dict[str, Any]:
    """Direct message to one registered agent (auto-binds the default LLM)."""
    try:
        from a2a.agents.llm import make_llm
        agents = {a.__name__.replace("Agent", "").lower(): a for a in _get_agents()}
        cls = agents.get(agent_name.lower())
        if cls is None:
            return {"ok": False, "error": f"unknown agent '{agent_name}'", "available": list(agents)}
        agent = cls(llm=make_llm())
        reply = agent.run(message)
        return {"ok": True, "mode": "direct", "agent": agent_name, "reply": reply}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def agent_cards() -> List[Dict[str, Any]]:
    """A2A AgentCard discovery for all registered agents."""
    try:
        cards = []
        for cls in _get_agents():
            try:
                a = cls()
                cards.append(a.card.to_dict())
            except Exception:
                continue
        return cards
    except Exception:
        return []


# ── Foundry hosted-agent entrypoint ───────────────────────────────────

def handle_foundry_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Foundry Invocations entrypoint for the a2a multi-agent system."""
    msg = str(payload.get("message") or payload.get("input") or "").strip()
    if not msg:
        return {"reply": "Envoyez un sujet de débat ou un agent cible (ex: 'debate: le subjonctif').", "ok": False}

    if msg.lower().startswith(("debate:", "débat:", "debate ")):
        topic = msg.split(":", 1)[-1].strip() or msg.split(" ", 1)[-1]
        res = debate(topic)
        return {"ok": res["ok"], "reply": f"⚖️ Débat sur « {topic} » — voir transcript.", **res}

    if ":" in msg and msg.split(":", 1)[0].lower() in ("researcher", "writer", "coder", "pro", "cons"):
        name, rest = msg.split(":", 1)
        return ask(name.strip(), rest.strip())

    # Default: run the debate orchestrator as a router
    res = debate(msg)
    return {"ok": res.get("ok", False), "reply": res.get("transcript") or res.get("error", ""), "mode": "debate"}