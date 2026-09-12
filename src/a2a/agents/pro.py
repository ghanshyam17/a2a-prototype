"""Pro agent: argues the positive side of a topic."""

from __future__ import annotations

from a2a.agents.base import BaseAgent


class ProAgent(BaseAgent):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            name="pro",
            description="Argues the positive side / benefits of a topic.",
            skills=["pros", "advantages", "positive-arguments", "debate"],
            **kwargs,
        )

    def system_prompt(self) -> str:
        return (
            super().system_prompt()
            + "\nYou are the PRO debater. Given a topic, produce 3-5 strong, concrete "
            "arguments IN FAVOUR of it. Be specific, evidence-leaning and concise. "
            "Number each point. Do not argue against the topic."
        )