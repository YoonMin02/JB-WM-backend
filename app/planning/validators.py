"""Code-owned validation for sandboxed planning output."""
from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException

FORBIDDEN_OUTPUT_FRAGMENTS = (
    "customer_id",
    "agent_session_id",
    "graph_thread_id",
    "fintech_use_num",
    "api_tran_id",
    "bank_tran_id",
    "card_value",
    "loan_repayment_id",
    "DATABASE_URL",
    "JWT_SECRET",
)


def reject_forbidden_output_identifiers(
    output: dict[str, Any],
    *,
    forbidden_values: list[str] | None = None,
) -> None:
    """Reject output that appears to leak provider ids or backend namespace ids."""

    text = json.dumps(output, ensure_ascii=False, default=str)
    leaked = [needle for needle in FORBIDDEN_OUTPUT_FRAGMENTS if needle in text]
    leaked.extend(value for value in forbidden_values or [] if value and value in text)
    if leaked:
        raise HTTPException(422, f"agent output contains forbidden identifiers: {', '.join(leaked)}")
