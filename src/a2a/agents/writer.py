"""Writer agent: drafts prose from research notes."""

from __future__ import annotations

from a2a.agents.base import BaseAgent


class WriterAgent(BaseAgent):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            name="writer",
            description="Drafts clear, well-structured prose from research notes.",
            skills=["drafting", "editing", "outlining"],
            **kwargs,
        )

    def system_prompt(self) -> str:
        return (
            super().system_prompt()
            + "\nYou specialise in writing. Use notes posted by the researcher and "
            "produce a polished, audience-appropriate draft."
        )