"""Cons agent: argues the negative side of a topic."""

from __future__ import annotations

from a2a.agents.base import BaseAgent


class ConsAgent(BaseAgent):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            name="cons",
            description="Argues the negative side / drawbacks of a topic.",
            skills=["cons", "disadvantages", "negative-arguments", "debate"],
            **kwargs,
        )

    def system_prompt(self) -> str:
        return (
            super().system_prompt()
            + "\nYou are the CONS debater. Given a topic, produce 3-5 strong, concrete "
            "arguments AGAINST it. Be specific, evidence-leaning and concise. "
            "Number each point. Do not argue in favour of the topic."
        )