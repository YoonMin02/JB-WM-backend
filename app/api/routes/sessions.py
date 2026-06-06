"""에이전트 세션 — 생성·조회·신호 주입·이벤트."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.agent.orchestrator import Orchestrator
from app.api.deps import current_principal, db_session
from app.api.errors import reasoner_http_exception
from app.core.auth import Principal, require_customer_access
from app.models.base import utcnow
from app.models.agent import (
    ActionProposal,
    AgentEvent,
    AgentMessage,
    AgentSession,
    NeedAssessmentRecord,
    PlanRecord,
)
from app.models.customer import Customer
from app.state_machine.states import State, allowed_actions
from app.state_machine.machine import transition

router = APIRouter(tags=["agent-sessions"])


def _authorize(principal: Principal, customer_id: str) -> None:
    if isinstance(principal, Principal):
        require_customer_access(principal, customer_id)


def serialize_session(db: Session, s: AgentSession) -> dict:
    pending = None
    if s.pending_proposal_id:
        p = db.get(ActionProposal, s.pending_proposal_id)
        if p:
            pending = {
                "id": p.id,
                "kind": p.kind,
                "summary": p.summary,
                "has_external_effect": p.has_external_effect,
                "rationale": p.rationale,
            }
    return {
        "session_id": s.id,
        "customer_id": s.customer_id,
        "state": s.state,
        "active_needs": s.active_needs,
        "allowed_actions": allowed_actions(State(s.state)),
        "pending_proposal": pending,
        "recent_context": s.recent_context,
        "failure_reason": s.failure_reason,
    }


class SignalIn(BaseModel):
    source: str = "event"  # event | user_utterance
    payload: dict = {}


@router.post("/customers/{customer_id}/agent-sessions", status_code=201)
def create_session(
    customer_id: str,
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
    force_new: bool = False,
) -> dict:
    if not db.get(Customer, customer_id):
        raise HTTPException(404, "고객을 찾을 수 없습니다.")
    _authorize(principal, customer_id)
    if not force_new:
        existing = db.exec(
            select(AgentSession)
            .where(AgentSession.customer_id == customer_id)
            .order_by(AgentSession.created_at.desc())
        ).first()
        if existing:
            return serialize_session(db, existing)
    s = AgentSession(customer_id=customer_id, state=State.MONITORING)
    db.add(s)
    db.commit()
    db.refresh(s)
    return serialize_session(db, s)


@router.get("/agent-sessions/{session_id}")
def get_session_state(
    session_id: str,
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> dict:
    s = db.get(AgentSession, session_id)
    if not s:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")
    _authorize(principal, s.customer_id)
    return serialize_session(db, s)


@router.get("/agent-sessions/{session_id}/events")
def get_events(
    session_id: str,
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> dict:
    s = db.get(AgentSession, session_id)
    if not s:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")
    _authorize(principal, s.customer_id)
    rows = db.exec(
        select(AgentEvent).where(AgentEvent.session_id == session_id).order_by(AgentEvent.created_at)
    ).all()
    return {"events": [{"type": e.type, "detail": e.detail, "created_at": e.created_at.isoformat()} for e in rows]}


@router.get("/agent-sessions/{session_id}/records")
def get_records(
    session_id: str,
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> dict:
    s = db.get(AgentSession, session_id)
    if not s:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")
    _authorize(principal, s.customer_id)
    messages = db.exec(
        select(AgentMessage)
        .where(AgentMessage.session_id == session_id)
        .order_by(AgentMessage.created_at)
    ).all()
    assessments = db.exec(
        select(NeedAssessmentRecord)
        .where(NeedAssessmentRecord.session_id == session_id)
        .order_by(NeedAssessmentRecord.created_at)
    ).all()
    plans = db.exec(
        select(PlanRecord).where(PlanRecord.session_id == session_id).order_by(PlanRecord.created_at)
    ).all()
    return {
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "metadata": m.meta,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
        "need_assessments": [
            {
                "primary_need": r.primary_need,
                "needs": r.needs,
                "confidence": r.confidence,
                "rationale": r.rationale,
                "raw_output": r.raw_output,
                "created_at": r.created_at.isoformat(),
            }
            for r in assessments
        ],
        "plans": [
            {
                "explanation": p.explanation,
                "raw_output": p.raw_output,
                "proposal_ids": p.proposal_ids,
                "created_at": p.created_at.isoformat(),
            }
            for p in plans
        ],
    }


@router.post("/agent-sessions/{session_id}/signals", status_code=202)
async def post_signal(
    session_id: str,
    body: SignalIn,
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> dict:
    from app.agent.errors import ReasonerError, ReasonerRateLimited

    s = db.get(AgentSession, session_id)
    if not s:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")
    _authorize(principal, s.customer_id)
    if s.state != State.MONITORING:
        raise HTTPException(409, f"신호는 Monitoring 상태에서만 받습니다 (현재: {s.state}).")
    try:
        s = await Orchestrator().handle_signal(db, s, body.source, body.payload)
    except (ReasonerRateLimited, ReasonerError) as e:
        _recover_reasoner_failure(db, s, e)
        raise reasoner_http_exception(e) from e
    return serialize_session(db, s)


def _recover_reasoner_failure(db: Session, session: AgentSession, error: Exception) -> None:
    """Reasoner 실패 후 세션을 재시도 가능한 Monitoring 상태로 되돌린다."""
    db.refresh(session)
    session.failure_reason = str(error)
    session.updated_at = utcnow()
    db.add(session)
    db.commit()
    if session.state not in {State.FAILED, State.UPDATE_MEMORY, State.MONITORING}:
        transition(db, session, State.FAILED, detail={"error": str(error)})
    if session.state == State.FAILED:
        transition(db, session, State.UPDATE_MEMORY, detail={"reason": "reasoner_failure"})
    if session.state == State.UPDATE_MEMORY:
        transition(db, session, State.MONITORING, detail={"reason": "reasoner_failure"})
