"""ActionProposal — 목록 + 승인/거절/수정 (승인 게이트)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.agent.orchestrator import Orchestrator
from app.api.deps import db_session
from app.api.routes.sessions import serialize_session
from app.models.agent import ActionProposal, AgentSession

router = APIRouter(tags=["proposals"])


@router.get("/agent-sessions/{session_id}/proposals")
def list_proposals(session_id: str, db: Session = Depends(db_session)) -> dict:
    rows = db.exec(select(ActionProposal).where(ActionProposal.session_id == session_id)).all()
    return {
        "proposals": [
            {
                "id": p.id,
                "kind": p.kind,
                "summary": p.summary,
                "has_external_effect": p.has_external_effect,
                "status": p.status,
            }
            for p in rows
        ]
    }


class ReviseIn(BaseModel):
    note: str = ""


async def _decide(db: Session, proposal_id: str, decision: str, note: str = "") -> dict:
    p = db.get(ActionProposal, proposal_id)
    if not p:
        raise HTTPException(404, "제안을 찾을 수 없습니다.")
    s = db.get(AgentSession, p.session_id)
    if not s:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")
    if s.pending_proposal_id != proposal_id:
        raise HTTPException(409, "이 제안은 현재 승인 대기 중이 아닙니다.")
    from app.models.agent import ApprovalDecision

    db.add(ApprovalDecision(proposal_id=proposal_id, decision=decision, note=note))
    db.commit()
    try:
        s = await Orchestrator().apply_decision(db, s, decision, note)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    return serialize_session(db, s)


@router.post("/proposals/{proposal_id}/approve")
async def approve(proposal_id: str, db: Session = Depends(db_session)) -> dict:
    return await _decide(db, proposal_id, "approve")


@router.post("/proposals/{proposal_id}/reject")
async def reject(proposal_id: str, db: Session = Depends(db_session)) -> dict:
    return await _decide(db, proposal_id, "reject")


@router.post("/proposals/{proposal_id}/revise")
async def revise(proposal_id: str, body: ReviseIn, db: Session = Depends(db_session)) -> dict:
    return await _decide(db, proposal_id, "revise", body.note)
