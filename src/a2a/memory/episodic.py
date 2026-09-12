"""Episodic memory: time-stamped sequences of events an agent experienced."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from a2a.memory.base import MemoryRecord


class Episode:
    """A contiguous sequence of records that form one 'experience'."""

    def __init__(self, id: str, title: str, started_at: datetime | None = None) -> None:
        self.id = id
        self.title = title
        self.started_at = started_at or datetime.now(timezone.utc)
        self.ended_at: datetime | None = None
        self.records: list[MemoryRecord] = []

    def add(self, record: MemoryRecord) -> None:
        self.records.append(record)

    def close(self) -> None:
        self.ended_at = datetime.now(timezone.utc)

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "steps": len(self.records),
        }


class EpisodicMemory:
    """Stores episodes (e.g. completed tasks) for later reflection/replay."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self._episodes: list[Episode] = []
        self._current: Episode | None = None

    def start_episode(self, title: str) -> Episode:
        from uuid import uuid4

        ep = Episode(id=str(uuid4()), title=title)
        self._current = ep
        self._episodes.append(ep)
        return ep

    def record(self, role: str, content: str, **metadata) -> MemoryRecord:
        record = MemoryRecord(agent_id=self.agent_id, role=role, content=content, metadata=metadata)
        if self._current is None:
            self.start_episode("untitled")
        assert self._current is not None
        self._current.add(record)
        return record

    def end_episode(self) -> Episode | None:
        ep = self._current
        if ep is not None:
            ep.close()
            self._current = None
        return ep

    def all(self) -> list[Episode]:
        return list(self._episodes)

    def latest(self) -> Episode | None:
        return self._episodes[-1] if self._episodes else None