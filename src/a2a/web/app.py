"""FastAPI web app: chat interface + agent-to-agent communication panel.

Endpoints
---------
GET  /                 -> chat UI (HTML)
GET  /api/agents       -> list agents
GET  /api/router       -> router config + which models are wired
POST /api/route        -> score a message and return the routing decision
POST /api/chat         -> start a debate; returns SSE stream of events
GET  /api/health       -> health check

The SSE stream emits one ``data: {...}\n\n`` line per ``DebateEvent`` from
``DebateOrchestrator.stream``. The browser renders chat messages from
``agent_message``/``final`` events, renders the agent-to-agent panel from
``agent_comm`` events, and renders a model-routing indicator from ``route``
events.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from a2a.agents.base import LLMClient
from a2a.debate import detect_debate_intent

if TYPE_CHECKING:
    from fastapi import FastAPI


def build_app(llm: LLMClient | None = None) -> FastAPI:
    """Construct the FastAPI web app for the chat UI."""
    from pathlib import Path

    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, StreamingResponse
    from fastapi.staticfiles import StaticFiles

    from a2a.debate.orchestrator import DebateOrchestrator
    from a2a.router import make_routed_llm

    routed_llm: Any = llm or make_routed_llm()
    app = FastAPI(title="a2a chat", version="0.1.0")
    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    orchestrator = DebateOrchestrator(llm=routed_llm)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (static_dir / "index.html").read_text(encoding="utf-8")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/agents")
    def agents() -> list[dict[str, Any]]:
        return [
            {
                "name": "pro",
                "description": orchestrator.pro.card.description,
                "skills": orchestrator.pro.card.skills,
            },
            {
                "name": "cons",
                "description": orchestrator.cons.card.description,
                "skills": orchestrator.cons.card.skills,
            },
        ]

    @app.get("/api/router")
    def router_config() -> dict[str, Any]:
        if hasattr(routed_llm, "describe"):
            return routed_llm.describe()
        return {"enabled": False}

    @app.post("/api/route")
    def route(payload: dict[str, Any]) -> dict[str, Any]:
        msg = str(payload.get("message", ""))
        if not hasattr(routed_llm, "bridge"):
            return {"enabled": False, "message": "LLM is not routed."}
        score, signals = routed_llm.bridge.score(msg)
        decision = routed_llm.bridge.decide(
            task=msg,
            lower_model_name=routed_llm.lower_model,
            higher_model_name=routed_llm.higher_model,
            classifier_llm=None,
        )
        return {
            "message": msg,
            "score": score,
            "signals": signals,
            "decision": decision.to_dict(),
        }

    @app.post("/api/chat")
    def chat(payload: dict[str, Any]) -> StreamingResponse:
        message = str(payload.get("message", "")).strip()
        if not message:
            return StreamingResponse(
                iter([_sse({"type": "error", "content": "empty message"})]),
                media_type="text/event-stream",
            )

        def event_stream():
            yield _sse({
                "type": "user",
                "content": message,
            })
            for event in orchestrator.stream(message):
                yield _sse(event.to_dict())

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.post("/api/intent")
    def intent(payload: dict[str, Any]) -> dict[str, Any]:
        msg = str(payload.get("message", ""))
        return detect_debate_intent(msg, llm=routed_llm).to_dict()

    return app


def _sse(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def serve(host: str = "127.0.0.1", port: int = 8080, llm: LLMClient | None = None) -> None:
    """Run the chat web UI with uvicorn (blocking)."""
    import uvicorn

    app = build_app(llm=llm)
    uvicorn.run(app, host=host, port=port)