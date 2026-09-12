"""HTTP client for the A2A protocol."""

from __future__ import annotations

import logging
from typing import Any

from a2a.a2a_protocol.schemas import A2AMessage, A2ATask

logger = logging.getLogger(__name__)


class A2AClient:
    """Thin async/sync client for A2A HTTP servers."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        import httpx

        self._client = httpx.Client(timeout=30.0)

    def agent_card(self) -> dict[str, Any]:
        r = self._client.get(f"{self.base_url}/.well-known/agent.json")
        r.raise_for_status()
        return r.json()

    def list_agents(self) -> list[dict[str, Any]]:
        r = self._client.get(f"{self.base_url}/agents")
        r.raise_for_status()
        return r.json()

    def send_task(self, content: str, sender: str | None = None) -> A2ATask:
        msg = A2AMessage(content=content, sender=sender)
        r = self._client.post(f"{self.base_url}/tasks", json=msg.model_dump())
        r.raise_for_status()
        return A2ATask.model_validate(r.json())

    def get_task(self, task_id: str) -> A2ATask:
        r = self._client.get(f"{self.base_url}/tasks/{task_id}")
        r.raise_for_status()
        return A2ATask.model_validate(r.json())

    def close(self) -> None:
        self._client.close()