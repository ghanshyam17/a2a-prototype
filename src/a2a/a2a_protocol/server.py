"""FastAPI app that wraps a BaseAgent in the A2A HTTP protocol."""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

from a2a.a2a_protocol.schemas import A2AMessage, A2ATask
from a2a.agents.base import BaseAgent

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


def build_app(agent: BaseAgent, peers: list[dict[str, Any]] | None = None) -> FastAPI:
    """Construct a FastAPI app exposing ``agent`` over the A2A protocol."""
    from fastapi import FastAPI, HTTPException

    app = FastAPI(title=f"a2a-{agent.name}", version="0.1.0")
    _tasks: dict[str, A2ATask] = {}
    _tasks_lock = threading.Lock()

    card = agent.card.to_dict()
    card["url"] = card.get("url") or f"http://localhost:{_port_of(agent)}/"

    @app.get("/.well-known/agent.json")
    def agent_card() -> dict[str, Any]:
        return card

    @app.get("/agents")
    def list_agents() -> list[dict[str, Any]]:
        return [{"name": agent.name, **agent.card.to_dict()}] + (peers or [])

    @app.post("/tasks", response_model=A2ATask)
    def create_task(message: A2AMessage) -> A2ATask:
        task = A2ATask(message=message, status="working", assigned_to=agent.name)
        with _tasks_lock:
            _tasks[task.id] = task
        try:
            result = agent.run(message.content, sender=message.sender)
            task.result = result
            task.status = "completed"
        except Exception as exc:  # noqa: BLE001
            logger.exception("Task %s failed", task.id)
            task.status = "failed"
            task.error = str(exc)
        with _tasks_lock:
            _tasks[task.id] = task
        return task

    @app.get("/tasks/{task_id}", response_model=A2ATask)
    def get_task(task_id: str) -> A2ATask:
        with _tasks_lock:
            if task_id not in _tasks:
                raise HTTPException(status_code=404, detail="task not found")
            return _tasks[task_id]

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "agent": agent.name}

    return app


def _port_of(agent: BaseAgent) -> int:
    from a2a.config import settings

    base = settings.a2a_port_base
    names = ["researcher", "writer", "coder"]
    try:
        return base + names.index(agent.name)
    except ValueError:
        return base + len(names)


def serve_agent(agent: BaseAgent, host: str | None = None, port: int | None = None) -> None:
    """Run the A2A HTTP server for ``agent`` with uvicorn (blocking)."""
    import uvicorn

    from a2a.config import settings

    host = host or settings.a2a_host
    port = port or _port_of(agent)
    agent.card.url = f"http://{host}:{port}/"
    app = build_app(agent)
    uvicorn.run(app, host=host, port=port)