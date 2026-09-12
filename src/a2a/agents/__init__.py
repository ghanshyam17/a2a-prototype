"""Agents package: BaseAgent and sample agents."""

from a2a.agents.base import AgentCard, BaseAgent
from a2a.agents.coder import CoderAgent
from a2a.agents.cons import ConsAgent
from a2a.agents.pro import ProAgent
from a2a.agents.researcher import ResearcherAgent
from a2a.agents.writer import WriterAgent

__all__ = [
    "AgentCard",
    "BaseAgent",
    "ResearcherAgent",
    "WriterAgent",
    "CoderAgent",
    "ProAgent",
    "ConsAgent",
]