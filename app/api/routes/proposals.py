"""ActionProposal — 목록 + 승인/거절/수정 (승인 게이트)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.agent.orchestrator import Orchestrator
from app.api.deps import current_principal, db_session
from app.api.errors import reasoner_http_exception
from app.api.routes.sessions import serialize_session
from app.core.auth import Principal, require_customer_access
from app.models.agent import ActionProposal, AgentSession

router = APIRouter(tags=["proposals"])


def _authorize(principal: Principal, customer_id: str) -> None:
    if isinstance(principal, Principal):
        require_customer_access(principal, customer_id)


@router.get("/agent-sessions/{session_id}/proposals")
def list_proposals(
    session_id: str,
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> dict:
    session = db.get(AgentSession, session_id)
    if not session:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")
    _authorize(principal, session.customer_id)
    rows = db.exec(select(ActionProposal).where(ActionProposal.session_id == session_id)).all()
    return {
        "proposals": [
            {
                "id": p.id,
                "kind": p.kind,
                "summary": p.summary,
                "has_external_effect": p.has_external_effect,
                "rationale": p.rationale,
                "params": p.params,
                "status": p.status,
            }
            for p in rows
        ]
    }


class ReviseIn(BaseModel):
    note: str = ""


async def _decide(
    db: Session,
    proposal_id: str,
    decision: str,
    note: str = "",
    principal: Principal | None = None,
) -> dict:
    p = db.get(ActionProposal, proposal_id)
    if not p:
        raise HTTPException(404, "제안을 찾을 수 없습니다.")
    s = db.get(AgentSession, p.session_id)
    if not s:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")
    if principal is not None:
        _authorize(principal, s.customer_id)
    if p.status != "proposed":
        raise HTTPException(409, "이미 처리된 제안입니다.")
    if s.state != "UserApproval":
        raise HTTPException(409, f"승인 가능한 세션 상태가 아닙니다: {s.state}")
    from app.models.agent import ApprovalDecision

    db.add(ApprovalDecision(proposal_id=proposal_id, decision=decision, note=note))
    s.pending_proposal_id = proposal_id
    db.add(s)
    db.commit()
    from app.agent.errors import ReasonerError, ReasonerRateLimited

    try:
        s = await Orchestrator().apply_decision(db, s, decision, note)
    except (ReasonerRateLimited, ReasonerError) as e:
        raise reasoner_http_exception(e) from e
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    return serialize_session(db, s)


@router.post("/proposals/{proposal_id}/approve")
async def approve(
    proposal_id: str,
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> dict:
    return await _decide(db, proposal_id, "approve", principal=principal)


@router.post("/proposals/{proposal_id}/reject")
async def reject(
    proposal_id: str,
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> dict:
    return await _decide(db, proposal_id, "reject", principal=principal)


@router.post("/proposals/{proposal_id}/revise")
async def revise(
    proposal_id: str,
    body: ReviseIn,
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> dict:
    return await _decide(db, proposal_id, "revise", body.note, principal=principal)
