"""Pydantic models for the A2A protocol messages."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class AgentCardModel(BaseModel):
    """Public agent card served at /.well-known/agent.json."""

    name: str
    description: str
    skills: list[str] = Field(default_factory=list)
    url: str | None = None
    version: str = "0.1.0"


class A2AMessage(BaseModel):
    role: str = "user"
    content: str
    sender: str | None = None
    receiver: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class A2ATask(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    message: A2AMessage
    status: str = "pending"  # pending | working | completed | failed
    result: str | None = None
    assigned_to: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()