"""AgentMemory: aggregates all memory subsystems for one agent."""

from __future__ import annotations

from typing import Any

from a2a.memory.base import MemoryRecord
from a2a.memory.episodic import Episode, EpisodicMemory
from a2a.memory.long_term import LongTermMemory
from a2a.memory.semantic import SemanticMemory
from a2a.memory.shared import SharedScratchpad, shared_scratchpad
from a2a.memory.short_term import ShortTermMemory


class AgentMemory:
    """Facade combining short-term, long-term, episodic, semantic and shared memory."""

    def __init__(
        self,
        agent_id: str,
        short_term_size: int = 20,
        shared: SharedScratchpad | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.short_term = ShortTermMemory(agent_id, max_messages=short_term_size)
        self.long_term = LongTermMemory(agent_id)
        self.episodic = EpisodicMemory(agent_id)
        self.semantic = SemanticMemory(agent_id)
        self.shared = shared or shared_scratchpad()

    # -- convenience -------------------------------------------------------
    def remember(self, role: str, content: str, **metadata) -> MemoryRecord:
        """Record a message in short-term, episodic and long-term memory."""
        st = self.short_term.add(role, content, **metadata)
        self.episodic.record(role, content, **metadata)
        self.long_term.add_record(MemoryRecord(
            agent_id=self.agent_id,
            role=role,
            content=content,
            metadata=metadata,
            embedding=None,
        ))
        return st

    def start_episode(self, title: str) -> Episode:
        return self.episodic.start_episode(title)

    def end_episode(self) -> Episode | None:
        return self.episodic.end_episode()

    def learn_fact(self, subject: str, predicate: str, value: Any, source: str = "self") -> None:
        self.semantic.add_fact(subject, predicate, value, source=source)

    def recall(self, query: str, k: int = 4) -> list[MemoryRecord]:
        return self.long_term.search(query, k=k)

    def context_for_llm(self, query: str | None = None) -> str:
        """Build a compact textual context bundle for prompt construction."""
        parts: list[str] = []
        recent = self.short_term.as_messages()
        if recent:
            parts.append("Recent conversation:")
            for m in recent[-6:]:
                parts.append(f"  {m['role']}: {m['content']}")
        if query:
            hits = self.recall(query, k=3)
            if hits:
                parts.append("Relevant long-term memories:")
                for h in hits:
                    parts.append(f"  - {h.content}")
        facts = self.semantic.all_facts()
        if facts:
            parts.append("Known facts:")
            for subj, preds in facts.items():
                preds_str = ", ".join(f"{k}={v}" for k, v in preds.items())
                parts.append(f"  - {subj}: {preds_str}")
        notes = self.shared.recent_notes(n=3)
        if notes:
            parts.append("Shared board (recent):")
            for n in notes:
                parts.append(f"  - [{n.agent_id}] {n.content}")
        return "\n".join(parts) if parts else "(no prior context)"