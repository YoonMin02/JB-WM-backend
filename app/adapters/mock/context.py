"""Sanitized mock context snapshots for sandboxed agent jobs.

The agent job receives one customer context pack, not a database handle. This
module is the code-owned boundary that turns provider-shaped mock data into a
redacted, single-customer snapshot suitable for LLM reasoning.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlmodel import Session

from app.tools import data_tools

REDACTION_VERSION = "v1"

FORBIDDEN_KEYS = {
    "id",
    "customer_id",
    "session_id",
    "agent_session_id",
    "graph_thread_id",
    "account_id",
    "loan_id",
    "policy_id",
    "proposal_id",
    "external_ref",
    "api_body",
    "api_body_header",
    "api_tran_id",
    "bank_tran_id",
    "fintech_use_num",
    "card_value",
    "loan_repayment_id",
    "raw_ref",
}


def build_agent_context_snapshot(db: Session, customer_id: str) -> dict[str, Any]:
    """Return a redacted, single-customer context pack for an agent job.

    The server keeps the real `customer_id` on `DataSnapshot`, while the JSON
    passed to the agent contains only domain facts and pseudonymous labels.
    """

    raw = data_tools.build_context(db, customer_id)
    profile = raw.get("profile", {})
    raw["profile"] = {
        "label": "customer",
        "age_band": profile.get("age_band"),
        "locale": profile.get("locale", "ko"),
    }
    raw.pop("customer_id", None)
    return _redact(raw)


def context_hash(context: dict[str, Any]) -> str:
    """Hash the exact redacted context persisted for a workflow run."""

    payload = json.dumps(context, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _redact(child)
            for key, child in value.items()
            if key not in FORBIDDEN_KEYS and not key.endswith("_id")
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value

