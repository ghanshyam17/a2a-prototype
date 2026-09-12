"""Researcher agent: gathers and summarizes information."""

from __future__ import annotations

from a2a.agents.base import BaseAgent


class ResearcherAgent(BaseAgent):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            name="researcher",
            description="Gathers, verifies and summarizes information on a topic.",
            skills=["search", "summarize", "fact-check"],
            **kwargs,
        )

    def system_prompt(self) -> str:
        return (
            super().system_prompt()
            + "\nYou specialise in research. Always cite which memories you used and "
            "produce a concise structured summary at the end."
        )