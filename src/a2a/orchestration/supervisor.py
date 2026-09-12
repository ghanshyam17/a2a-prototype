"""LangGraph-based supervisor orchestrator for multi-agent workflows.

The supervisor uses an LLM to route each step to one of the registered agents
(or to FINISH). The graph is::

    START -> supervisor -> {agent nodes} -> supervisor -> ... -> FINISH

State is shared via a typed dict and includes the running message history and
the next agent to call. Memory is preserved per-agent across the run.
"""

from __future__ import annotations

import logging
import re
from typing import Any, TypedDict

from a2a.agents.base import BaseAgent, LLMClient
from a2a.agents.llm import make_llm

logger = logging.getLogger(__name__)


class OrchestrationState(TypedDict, total=False):
    """Shared state flowing through the LangGraph workflow."""

    input: str
    messages: list[dict[str, str]]
    next: str
    iterations: int
    final: str


class SupervisorOrchestrator:
    """A supervisor that routes between registered agents using LangGraph."""

    MAX_ITERATIONS = 8

    def __init__(
        self,
        agents: list[BaseAgent],
        llm: LLMClient | None = None,
    ) -> None:
        if not agents:
            raise ValueError("At least one agent is required.")
        self.agents: dict[str, BaseAgent] = {a.name: a for a in agents}
        self.llm = llm or make_llm()
        self._graph = self._build_graph()

    # -- Graph construction ----------------------------------------------
    def _build_graph(self):
        from langgraph.graph import END, StateGraph

        builder = StateGraph(OrchestrationState)
        builder.add_node("supervisor", self._supervisor_node)
        for name in self.agents:
            builder.add_node(name, self._agent_node(name))

        builder.set_entry_point("supervisor")
        builder.add_conditional_edges(
            "supervisor",
            lambda s: s.get("next", "FINISH"),
            {**{n: n for n in self.agents}, "FINISH": END},
        )
        for name in self.agents:
            builder.add_edge(name, "supervisor")
        return builder.compile()

    # -- Nodes ------------------------------------------------------------
    def _supervisor_node(self, state: OrchestrationState) -> dict[str, Any]:
        messages = list(state.get("messages", []))
        if not messages and state.get("input"):
            messages = [{"role": "user", "content": state["input"]}]
        it = state.get("iterations", 0) + 1
        if it >= self.MAX_ITERATIONS:
            return {"next": "FINISH", "iterations": it}

        agent_catalog = "\n".join(
            f"- {a.name}: {a.card.description} (skills: {', '.join(a.card.skills)})"
            for a in self.agents.values()
        )
        routing_prompt = (
            "You are a supervisor coordinating AI agents. Decide which agent should act next "
            "or respond with FINISH when the user's request is satisfied.\n\n"
            f"Available agents:\n{agent_catalog}\n\n"
            "Conversation so far:\n"
            + "\n".join(f"{m['role']}: {m['content'][:300]}" for m in messages[-8:])
            + "\n\nRespond with ONLY one of: an agent name, or FINISH."
        )
        decision_raw = self.llm.invoke([
            {"role": "system", "content": routing_prompt},
            {"role": "user", "content": state.get("input", "")},
        ])
        decision = self._parse_decision(decision_raw, candidates=list(self.agents))
        logger.info("Supervisor decided: %s (iter=%d)", decision, it)
        return {"next": decision, "messages": messages, "iterations": it}

    def _agent_node(self, name: str):
        def node(state: OrchestrationState) -> dict[str, Any]:
            agent = self.agents[name]
            transcript = "\n".join(
                f"{m['role']}: {m['content']}" for m in state.get("messages", [])
            )
            prompt = (
                f"Original request: {state.get('input', '')}\n\n"
                f"Transcript so far:\n{transcript}\n\n"
                f"Continue the work as {agent.name}. Produce your contribution."
            )
            response = agent.run(prompt, orchestrator="supervisor")
            new_messages = list(state.get("messages", [])) + [
                {"role": "assistant", "content": response, "name": agent.name},
            ]
            return {"messages": new_messages, "next": "supervisor"}

        return node

    # -- Helpers ----------------------------------------------------------
    @staticmethod
    def _parse_decision(raw: str, candidates: list[str] | None = None) -> str:
        text = raw.strip().strip("`\"'")
        if "finish" in text.lower():
            return "FINISH"
        if candidates:
            for name in candidates:
                if re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE):
                    return name
            return "FINISH"
        match = re.search(r"\b(FINISH|[a-z_]+)\b", text, re.IGNORECASE)
        if not match:
            return "FINISH"
        token = match.group(1).lower()
        return "FINISH" if token == "finish" else token

    # -- Public API -------------------------------------------------------
    def run(self, user_input: str) -> dict[str, Any]:
        initial: OrchestrationState = {
            "input": user_input,
            "messages": [{"role": "user", "content": user_input}],
            "iterations": 0,
            "next": "",
            "final": "",
        }
        final_state = self._graph.invoke(initial, config={"recursion_limit": 25})
        messages = final_state.get("messages", [])
        final_state["final"] = messages[-1]["content"] if messages else ""
        return final_state

    def describe(self) -> list[dict[str, Any]]:
        return [a.describe() for a in self.agents.values()]