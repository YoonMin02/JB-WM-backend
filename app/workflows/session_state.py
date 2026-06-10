"""Customer-facing session state for the LangGraph workflow."""
from __future__ import annotations

from enum import StrEnum


class SessionState(StrEnum):
    MONITORING = "Monitoring"
    USER_APPROVAL = "UserApproval"


def allowed_actions(state: SessionState) -> list[str]:
    if state == SessionState.USER_APPROVAL:
        return ["approve", "reject", "revise"]
    return []
