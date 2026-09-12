"""Long-term memory: a simple vector store for retrieval over past interactions."""

from __future__ import annotations

import math
from collections.abc import Sequence

from a2a.memory.base import MemoryRecord
from a2a.memory.embeddings import Embedder, default_embedder


class LongTermMemory:
    """In-process vector store keyed by agent.

    Swappable for a real vector DB (Chroma, FAISS, pgvector) by replacing the
    storage and retrieval implementations while keeping the public interface.
    """

    def __init__(self, agent_id: str, embedder: Embedder | None = None) -> None:
        self.agent_id = agent_id
        self._embedder = embedder or default_embedder()
        self._records: list[MemoryRecord] = []

    def add(self, role: str, content: str, **metadata) -> MemoryRecord:
        embedding = self._embedder.embed(content)
        record = MemoryRecord(
            agent_id=self.agent_id,
            role=role,
            content=content,
            metadata=metadata,
            embedding=embedding,
        )
        self._records.append(record)
        return record

    def add_record(self, record: MemoryRecord) -> None:
        if record.embedding is None:
            record.embedding = self._embedder.embed(record.content)
        self._records.append(record)

    def search(self, query: str, k: int = 4) -> list[MemoryRecord]:
        if not self._records:
            return []
        q = self._embedder.embed(query)
        scored = [(self._cosine(q, r.embedding or []), r) for r in self._records]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:k]]

    def all(self) -> list[MemoryRecord]:
        return list(self._records)

    @staticmethod
    def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)