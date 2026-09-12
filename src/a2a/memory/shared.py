"""Shared scratchpad: a coordination space all agents can read/write."""

from __future__ import annotations

import threading
from typing import Any

from a2a.memory.base import MemoryRecord


class SharedScratchpad:
    """A thread-safe shared board agents use to coordinate.

    The scratchpad holds:
      * ``notes``  - free-form messages tagged by writer
      * ``tasks``  - simple task queue with status
      * ``kv``     - shared key/value state
    """

    _instance: SharedScratchpad | None = None
    _lock = threading.Lock()

    def __new__(cls) -> SharedScratchpad:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        self._mutex = threading.Lock()
        self.notes: list[MemoryRecord] = []
        self.tasks: dict[str, dict[str, Any]] = {}
        self.kv: dict[str, Any] = {}

    # ---- notes -----------------------------------------------------------
    def post_note(self, agent_id: str, content: str, **metadata) -> MemoryRecord:
        rec = MemoryRecord(agent_id=agent_id, role="system", content=content, metadata=metadata)
        with self._mutex:
            self.notes.append(rec)
        return rec

    def recent_notes(self, n: int = 10) -> list[MemoryRecord]:
        with self._mutex:
            return list(self.notes[-n:])

    # ---- tasks -----------------------------------------------------------
    def create_task(self, task_id: str, description: str, assignee: str = "") -> None:
        with self._mutex:
            self.tasks[task_id] = {
                "description": description,
                "assignee": assignee,
                "status": "pending",
            }

    def update_task(self, task_id: str, status: str, assignee: str | None = None) -> None:
        with self._mutex:
            if task_id in self.tasks:
                self.tasks[task_id]["status"] = status
                if assignee is not None:
                    self.tasks[task_id]["assignee"] = assignee

    def list_tasks(self) -> list[dict[str, Any]]:
        with self._mutex:
            return [
                {"id": tid, **data} for tid, data in self.tasks.items() if data["status"] != "done"
            ]

    # ---- kv --------------------------------------------------------------
    def set(self, key: str, value: Any) -> None:
        with self._mutex:
            self.kv[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        with self._mutex:
            return self.kv.get(key, default)


def shared_scratchpad() -> SharedScratchpad:
    """Convenience accessor for the singleton scratchpad."""
    return SharedScratchpad()