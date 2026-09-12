"""Short-term memory: a bounded conversation buffer per agent."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable

from a2a.memory.base import MemoryRecord


class ShortTermMemory:
    """A rolling window of recent messages for the current conversation."""

    def __init__(self, agent_id: str, max_messages: int = 20) -> None:
        self.agent_id = agent_id
        self.max_messages = max_messages
        self._buffer: deque[MemoryRecord] = deque(maxlen=max_messages)

    def add(self, role: str, content: str, **metadata) -> MemoryRecord:
        record = MemoryRecord(agent_id=self.agent_id, role=role, content=content, metadata=metadata)
        self._buffer.append(record)
        return record

    def add_record(self, record: MemoryRecord) -> None:
        self._buffer.append(record)

    def all(self) -> list[MemoryRecord]:
        return list(self._buffer)

    def recent(self, n: int = 5) -> list[MemoryRecord]:
        return list(self._buffer)[-n:]

    def as_messages(self) -> list[dict[str, str]]:
        """Render the buffer as LangChain-style chat messages."""
        return [{"role": r.role, "content": r.content} for r in self._buffer]

    def extend(self, records: Iterable[MemoryRecord]) -> None:
        for r in records:
            self.add_record(r)

    def clear(self) -> None:
        self._buffer.clear()