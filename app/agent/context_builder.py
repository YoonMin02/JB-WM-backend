"""Build explicit context packs for stateless LLM runs.

The DB, not the LLM provider thread, owns JB-WM session continuity. This module
decides which previous conversation, decisions, proposals, and policy text are
re-injected into each one-shot reasoner call.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.core.config import settings
from app.models.agent import (
    ActionProposal,
    AgentEvent,
    AgentMessage,
    AgentSession,
    NeedAssessmentRecord,
    PlanRecord,
)
from app.tools.data_tools import build_context

RECENT_MESSAGE_LIMIT = 12
DECISION_RECORD_LIMIT = 8
EVENT_LIMIT = 20
POLICY_DOC_LIMIT = 8
POLICY_DOC_CHAR_LIMIT = 4000


def build_agent_context(
    db: Session,
    session: AgentSession,
    *,
    current_signal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the full read-only context pack for one reasoner call."""
    ctx = build_context(db, session.customer_id)
    ctx["agent_session"] = {
        "id": session.id,
        "state": session.state,
        "active_needs": session.active_needs,
        "pending_proposal_id": session.pending_proposal_id,
        "recent_context": session.recent_context,
        "current_signal": current_signal,
    }
    ctx["session_memory"] = {
        "recent_conversation": _recent_messages(db, session.id),
        "decision_history": _decision_history(db, session.id),
        "proposal_history": _proposal_history(db, session.id),
        "event_timeline": _event_timeline(db, session.id),
    }
    ctx["policy_context"] = _policy_docs()
    return ctx


def _recent_messages(db: Session, session_id: str) -> list[dict[str, Any]]:
    rows = db.exec(
        select(AgentMessage)
        .where(AgentMessage.session_id == session_id)
        .order_by(AgentMessage.created_at.desc())
        .limit(RECENT_MESSAGE_LIMIT)
    ).all()
    return [
        {
            "role": row.role,
            "content": row.content,
            "metadata": row.meta,
            "created_at": row.created_at.isoformat(),
        }
        for row in reversed(rows)
    ]


def _decision_history(db: Session, session_id: str) -> dict[str, list[dict[str, Any]]]:
    assessments = db.exec(
        select(NeedAssessmentRecord)
        .where(NeedAssessmentRecord.session_id == session_id)
        .order_by(NeedAssessmentRecord.created_at.desc())
        .limit(DECISION_RECORD_LIMIT)
    ).all()
    plans = db.exec(
        select(PlanRecord)
        .where(PlanRecord.session_id == session_id)
        .order_by(PlanRecord.created_at.desc())
        .limit(DECISION_RECORD_LIMIT)
    ).all()
    return {
        "need_assessments": [
            {
                "primary_need": row.primary_need,
                "needs": row.needs,
                "confidence": row.confidence,
                "rationale": row.rationale,
                "created_at": row.created_at.isoformat(),
            }
            for row in reversed(assessments)
        ],
        "plans": [
            {
                "explanation": row.explanation,
                "proposal_ids": row.proposal_ids,
                "created_at": row.created_at.isoformat(),
            }
            for row in reversed(plans)
        ],
    }


def _proposal_history(db: Session, session_id: str) -> list[dict[str, Any]]:
    rows = db.exec(
        select(ActionProposal)
        .where(ActionProposal.session_id == session_id)
        .order_by(ActionProposal.created_at.desc())
        .limit(DECISION_RECORD_LIMIT)
    ).all()
    return [
        {
            "id": row.id,
            "kind": row.kind,
            "summary": row.summary,
            "has_external_effect": row.has_external_effect,
            "status": row.status,
            "rationale": row.rationale,
            "created_at": row.created_at.isoformat(),
        }
        for row in reversed(rows)
    ]


def _event_timeline(db: Session, session_id: str) -> list[dict[str, Any]]:
    rows = db.exec(
        select(AgentEvent)
        .where(AgentEvent.session_id == session_id)
        .order_by(AgentEvent.created_at.desc())
        .limit(EVENT_LIMIT)
    ).all()
    return [
        {
            "type": row.type,
            "detail": row.detail,
            "created_at": row.created_at.isoformat(),
        }
        for row in reversed(rows)
    ]


def _policy_docs() -> list[dict[str, str]]:
    root = Path(settings.policy_docs_path)
    if not root.exists() or not root.is_dir():
        return []
    docs: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if len(docs) >= POLICY_DOC_LIMIT:
            break
        if not path.is_file() or path.suffix.lower() not in {".md", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")[:POLICY_DOC_CHAR_LIMIT]
        docs.append({"path": str(path.relative_to(root)), "content": text})
    return docs
