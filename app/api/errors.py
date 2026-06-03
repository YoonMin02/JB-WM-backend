"""API error normalization helpers."""
from __future__ import annotations

from fastapi import HTTPException

from app.agent.codex_adapter import CodexRateLimited, CodexReasoningError


def reasoner_http_exception(error: Exception) -> HTTPException:
    if isinstance(error, CodexRateLimited):
        return HTTPException(
            status_code=429,
            detail={"error": "codex_rate_limited", "message": f"추론 호출 한도 초과: {error}"},
        )
    if isinstance(error, CodexReasoningError):
        return HTTPException(
            status_code=error.status_code,
            detail={"error": error.error_code, "message": str(error)},
        )
    return HTTPException(
        status_code=500,
        detail={"error": "internal_error", "message": str(error)},
    )
