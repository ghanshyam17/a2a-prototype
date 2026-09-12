"""Intent detection for the chat-as-interface debate flow.

Given a free-form user message, ``detect_debate_intent`` decides:
  * whether the user is asking for a pros/cons debate
  * which side(s) to invoke: "pro", "cons", or "both"
  * the topic to debate

The detector uses an LLM when available, falling back to a regex/keyword based
heuristic so the chat UI is usable even without an LLM server running.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from typing import Any

from a2a.agents.base import LLMClient
from a2a.agents.llm import StubLLM

logger = logging.getLogger(__name__)


@dataclass
class DebaterIntent:
    """Parsed intent from the user's chat message."""

    is_debate: bool
    topic: str
    side: str  # "pro" | "cons" | "both"
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_PRO_RE = re.compile(r"\b(pro|pros|advantages?|benefits?|in favour of|in favor of|for)\b", re.I)
_CON_RE = re.compile(
    r"\b(cons?|disadvantages?|drawbacks?|against|negative|downsides?)\b", re.I
)
_DEBATE_RE = re.compile(
    r"\b(pros?\s*(and|vs\.?|/)\s*cons?|debate|argue|arguments?\s+(for|against))\b",
    re.I,
)
_STOPWORDS = {
    "the", "a", "an", "is", "are", "of", "for", "and", "or", "to", "about",
    "on", "in", "with", "give", "me", "list", "please", "tell", "show",
    "what", "vs", "versus", "pros", "cons", "pro", "con", "advantages",
    "disadvantages", "benefits", "drawbacks", "debate", "arguments", "argument",
}


def _heuristic(message: str) -> DebaterIntent:
    msg = message.strip()
    low = msg.lower()

    has_pro = bool(_PRO_RE.search(low))
    has_con = bool(_CON_RE.search(low))
    has_debate = bool(_DEBATE_RE.search(low))

    is_debate = has_debate or (has_pro and has_con) or has_pro or has_con
    if has_pro and has_con:
        side = "both"
    elif has_con:
        side = "cons"
    elif has_pro:
        side = "pro"
    else:
        side = "both"

    # crude topic extraction: strip debate keywords, keep the rest
    cleaned = msg
    for pat in (_DEBATE_RE, _PRO_RE, _CON_RE):
        cleaned = pat.sub(" ", cleaned)
    cleaned = re.sub(r"\b(please|give me|list|tell me|show me|what are|what is)\b", " ", cleaned, flags=re.I)
    tokens = [t for t in re.split(r"\s+", cleaned) if t and t.lower() not in _STOPWORDS]
    topic = " ".join(tokens).strip(" -:,.|/\"'") or msg
    return DebaterIntent(is_debate=is_debate, topic=topic or "(unspecified topic)", side=side)


_INTENT_PROMPT = """You are an intent classifier for a debate assistant.
Given a user message, decide if they want a pros/cons debate and extract:
- is_debate: true/false
- topic: the subject to debate (a short noun phrase, <= 8 words)
- side: one of "pro", "cons", "both"
- rationale: one short sentence

Respond with ONLY valid JSON, no markdown fences, with exactly these keys:
{"is_debate": bool, "topic": str, "side": str, "rationale": str}

User message: """


def detect_debate_intent(message: str, llm: LLMClient | None = None) -> DebaterIntent:
    """Detect debate intent from a chat message."""
    if not message.strip():
        return DebaterIntent(is_debate=False, topic="", side="both")

    if llm is not None and not isinstance(llm, StubLLM):
        try:
            raw = llm.invoke([
                {"role": "system", "content": _INTENT_PROMPT + message.strip()},
                {"role": "user", "content": message.strip()},
            ])
            data = _parse_json(raw)
            if data:
                return DebaterIntent(
                    is_debate=bool(data.get("is_debate", False)),
                    topic=str(data.get("topic", "")).strip() or message.strip(),
                    side=str(data.get("side", "both")).strip().lower(),
                    rationale=str(data.get("rationale", "")),
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM intent detection failed (%s); using heuristic.", exc)

    return _heuristic(message)


def _parse_json(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    # try to locate the first JSON object in the text
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None