"""Serializable LangGraph state for one customer-scoped workflow run."""
from __future__ import annotations

from typing import Any, TypedDict


class WMGraphState(TypedDict, total=False):
    """State persisted by LangGraph checkpointers.

    Only serializable, redacted references belong here. DB sessions, principals,
    provider credentials, and raw provider payloads are passed through runtime
    config or stored in database rows outside the checkpoint.
    """

    scope: dict[str, str]
    source: str
    payload: dict[str, Any]
    data_snapshot_id: str
    context_hash: str
    signal: dict[str, Any]
    assessment: dict[str, Any]
    plan: dict[str, Any]
    agent_job_id: str
    agent_message: str
    proposal_ids: list[str]
    pending_proposal_id: str | None
    approval_decision: dict[str, Any]
    execution_results: list[dict[str, Any]]
    stage: str
    error: dict[str, Any]
