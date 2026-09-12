"""Debate subsystem: intent detection, orchestrator, and event streaming."""

from a2a.debate.intent import DebaterIntent, detect_debate_intent
from a2a.debate.orchestrator import DebateEvent, DebateOrchestrator

__all__ = [
    "DebaterIntent",
    "detect_debate_intent",
    "DebateOrchestrator",
    "DebateEvent",
]