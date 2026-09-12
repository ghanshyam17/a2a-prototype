"""Semantic memory: durable facts / knowledge an agent has learned."""

from __future__ import annotations

from typing import Any

from a2a.memory.base import MemoryRecord


class SemanticMemory:
    """A simple key/value fact store keyed by subject.

    Each fact is stored as ``{subject: {predicate: value}}``. For the prototype
    this is in-memory; in production you'd back this with a knowledge graph
    (e.g. RDF, Neo4j) or a structured DB.
    """

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self._facts: dict[str, dict[str, Any]] = {}
        self._history: list[MemoryRecord] = []

    def add_fact(self, subject: str, predicate: str, value: Any, source: str = "self") -> None:
        bucket = self._facts.setdefault(subject, {})
        bucket[predicate] = value
        self._history.append(
            MemoryRecord(
                agent_id=self.agent_id,
                role="system",
                content=f"{subject} {predicate} = {value!r} (from {source})",
                metadata={"subject": subject, "predicate": predicate, "source": source},
            )
        )

    def get(self, subject: str, predicate: str, default: Any = None) -> Any:
        return self._facts.get(subject, {}).get(predicate, default)

    def about(self, subject: str) -> dict[str, Any]:
        return dict(self._facts.get(subject, {}))

    def search(self, term: str) -> list[MemoryRecord]:
        term_l = term.lower()
        return [r for r in self._history if term_l in r.content.lower()]

    def all_facts(self) -> dict[str, dict[str, Any]]:
        return {s: dict(p) for s, p in self._facts.items()}