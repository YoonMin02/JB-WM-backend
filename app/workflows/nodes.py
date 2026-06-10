"""LangGraph nodes for the redesigned wealth-management workflow."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt
from sqlmodel import Session, select

from app.adapters.mock.context import REDACTION_VERSION, build_agent_context_snapshot, context_hash
from app.agent_jobs import AgentJobDispatcher
from app.executor.handlers import execute_scoped
from app.models.agent import (
    ActionExecution,
    ActionProposal,
    AgentEvent,
    AgentMessage,
    AgentSession,
    ApprovalDecision,
    NeedAssessmentRecord,
    PlanRecord,
    Signal,
)
from app.models.base import utcnow
from app.models.memory import CustomerMemory
from app.models.workflow import DataSnapshot
from app.planning.schemas import ActionProposalSchema, NeedAssessment, Plan
from app.policy.engine import evaluate
from app.signals.detectors import detect_signal
from app.signals.schemas import SignalEnvelope
from app.workflows.state import WMGraphState
from app.workflows.session_state import SessionState


def data_refresh(state: WMGraphState, config: RunnableConfig) -> dict[str, Any]:
    db = _db(config)
    session = _session(db, state)
    scope = _scope(state)
    _assert_scope(session, scope)

    context = build_agent_context_snapshot(db, session.customer_id)
    snapshot = DataSnapshot(
        graph_thread_id=scope["graph_thread_id"],
        customer_id=session.customer_id,
        context=context,
        context_hash=context_hash(context),
        redaction_version=REDACTION_VERSION,
    )
    db.add(snapshot)
    _event(db, session.id, "graph_state", {"stage": "DataRefresh"})
    db.commit()
    db.refresh(snapshot)

    return {
        "data_snapshot_id": snapshot.id,
        "context_hash": snapshot.context_hash,
        "stage": "DataRefresh",
    }


def signal_detect(state: WMGraphState, config: RunnableConfig) -> dict[str, Any]:
    db = _db(config)
    session = _session(db, state)
    snapshot = db.get(DataSnapshot, state["data_snapshot_id"])
    if snapshot is None:
        raise HTTPException(404, "context snapshot을 찾을 수 없습니다.")

    signal = detect_signal(state.get("source", "event"), state.get("payload", {}), snapshot.context)
    db.add(Signal(session_id=session.id, source=signal.source, payload=signal.model_dump()))
    db.add(
        AgentMessage(
            session_id=session.id,
            role="user" if signal.source == "user_utterance" else "system",
            content=_message_content(signal),
            meta={"kind": "signal", "signal": signal.model_dump()},
        )
    )
    _event(db, session.id, "graph_state", {"stage": "SignalDetect", "signal": signal.model_dump()})
    db.commit()
    return {"signal": signal.model_dump(), "stage": "SignalDetect"}


def signal_gate(state: WMGraphState, config: RunnableConfig) -> dict[str, Any]:
    db = _db(config)
    session = _session(db, state)
    signal = SignalEnvelope.model_validate(state["signal"])
    _event(db, session.id, "graph_state", {"stage": "SignalGate", "kind": signal.kind})
    db.commit()
    return {"stage": "SignalGate"}


def build_context(state: WMGraphState, config: RunnableConfig) -> dict[str, Any]:
    db = _db(config)
    session = _session(db, state)
    _event(
        db,
        session.id,
        "context_pack",
        {
            "stage": "BuildContext",
            "data_snapshot_id": state["data_snapshot_id"],
            "context_hash": state.get("context_hash"),
        },
    )
    db.commit()
    return {"stage": "BuildContext"}


def spawn_agent(state: WMGraphState, config: RunnableConfig) -> dict[str, Any]:
    db = _db(config)
    session = _session(db, state)
    snapshot = db.get(DataSnapshot, state["data_snapshot_id"])
    if snapshot is None:
        raise HTTPException(404, "context snapshot을 찾을 수 없습니다.")
    signal = SignalEnvelope.model_validate(state["signal"])

    result = AgentJobDispatcher().run(db, session=session, snapshot=snapshot, signal=signal)
    assessment: NeedAssessment = result["assessment"]
    plan: Plan = result["plan"]
    job = result["job"]
    _event(db, session.id, "agent_job", {"stage": "SpawnAgent", "agent_job_id": job.id})
    db.commit()
    return {
        "assessment": assessment.model_dump(),
        "plan": plan.model_dump(),
        "agent_job_id": job.id,
        "agent_message": result["message"],
        "stage": "SpawnAgent",
    }


def validate_output(state: WMGraphState, config: RunnableConfig) -> dict[str, Any]:
    db = _db(config)
    session = _session(db, state)
    assessment = NeedAssessment.model_validate(state["assessment"])
    plan = Plan.model_validate(state["plan"])
    _event(
        db,
        session.id,
        "graph_state",
        {"stage": "ValidateOutput", "primary_need": assessment.primary_need, "proposal_count": len(plan.proposals)},
    )
    db.commit()
    return {"stage": "ValidateOutput"}


def policy_check(state: WMGraphState, config: RunnableConfig) -> dict[str, Any]:
    db = _db(config)
    session = _session(db, state)
    assessment = NeedAssessment.model_validate(state["assessment"])
    plan = Plan.model_validate(state["plan"])

    _record_assessment(db, session, assessment)
    proposals = _persist_plan(db, session, plan)
    _record_plan(db, session, plan, proposals, state.get("agent_message", ""))

    auto_executed: list[str] = []
    pending = None
    for proposal in proposals:
        if _needs_approval(proposal):
            pending = pending or proposal
            continue
        execution = execute_scoped(
            db,
            proposal_id=proposal.id,
            customer_id=session.customer_id,
            require_approval=False,
        )
        auto_executed.append(execution.id)

    if pending is not None:
        session.pending_proposal_id = pending.id
        session.state = SessionState.USER_APPROVAL
    else:
        session.pending_proposal_id = None
        session.state = SessionState.MONITORING
    session.active_needs = {"primary_need": assessment.primary_need, "needs": _need_levels(assessment)}
    session.recent_context = {
        "assessment": assessment.model_dump(),
        "plan": plan.model_dump(),
        "data_snapshot_id": state["data_snapshot_id"],
        "agent_job_id": state.get("agent_job_id"),
    }
    session.updated_at = utcnow()
    db.add(session)
    _event(
        db,
        session.id,
        "policy",
        {
            "stage": "PolicyCheck",
            "proposal_ids": [proposal.id for proposal in proposals],
            "pending_proposal_id": pending.id if pending else None,
            "auto_execution_ids": auto_executed,
        },
    )
    db.commit()
    return {
        "proposal_ids": [proposal.id for proposal in proposals],
        "pending_proposal_id": pending.id if pending else None,
        "stage": "PolicyCheck",
    }


def approval_interrupt(state: WMGraphState, config: RunnableConfig) -> dict[str, Any]:
    pending_id = state.get("pending_proposal_id")
    if pending_id is None:
        return {"stage": "ApprovalSkipped"}

    db = _db(config)
    _session(db, state)
    proposal = db.get(ActionProposal, pending_id)
    if proposal is None:
        raise HTTPException(404, "승인 대기 제안을 찾을 수 없습니다.")

    decision = interrupt(
        {
            "proposal_id": proposal.id,
            "kind": proposal.kind,
            "summary": proposal.summary,
            "rationale": proposal.rationale,
            "message": "이 제안은 고객 승인 후에만 실행할 수 있습니다.",
        }
    )
    return {"approval_decision": decision, "stage": "ApprovalInterrupt"}


def execute_action(state: WMGraphState, config: RunnableConfig) -> dict[str, Any]:
    db = _db(config)
    session = _session(db, state)
    pending_id = state.get("pending_proposal_id")
    if pending_id is None:
        return {"stage": "ExecuteSkipped"}

    decision = dict(state.get("approval_decision") or {})
    proposal_id = str(decision.get("proposal_id") or pending_id)
    if proposal_id != pending_id:
        raise HTTPException(409, "승인 결정과 대기 제안이 일치하지 않습니다.")

    proposal = db.get(ActionProposal, pending_id)
    if proposal is None:
        raise HTTPException(404, "제안을 찾을 수 없습니다.")

    action = str(decision.get("decision") or "")
    note = str(decision.get("note") or "")
    decided_by = _principal_subject(config)
    db.add(ApprovalDecision(proposal_id=proposal.id, decision=action, decided_by=decided_by, note=note))

    execution_results = list(state.get("execution_results") or [])
    if action == "approve":
        proposal.status = "approved"
        db.add(proposal)
        db.commit()
        execution = execute_scoped(
            db,
            proposal_id=proposal.id,
            customer_id=session.customer_id,
            require_approval=True,
        )
        execution_results.append(_execution_dict(execution))
        _event(db, session.id, "approval", {"proposal_id": proposal.id, "decision": "approve"})
    elif action == "reject":
        proposal.status = "rejected"
        db.add(proposal)
        _event(db, session.id, "approval", {"proposal_id": proposal.id, "decision": "reject"})
    elif action == "revise":
        proposal.status = "deferred"
        db.add(proposal)
        db.add(
            AgentMessage(
                session_id=session.id,
                role="assistant",
                content="수정 요청을 기록했습니다. 원하는 방향을 메시지로 남기면 새 신호로 다시 검토하겠습니다.",
                meta={"kind": "revision_requested", "proposal_id": proposal.id},
            )
        )
        _event(db, session.id, "approval", {"proposal_id": proposal.id, "decision": "revise", "note": note})
    else:
        raise HTTPException(400, "decision은 approve/reject/revise 중 하나여야 합니다.")

    next_pending = _next_pending_proposal(db, session)
    session.pending_proposal_id = next_pending.id if next_pending is not None else None
    session.state = SessionState.USER_APPROVAL if next_pending is not None else SessionState.MONITORING
    session.updated_at = utcnow()
    db.add(session)
    db.commit()

    return {
        "pending_proposal_id": session.pending_proposal_id,
        "approval_decision": {},
        "execution_results": execution_results,
        "stage": "ExecuteAction",
    }


def verify_result(state: WMGraphState, config: RunnableConfig) -> dict[str, Any]:
    db = _db(config)
    session = _session(db, state)
    _event(db, session.id, "graph_state", {"stage": "VerifyResult", "results": state.get("execution_results", [])})
    db.commit()
    return {"stage": "VerifyResult"}


def update_memory(state: WMGraphState, config: RunnableConfig) -> dict[str, Any]:
    db = _db(config)
    session = _session(db, state)
    memory = db.get(CustomerMemory, session.customer_id)
    if memory is None:
        memory = CustomerMemory(customer_id=session.customer_id)
    memory.updated_at = utcnow()
    session.updated_at = utcnow()
    if not session.pending_proposal_id:
        session.state = SessionState.MONITORING
        session.active_needs = {}
    db.add(memory)
    db.add(session)
    _event(db, session.id, "memory", {"stage": "UpdateMemory", "updated": True})
    db.commit()
    return {"stage": "Done"}


def route_after_policy(state: WMGraphState) -> str:
    return "approval_interrupt" if state.get("pending_proposal_id") else "verify_result"


def route_after_execution(state: WMGraphState) -> str:
    return "approval_interrupt" if state.get("pending_proposal_id") else "verify_result"


def _db(config: RunnableConfig) -> Session:
    db = config["configurable"].get("db")
    if not isinstance(db, Session):
        raise RuntimeError("LangGraph DB session missing from runtime config")
    return db


def _scope(state: WMGraphState) -> dict[str, str]:
    scope = state.get("scope") or {}
    required = {"tenant_id", "customer_id", "agent_session_id", "graph_thread_id"}
    missing = required - set(scope)
    if missing:
        raise HTTPException(400, f"workflow scope missing: {', '.join(sorted(missing))}")
    return scope


def _session(db: Session, state: WMGraphState) -> AgentSession:
    scope = _scope(state)
    session = db.get(AgentSession, scope["agent_session_id"])
    if session is None:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")
    return session


def _assert_scope(session: AgentSession, scope: dict[str, str]) -> None:
    if session.customer_id != scope["customer_id"] or session.id != scope["agent_session_id"]:
        raise HTTPException(403, "워크플로우 scope가 세션과 일치하지 않습니다.")


def _event(db: Session, session_id: str, type_: str, detail: dict[str, Any]) -> None:
    db.add(AgentEvent(session_id=session_id, type=type_, detail=detail))


def _message_content(signal: SignalEnvelope) -> str:
    if signal.source == "user_utterance":
        text = signal.payload.get("text")
        return str(text) if text else str(signal.payload)
    summary = signal.payload.get("customer_summary")
    if summary:
        title = signal.payload.get("title") or "새 금융 데이터"
        return f"{title}: {summary}"
    return f"{signal.kind}: {signal.rationale}"


def _need_levels(assessment: NeedAssessment) -> dict[str, str]:
    return {
        "medical_cost_need": assessment.medical_cost_need,
        "insurance_need": assessment.insurance_need,
        "cashflow_need": assessment.cashflow_need,
        "asset_defense_need": assessment.asset_defense_need,
        "investment_adjust_need": assessment.investment_adjust_need,
        "life_plan_need": assessment.life_plan_need,
    }


def _record_assessment(db: Session, session: AgentSession, assessment: NeedAssessment) -> None:
    db.add(
        NeedAssessmentRecord(
            session_id=session.id,
            needs=_need_levels(assessment),
            primary_need=assessment.primary_need,
            confidence=assessment.confidence,
            rationale=assessment.rationale,
            raw_output=assessment.model_dump(),
        )
    )


def _persist_plan(db: Session, session: AgentSession, plan: Plan) -> list[ActionProposal]:
    proposals: list[ActionProposal] = []
    for item in plan.proposals:
        proposal = ActionProposal(
            session_id=session.id,
            kind=item.kind,
            summary=item.summary,
            has_external_effect=item.has_external_effect,
            params=item.params,
            rationale=item.rationale,
        )
        db.add(proposal)
        proposals.append(proposal)
    db.commit()
    for proposal in proposals:
        db.refresh(proposal)
    return proposals


def _record_plan(db: Session, session: AgentSession, plan: Plan, proposals: list[ActionProposal], message: str) -> None:
    db.add(
        PlanRecord(
            session_id=session.id,
            explanation=plan.explanation,
            raw_output=plan.model_dump(),
            proposal_ids=[proposal.id for proposal in proposals],
        )
    )
    db.add(
        AgentMessage(
            session_id=session.id,
            role="assistant",
            content=message or plan.explanation or "계획을 생성했습니다.",
            meta={"kind": "plan", "proposal_ids": [proposal.id for proposal in proposals]},
        )
    )
    db.commit()


def _needs_approval(proposal: ActionProposal) -> bool:
    schema = ActionProposalSchema(
        kind=proposal.kind,
        summary=proposal.summary,
        has_external_effect=proposal.has_external_effect,
        params=proposal.params,
        rationale=proposal.rationale,
    )
    return evaluate(schema).needs_approval


def _next_pending_proposal(db: Session, session: AgentSession) -> ActionProposal | None:
    proposals = db.exec(
        select(ActionProposal)
        .where(ActionProposal.session_id == session.id, ActionProposal.status == "proposed")
        .order_by(ActionProposal.created_at)
    ).all()
    for proposal in proposals:
        if _needs_approval(proposal):
            return proposal
    return None


def _execution_dict(execution: ActionExecution) -> dict[str, Any]:
    return {
        "id": execution.id,
        "proposal_id": execution.proposal_id,
        "executor": execution.executor,
        "status": execution.status,
        "result": execution.result,
    }


def _principal_subject(config: RunnableConfig) -> str:
    principal = config["configurable"].get("principal")
    return str(getattr(principal, "subject", "") or "")
