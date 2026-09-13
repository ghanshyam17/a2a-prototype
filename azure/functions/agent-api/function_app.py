"""Azure Functions HTTP surface for the a2a debate system.

Routes (FUNCTION auth level):

- ``GET  /api/agent`` -> capability card (actions, agents, router config).
- ``POST /api/agent`` ``{"action": "debate", "message": "<topic>"}``
  -> full event list from the real DebateOrchestrator.
- ``POST /api/agent`` ``{"action": "route", "message": "..."}``
  -> heuristic score + tier decision from the real AgenticRouterBridge.

Import layout: the deploy zip (assembled by azure/scripts/deploy-functions.sh)
bundles the repo's ``src/a2a`` under ``_vendor/a2a``; from a repo checkout the
live tree under ``src/`` is used. ``MODEL_PROVIDER=stub`` keeps the deployed
API fully LLM-bill-free (deterministic stub orchestrator).
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import azure.functions as func


def _bootstrap_imports() -> None:
    here = Path(__file__).resolve().parent

    for base in (here, here.parent):
        vendor = base / "_vendor"
        if (vendor / "a2a").is_dir() and str(vendor) not in sys.path:
            sys.path.insert(0, str(vendor))

    for cand in (here, *here.parents):
        if (cand / "src" / "a2a").is_dir():
            src = cand / "src"
            if str(src) not in sys.path:
                sys.path.insert(0, str(src))
            break


_bootstrap_imports()

from a2a.agents.llm import make_llm  # noqa: E402
from a2a.config import settings  # noqa: E402
from a2a.debate.orchestrator import DebateOrchestrator  # noqa: E402
from a2a.router import AgenticRouterBridge  # noqa: E402

logger = logging.getLogger("agent-api")

app = func.FunctionApp()

_ORCH: DebateOrchestrator | None = None
_BRIDGE: AgenticRouterBridge | None = None


def _orchestrator() -> DebateOrchestrator:
    global _ORCH
    if _ORCH is None:
        _ORCH = DebateOrchestrator(llm=make_llm())
    return _ORCH


def _bridge() -> AgenticRouterBridge:
    global _BRIDGE
    if _BRIDGE is None:
        _BRIDGE = AgenticRouterBridge(
            lower_threshold=settings.router_lower_threshold,
            higher_threshold=settings.router_higher_threshold,
            classifier_band=settings.router_classifier_band,
        )
    return _BRIDGE


def _json(payload: dict, status: int = 200) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(payload, default=str), mimetype="application/json", status_code=status
    )


@app.function_name(name="AgentApi")
@app.route(route="agent", methods=["POST", "GET"], auth_level=func.AuthLevel.FUNCTION)
def agent_api(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "GET":
        return _json(
            {
                "service": "a2a-debate",
                "actions": ["debate", "route"],
                "agents": ["pro", "cons"],
                "model_provider": settings.model_provider,
                "router": {
                    "lower_threshold": settings.router_lower_threshold,
                    "higher_threshold": settings.router_higher_threshold,
                },
            }
        )

    try:
        body = req.get_json()
    except ValueError:
        return _json({"error": "invalid JSON body"}, 400)

    action = (body.get("action") or "debate").lower()
    message = body.get("message") or ""
    if not message:
        return _json({"error": "message is required"}, 400)

    if action == "route":
        try:
            b = _bridge()
            score, signals = b.score(message)
            decision = b.decide(
                message,
                lower_model_name=settings.lower_model,
                higher_model_name=settings.higher_model,
                classifier_llm=None,
            )
            return _json(
                {"action": "route", "score": score, "signals": signals, "decision": decision.to_dict()}
            )
        except Exception as exc:  # noqa: BLE001 - structured error, not a bare 500
            logger.exception("route action failed")
            return _json({"action": "route", "error": f"{type(exc).__name__}: {exc}"}, 500)

    if action != "debate":
        return _json({"error": f"unknown action '{action}'"}, 400)

    try:
        events = [e.to_dict() for e in _orchestrator().stream(message)]
        return _json({"action": "debate", "events": events})
    except Exception as exc:  # noqa: BLE001
        logger.exception("debate action failed")
        return _json({"action": "debate", "error": f"{type(exc).__name__}: {exc}"}, 500)
