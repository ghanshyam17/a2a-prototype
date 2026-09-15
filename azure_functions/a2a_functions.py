"""Azure Functions for a2a — HTTP triggers over the multi-agent orchestration.

  POST /api/a2a/debate  {topic} -> pro/cons debate via DebateOrchestrator
  POST /api/a2a/ask     {agent, message} -> direct agent invocation
  GET  /api/a2a/cards   -> A2A AgentCard discovery (native protocol)
  GET  /api/a2a/health  -> agent roster + Foundry wiring
  POST /api/foundry/invoke {message} -> Foundry hosted-agent entrypoint
"""

import json
import logging
import os
import sys
from pathlib import Path

import azure.functions as func

_fn_dir = Path(__file__).resolve().parent
for p in (str(_fn_dir), str(_fn_dir / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from a2a_foundry import debate, ask, agent_cards, handle_foundry_request
except ImportError:
    from azure_functions.a2a_foundry import debate, ask, agent_cards, handle_foundry_request

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)
logger = logging.getLogger("a2a-functions")


def _ok(data, status=200):
    return func.HttpResponse(
        json.dumps(data, ensure_ascii=False, default=str),
        status_code=status,
        mimetype="application/json",
    )


def _err(msg, status=500):
    return _ok({"error": msg}, status)


def _body(req):
    try:
        return req.get_json()
    except Exception:
        return {}


@app.route(route="a2a/debate", methods=["POST"])
def a2a_debate(req: func.HttpRequest):
    topic = (_body(req).get("topic") or "").strip()
    if not topic:
        return _err("topic is required", 400)
    try:
        return _ok(debate(topic))
    except Exception as e:
        return _err(f"{type(e).__name__}: {str(e)[:200]}", 500)


@app.route(route="a2a/ask", methods=["POST"])
def a2a_ask(req: func.HttpRequest):
    b = _body(req)
    agent = (b.get("agent") or "").strip()
    message = (b.get("message") or "").strip()
    if not agent or not message:
        return _err("agent and message are required", 400)
    try:
        return _ok(ask(agent, message))
    except Exception as e:
        return _err(f"{type(e).__name__}: {str(e)[:200]}", 500)


@app.route(route="a2a/cards", methods=["GET"])
def a2a_cards(req: func.HttpRequest):
    try:
        return _ok({"cards": agent_cards()})
    except Exception as e:
        return _err(f"{type(e).__name__}: {str(e)[:200]}", 500)


@app.route(route="foundry/invoke", methods=["POST"])
def foundry_invoke(req: func.HttpRequest):
    payload = _body(req)
    if not payload:
        return _err("JSON body required", 400)
    try:
        return _ok(handle_foundry_request(payload))
    except Exception as e:
        return _err(f"{type(e).__name__}: {str(e)[:200]}", 500)


@app.route(route="foundry/health", methods=["GET"])
def foundry_health(req: func.HttpRequest):
    endpoint = os.environ.get("AZURE_FOUNDRY_PROJECT_ENDPOINT", "")
    agent = os.environ.get("AZURE_FOUNDRY_AGENT_ID", "a2a-orchestrator")
    detail = {"endpoint": endpoint or "(not set)", "agent": agent, "wired": bool(endpoint)}
    if endpoint:
        try:
            from azure.identity import DefaultAzureCredential
            from azure.ai.projects import AIProjectClient

            client = AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())
            list_op = getattr(client.agents, "list", None) or getattr(client.agents, "list_agents", None)
            agents_list = list_op() if callable(list_op) else []
            names = [getattr(a, "name", str(a)) for a in getattr(agents_list, "data", agents_list)]
            detail["agents"] = names
            detail["agent_present"] = agent in names
        except Exception as e:
            detail["sdk_error"] = str(e)[:200]
    return _ok({"status": "ok", "service": "a2a-functions", **detail})
