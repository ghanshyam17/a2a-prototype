"""Base agent definition shared by all agents."""

from __future__ import annotations

import logging
from typing import Any, Protocol

from a2a.memory import AgentMemory

logger = logging.getLogger(__name__)


class LLMClient(Protocol):
    """Minimal LLM interface used by agents."""

    def invoke(self, messages: list[dict[str, str]]) -> str: ...


class AgentCard:
    """Public description of an agent, used both for orchestration and A2A HTTP."""

    def __init__(
        self,
        name: str,
        description: str,
        skills: list[str],
        url: str | None = None,
        version: str = "0.1.0",
    ) -> None:
        self.name = name
        self.description = description
        self.skills = skills
        self.url = url
        self.version = version

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "skills": self.skills,
            "url": self.url,
            "version": self.version,
        }


class BaseAgent:
    """Common agent behaviour: identity, memory, LLM access, message handling."""

    def __init__(
        self,
        name: str,
        description: str,
        skills: list[str],
        llm: LLMClient | None = None,
        memory: AgentMemory | None = None,
    ) -> None:
        self.card = AgentCard(name=name, description=description, skills=skills)
        self.memory = memory or AgentMemory(agent_id=name)
        self._llm = llm
        self.name = name

    # -- LLM --------------------------------------------------------------
    def set_llm(self, llm: LLMClient) -> None:
        self._llm = llm

    @property
    def llm(self) -> LLMClient:
        if self._llm is None:
            raise RuntimeError(f"Agent {self.name} has no LLM bound.")
        return self._llm

    # -- Prompt construction ---------------------------------------------
    def system_prompt(self) -> str:
        return (
            f"You are {self.name}, an AI agent.\n"
            f"Description: {self.card.description}\n"
            f"Skills: {', '.join(self.card.skills)}\n"
            "Use the provided memory context when answering. "
            "Be concise and useful to other agents that may consume your output."
        )

    def build_messages(self, user_input: str, query: str | None = None) -> list[dict[str, str]]:
        context = self.memory.context_for_llm(query=user_input)
        return [
            {"role": "system", "content": self.system_prompt()},
            {"role": "system", "content": f"Memory context:\n{context}"},
            {"role": "user", "content": user_input},
        ]

    # -- Execution --------------------------------------------------------
    def run(self, user_input: str, **metadata) -> str:
        """Process an input and produce a textual response."""
        self.memory.start_episode(title=user_input[:80])
        self.memory.remember("user", user_input, **metadata)
        messages = self.build_messages(user_input)
        response = self.llm.invoke(messages)
        self.memory.remember("assistant", response, **metadata)
        self.memory.end_episode()
        self.memory.shared.post_note(self.name, f"handled: {user_input[:120]}")
        return response

    # -- Communication ----------------------------------------------------
    def send_to(self, other: BaseAgent, message: str) -> str:
        """Direct in-process agent-to-agent message."""
        self.memory.shared.post_note(
            self.name, f"-> {other.name}: {message}", to=other.name
        )
        return other.run(message, sender=self.name)

    def describe(self) -> dict[str, Any]:
        return self.card.to_dict()