"""Customer namespace and scope checks for LangGraph workflow runs."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

from fastapi import HTTPException

from app.core.auth import Principal, require_customer_access


@dataclass(frozen=True)
class CustomerScope:
    """Immutable customer namespace injected by backend code, never by the agent."""

    tenant_id: str
    customer_id: str
    agent_session_id: str
    graph_thread_id: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def require_scope_access(principal: Principal, customer_id: str) -> None:
    """Central wrapper so workflow routes cannot forget customer owner checks."""

    require_customer_access(principal, customer_id)


def assert_scope_unchanged(expected: CustomerScope, actual: dict | CustomerScope) -> None:
    """Reject graph/agent output that tries to mutate customer namespace."""

    actual_dict = actual.as_dict() if isinstance(actual, CustomerScope) else dict(actual)
    if actual_dict != expected.as_dict():
        raise HTTPException(403, "워크플로우 scope 변경이 감지되었습니다.")


def scope_digest(scope: CustomerScope) -> str:
    """Stable digest used to compare DB thread ownership with graph state."""

    payload = json.dumps(scope.as_dict(), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
