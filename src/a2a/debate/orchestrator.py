"""DebateOrchestrator: runs the pro/cons debate and streams agent-to-agent events.

The orchestrator:
  1. detects intent from the user message (debate? topic? side?)
  2. streams an ``intent`` event
  3. asks the pro and/or cons agent to produce arguments for the topic
  4. streams each agent's response as an ``agent_message`` event
  5. optionally asks the opposing agent to rebut (agent-to-agent communication)
  6. streams ``agent_comm`` events for each direct agent-to-agent exchange
  7. streams a ``final`` event summarising the debate

Events are yielded as dicts so they can be serialised to SSE in the web UI or
collected by tests.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from typing import Any

from a2a.agents.base import BaseAgent
from a2a.agents.cons import ConsAgent
from a2a.agents.llm import make_llm
from a2a.agents.pro import ProAgent
from a2a.debate.intent import detect_debate_intent

logger = logging.getLogger(__name__)


@dataclass
class DebateEvent:
    """A single streamed event during a debate."""

    type: str  # route | intent | agent_message | agent_comm | final | error
    agent: str = ""
    content: str = ""
    topic: str = ""
    side: str = ""
    to: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["timestamp"] = round(d["timestamp"], 3)
        return d


class DebateOrchestrator:
    """Runs a pro/cons debate between two agents and streams events.

    When the LLM is a ``RoutedLLM``, the orchestrator emits a ``route`` event
    before each LLM call showing which model (lower vs higher) handled it and
    why. It also forces specific tiers for specific sub-tasks:

      * intent detection  -> LOWER  (cheap classification)
      * argument generation -> router decides (usually HIGHER for reasoning)
      * rebuttals         -> HIGHER (needs to reason over opponent's points)
    """

    def __init__(
        self,
        pro: BaseAgent | None = None,
        cons: BaseAgent | None = None,
        llm=None,
    ) -> None:
        self.llm = llm or make_llm()
        self.pro = pro or ProAgent(llm=self.llm)
        self.cons = cons or ConsAgent(llm=self.llm)
        self._route_buffer: list[DebateEvent] = []
        self._install_route_hook()

    def _install_route_hook(self) -> None:
        """Capture route decisions from RoutedLLM into a buffer."""
        if not hasattr(self.llm, "on_route"):
            return  # not a routed LLM

        def hook(decision) -> None:
            self._route_buffer.append(DebateEvent(
                type="route",
                content=decision.model,
                metadata=decision.to_dict(),
            ))

        self.llm.on_route = hook

    # -- public API -------------------------------------------------------
    def run(self, user_message: str) -> dict[str, Any]:
        """Run synchronously and return the final transcript dict."""
        events = list(self.stream(user_message))
        final = next((e for e in reversed(events) if e.type == "final"), None)
        return {
            "events": [e.to_dict() for e in events],
            "final": final.content if final else "",
            "topic": final.topic if final else "",
        }

    def stream(self, user_message: str) -> Iterator[DebateEvent]:
        """Run the debate, yielding events as they happen (for SSE)."""
        try:
            # Intent detection is cheap -> force the lower (small) model.
            self._force_tier_before("intent", lower=True)
            intent = detect_debate_intent(user_message, llm=self.llm)
            yield from self._drain_route(agent="intent")
            yield DebateEvent(
                type="intent",
                content=intent.rationale or "debate",
                topic=intent.topic,
                side=intent.side,
                metadata=intent.to_dict(),
            )

            if not intent.is_debate:
                yield DebateEvent(
                    type="final",
                    content=(
                        "I couldn't detect a debate request. Ask me something like: "
                        "'Give me pros and cons of remote work.'"
                    ),
                    topic=intent.topic,
                    side=intent.side,
                )
                return

            topic = intent.topic
            side = intent.side if intent.side in {"pro", "cons", "both"} else "both"

            pro_args = ""
            cons_args = ""

            if side in {"pro", "both"}:
                # Argument generation: let the router decide (reasoning-heavy
                # topics route to HIGHER, trivial ones to LOWER).
                self._force_tier_before("pro", lower=None)
                pro_args = self._invoke_agent(self.pro, topic, "List the pros.")
                yield from self._drain_route(agent=self.pro.name)
                yield DebateEvent(
                    type="agent_message",
                    agent=self.pro.name,
                    content=pro_args,
                    topic=topic,
                    side="pro",
                )

            if side in {"cons", "both"}:
                self._force_tier_before("cons", lower=None)
                cons_args = self._invoke_agent(self.cons, topic, "List the cons.")
                yield from self._drain_route(agent=self.cons.name)
                yield DebateEvent(
                    type="agent_message",
                    agent=self.cons.name,
                    content=cons_args,
                    topic=topic,
                    side="cons",
                )

            # Agent-to-agent rebuttal: each agent sees the other's arguments
            # and posts a short rebuttal on the shared board. Rebuttals need to
            # reason over the opponent's points -> force HIGHER.
            if side == "both" and pro_args and cons_args:
                self._force_tier_before("pro", lower=False)
                rebuttal_pro = self._agent_to_agent(
                    sender=self.pro,
                    receiver=self.cons,
                    topic=topic,
                    prior=cons_args,
                    instruction="The CONS agent made these points. Write a short rebuttal defending the PRO side.",
                )
                yield from self._drain_route(agent=self.pro.name)
                yield DebateEvent(
                    type="agent_comm",
                    agent=self.pro.name,
                    to=self.cons.name,
                    content=rebuttal_pro,
                    topic=topic,
                    side="pro",
                    metadata={"kind": "rebuttal"},
                )

                self._force_tier_before("cons", lower=False)
                rebuttal_cons = self._agent_to_agent(
                    sender=self.cons,
                    receiver=self.pro,
                    topic=topic,
                    prior=pro_args,
                    instruction="The PRO agent made these points. Write a short rebuttal defending the CONS side.",
                )
                yield from self._drain_route(agent=self.cons.name)
                yield DebateEvent(
                    type="agent_comm",
                    agent=self.cons.name,
                    to=self.pro.name,
                    content=rebuttal_cons,
                    topic=topic,
                    side="cons",
                    metadata={"kind": "rebuttal"},
                )

            summary = self._build_summary(topic, side, pro_args, cons_args)
            yield DebateEvent(
                type="final",
                content=summary,
                topic=topic,
                side=side,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Debate failed")
            yield DebateEvent(type="error", content=f"Debate failed: {exc}")

    # -- route helpers ----------------------------------------------------
    def _force_tier_before(self, agent: str, lower: bool | None) -> None:
        """Set the tier for the next LLM call.

        ``lower=True``  -> LOWER (small)
        ``lower=False`` -> HIGHER (large)
        ``lower=None``  -> let the router decide (clear the override)
        """
        force = getattr(self.llm, "force_tier", None)
        if force is None:
            return
        from a2a.router.models import RouteTier

        if lower is True:
            force(RouteTier.LOWER)
        elif lower is False:
            force(RouteTier.HIGHER)
        else:
            force(None)

    def _drain_route(self, agent: str) -> Iterator[DebateEvent]:
        """Emit any buffered route events, tagged with the calling agent."""
        while self._route_buffer:
            ev = self._route_buffer.pop(0)
            ev.agent = agent
            yield ev

    # -- helpers ----------------------------------------------------------
    def _invoke_agent(self, agent: BaseAgent, topic: str, instruction: str) -> str:
        prompt = f"Topic: {topic}\n\n{instruction}"
        return agent.run(prompt, topic=topic, source="debate")

    def _agent_to_agent(
        self,
        sender: BaseAgent,
        receiver: BaseAgent,
        topic: str,
        prior: str,
        instruction: str,
    ) -> str:
        """Direct agent-to-agent exchange via the shared scratchpad + receiver.run."""
        self.pro.memory.shared.post_note(
            sender.name,
            f"-> {receiver.name} | topic={topic}\n{instruction}\nPrior points:\n{prior[:400]}",
            to=receiver.name,
            topic=topic,
        )
        prompt = (
            f"Topic: {topic}\n\n"
            f"{instruction}\n\n"
            f"Opponent's points:\n{prior}\n\n"
            f"Write a focused 2-4 sentence rebuttal."
        )
        return receiver.run(prompt, topic=topic, source=f"rebuttal-from-{sender.name}")

    @staticmethod
    def _build_summary(topic: str, side: str, pro_args: str, cons_args: str) -> str:
        parts = [f"Debate summary for: {topic}\n"]
        if pro_args:
            parts.append("PRO arguments:\n" + pro_args)
        if cons_args:
            parts.append("\nCONS arguments:\n" + cons_args)
        if side == "pro":
            parts.append("\n(Only PRO arguments were requested.)")
        elif side == "cons":
            parts.append("\n(Only CONS arguments were requested.)")
        return "\n".join(parts)