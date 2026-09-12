"""Coder agent: writes and reviews code."""

from __future__ import annotations

from a2a.agents.base import BaseAgent


class CoderAgent(BaseAgent):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            name="coder",
            description="Writes, reviews and explains code.",
            skills=["python", "refactoring", "code-review"],
            **kwargs,
        )

    def system_prompt(self) -> str:
        return (
            super().system_prompt()
            + "\nYou specialise in coding. Prefer small, testable functions and "
            "explain assumptions in comments."
        )