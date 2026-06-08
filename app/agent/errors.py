"""Reasoner error boundary shared by API routes and implementations."""
from __future__ import annotations


class ReasonerRateLimited(RuntimeError):
    """Configured LLM call budget was exceeded."""


class ReasonerError(RuntimeError):
    """API-normalizable LLM/reasoner error."""

    status_code = 502
    error_code = "reasoner_error"


class ReasonerUnavailable(ReasonerError):
    """Provider/auth/runtime connection problem."""

    status_code = 503
    error_code = "reasoner_unavailable"


class ReasonerOutputError(ReasonerError):
    """LLM output did not validate against the requested schema."""

    error_code = "reasoner_output_error"
