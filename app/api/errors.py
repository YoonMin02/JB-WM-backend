"""API error normalization helpers."""
from __future__ import annotations

from fastapi import HTTPException

from app.agent.errors import ReasonerError, ReasonerRateLimited


def reasoner_http_exception(error: Exception) -> HTTPException:
    if isinstance(error, ReasonerRateLimited):
        return HTTPException(
            status_code=429,
            detail={"error": "reasoner_rate_limited", "message": f"추론 호출 한도 초과: {error}"},
        )
    if isinstance(error, ReasonerError):
        return HTTPException(
            status_code=error.status_code,
            detail={"error": error.error_code, "message": str(error)},
        )
    return HTTPException(
        status_code=500,
        detail={"error": "internal_error", "message": str(error)},
    )
