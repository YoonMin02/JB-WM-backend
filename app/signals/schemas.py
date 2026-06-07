"""Signal schemas for deterministic event detection."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SignalSource = Literal["event", "user_utterance", "detector", "approval_revision"]


class SignalEnvelope(BaseModel):
    source: SignalSource = "event"
    kind: str = "manual"
    severity: Literal["low", "mid", "high"] = "mid"
    payload: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""

