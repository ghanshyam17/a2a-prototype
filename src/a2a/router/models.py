"""Router data models (independent of agentic_router so the a2a package can
be used without it if needed)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class RouteTier(str, Enum):
    LOWER = "lower"
    HIGHER = "higher"


class RouteMethod(str, Enum):
    HEURISTIC = "heuristic"
    CLASSIFIER = "classifier"
    OVERRIDE = "override"


@dataclass
class RouteDecision:
    """The router's verdict on which model should handle a task."""

    tier: RouteTier
    model: str
    score: float
    method: RouteMethod
    reason: str
    signals: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["tier"] = self.tier.value
        d["method"] = self.method.value
        return d