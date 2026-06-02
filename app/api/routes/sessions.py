"""에이전트 세션 — 생성·조회·신호 주입·이벤트."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.agent.orchestrator import Orchestrator
from app.api.deps import db_session
from app.models.agent import ActionProposal, AgentEvent, AgentSession
from app.models.customer import Customer
from app.state_machine.states import State, allowed_actions

router = APIRouter(tags=["agent-sessions"])


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
def create_session(customer_id: str, db: Session = Depends(db_session)) -> dict:
    if not db.get(Customer, customer_id):
        raise HTTPException(404, "고객을 찾을 수 없습니다.")
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
def get_session_state(session_id: str, db: Session = Depends(db_session)) -> dict:
    s = db.get(AgentSession, session_id)
    if not s:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")
    return serialize_session(db, s)


@router.get("/agent-sessions/{session_id}/events")
def get_events(session_id: str, db: Session = Depends(db_session)) -> dict:
    rows = db.exec(
        select(AgentEvent).where(AgentEvent.session_id == session_id).order_by(AgentEvent.created_at)
    ).all()
    return {"events": [{"type": e.type, "detail": e.detail, "created_at": e.created_at.isoformat()} for e in rows]}


@router.post("/agent-sessions/{session_id}/signals", status_code=202)
async def post_signal(session_id: str, body: SignalIn, db: Session = Depends(db_session)) -> dict:
    from app.agent.codex_adapter import CodexRateLimited

    s = db.get(AgentSession, session_id)
    if not s:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")
    if s.state != State.MONITORING:
        raise HTTPException(409, f"신호는 Monitoring 상태에서만 받습니다 (현재: {s.state}).")
    try:
        s = await Orchestrator().handle_signal(db, s, body.source, body.payload)
    except CodexRateLimited as e:
        raise HTTPException(429, f"추론 호출 한도 초과: {e}") from e
    return serialize_session(db, s)
