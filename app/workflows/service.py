"""Service layer around the LangGraph workflow.

Routes should call this module instead of touching the checkpointer directly.
That keeps the security order explicit: resolve opaque thread, verify customer
scope, then invoke or resume the graph.
"""
from __future__ import annotations

import json
from pathlib import Path
from collections.abc import Iterator
from typing import Any, Literal

from fastapi import HTTPException
from langgraph.types import Command
from sqlmodel import Session, select

from app.core.auth import Principal
from app.core.config import settings
from app.models.agent import ActionExecution, ActionProposal, AgentEvent, AgentMessage, AgentSession
from app.models.customer import Customer
from app.models.workflow import AgentJob, AgentThread, DataSnapshot
from app.security.scope import CustomerScope, require_scope_access, scope_digest
from app.workflows.wm_graph import get_workflow_graph
from app.workflows.session_state import SessionState, allowed_actions

TENANT_ID = "jbwm"


def create_or_reuse_thread(
    db: Session,
    *,
    customer_id: str,
    principal: Principal,
    force_new: bool = False,
) -> dict[str, Any]:
    """Create an AgentSession + opaque AgentThread for one customer."""

    if db.get(Customer, customer_id) is None:
        raise HTTPException(404, "고객을 찾을 수 없습니다.")
    require_scope_access(principal, customer_id)

    if not force_new:
        active_threads = db.exec(
            select(AgentThread)
            .where(AgentThread.customer_id == customer_id, AgentThread.status == "active")
            .order_by(AgentThread.created_at.desc())
        ).all()
        existing = _pick_reusable_thread(db, active_threads)
        if existing is not None:
            if settings.app_env in {"local", "dev"} and not _has_graph_checkpoint(existing, db, principal):
                existing.status = "stale"
                db.add(existing)
                db.commit()
            else:
                return serialize_thread(db, existing)

    session = AgentSession(customer_id=customer_id, state=SessionState.MONITORING)
    db.add(session)
    db.commit()
    db.refresh(session)

    thread = AgentThread(
        tenant_id=TENANT_ID,
        customer_id=customer_id,
        agent_session_id=session.id,
        created_by_principal_id=principal.subject,
    )
    scope = CustomerScope(
        tenant_id=TENANT_ID,
        customer_id=customer_id,
        agent_session_id=session.id,
        graph_thread_id=thread.graph_thread_id,
    )
    thread.scope_hash = scope_digest(scope)
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return serialize_thread(db, thread)


def _pick_reusable_thread(db: Session, threads: list[AgentThread]) -> AgentThread | None:
    """Prefer an unresolved approval thread over a newer idle thread."""

    for thread in threads:
        session = db.get(AgentSession, thread.agent_session_id)
        if session and session.state == SessionState.USER_APPROVAL:
            return thread
    return threads[0] if threads else None


def trigger_event(
    db: Session,
    *,
    graph_thread_id: str,
    principal: Principal,
    source: str = "event",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a workflow from a manual/external signal until done or interrupted."""

    thread, session = resolve_thread(db, graph_thread_id, principal)
    if session.state not in {SessionState.MONITORING, SessionState.USER_APPROVAL}:
        raise HTTPException(409, f"신호를 받을 수 없는 세션 상태입니다: {session.state}")
    if session.state == SessionState.USER_APPROVAL:
        raise HTTPException(409, "승인 대기 중에는 먼저 approve/reject/revise를 처리해야 합니다.")

    scope = _scope_for(thread)
    state = {
        "scope": scope.as_dict(),
        "source": source,
        "payload": payload or {},
        "stage": "Monitoring",
        "execution_results": [],
    }
    config = _graph_config(thread, db, principal)
    result = get_workflow_graph().invoke(state, config)
    return {**serialize_thread(db, thread), "graph_result": _trim_graph_result(result)}


def stream_event(
    db: Session,
    *,
    graph_thread_id: str,
    principal: Principal,
    source: str = "event",
    payload: dict[str, Any] | None = None,
) -> Iterator[dict[str, Any]]:
    """Stream a workflow run as node-level server-sent events."""

    thread, session = resolve_thread(db, graph_thread_id, principal)
    if session.state not in {SessionState.MONITORING, SessionState.USER_APPROVAL}:
        raise HTTPException(409, f"신호를 받을 수 없는 세션 상태입니다: {session.state}")
    if session.state == SessionState.USER_APPROVAL:
        raise HTTPException(409, "승인 대기 중에는 먼저 approve/reject/revise를 처리해야 합니다.")

    scope = _scope_for(thread)
    state = {
        "scope": scope.as_dict(),
        "source": source,
        "payload": payload or {},
        "stage": "Monitoring",
        "execution_results": [],
    }
    yield from _stream_graph(db, thread, principal, state)


def submit_decision(
    db: Session,
    *,
    graph_thread_id: str,
    principal: Principal,
    decision: Literal["approve", "reject", "revise"],
    proposal_id: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    """Resume the workflow at the LangGraph approval interrupt."""

    thread, session = resolve_thread(db, graph_thread_id, principal)
    if session.state != SessionState.USER_APPROVAL or not session.pending_proposal_id:
        raise HTTPException(409, "승인 대기 중인 제안이 없습니다.")
    target_proposal_id = proposal_id or session.pending_proposal_id
    if target_proposal_id != session.pending_proposal_id:
        raise HTTPException(409, "현재 대기 제안만 처리할 수 있습니다.")

    config = _graph_config(thread, db, principal)
    result = get_workflow_graph().invoke(
        Command(resume={"decision": decision, "proposal_id": target_proposal_id, "note": note}),
        config,
    )
    return {**serialize_thread(db, thread), "graph_result": _trim_graph_result(result)}


def stream_decision(
    db: Session,
    *,
    graph_thread_id: str,
    principal: Principal,
    decision: Literal["approve", "reject", "revise"],
    proposal_id: str | None = None,
    note: str = "",
) -> Iterator[dict[str, Any]]:
    """Stream a resumed approval decision run as node-level SSE payloads."""

    thread, session = resolve_thread(db, graph_thread_id, principal)
    if session.state != SessionState.USER_APPROVAL or not session.pending_proposal_id:
        raise HTTPException(409, "승인 대기 중인 제안이 없습니다.")
    target_proposal_id = proposal_id or session.pending_proposal_id
    if target_proposal_id != session.pending_proposal_id:
        raise HTTPException(409, "현재 대기 제안만 처리할 수 있습니다.")

    yield from _stream_graph(
        db,
        thread,
        principal,
        Command(resume={"decision": decision, "proposal_id": target_proposal_id, "note": note}),
    )


def record_user_message(
    db: Session,
    *,
    graph_thread_id: str,
    principal: Principal,
    text: str,
) -> dict[str, Any]:
    """Append a user reply without resuming the approval interrupt.

    During `UserApproval`, a free-text reply is context for the human decision;
    the actual state transition still requires approve/reject/revise.
    """

    thread, session = resolve_thread(db, graph_thread_id, principal)
    db.add(
        AgentMessage(
            session_id=session.id,
            role="user",
            content=text,
            meta={"kind": "user_reply", "pending_proposal_id": session.pending_proposal_id},
        )
    )
    db.commit()
    return serialize_thread(db, thread)


def stream_user_message(
    db: Session,
    *,
    graph_thread_id: str,
    principal: Principal,
    text: str,
) -> Iterator[dict[str, Any]]:
    """Stream a chat message action.

    Approval-state free text is only recorded. Normal monitoring-state text is
    treated as a user utterance signal and can run the workflow.
    """

    thread, session = resolve_thread(db, graph_thread_id, principal)
    if session.state == SessionState.USER_APPROVAL:
        yield {"event": "session", "data": record_user_message(db, graph_thread_id=thread.graph_thread_id, principal=principal, text=text)}
        yield {"event": "complete", "data": serialize_thread(db, thread)}
        return
    yield from stream_event(
        db,
        graph_thread_id=thread.graph_thread_id,
        principal=principal,
        source="user_utterance",
        payload={"text": text},
    )


def resolve_thread(db: Session, graph_thread_id: str, principal: Principal) -> tuple[AgentThread, AgentSession]:
    """Resolve opaque thread id and verify principal ownership before graph use."""

    thread = db.get(AgentThread, graph_thread_id)
    if thread is None or thread.status != "active":
        raise HTTPException(404, "워크플로우 thread를 찾을 수 없습니다.")
    require_scope_access(principal, thread.customer_id)
    session = db.get(AgentSession, thread.agent_session_id)
    if session is None or session.customer_id != thread.customer_id:
        raise HTTPException(403, "thread/session scope가 일치하지 않습니다.")
    if thread.scope_hash:
        expected = scope_digest(_scope_for(thread))
        if thread.scope_hash != expected:
            raise HTTPException(403, "thread scope hash가 일치하지 않습니다.")
    return thread, session


def serialize_thread(db: Session, thread: AgentThread) -> dict[str, Any]:
    session = db.get(AgentSession, thread.agent_session_id)
    if session is None:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")

    pending = _proposal_dict(db.get(ActionProposal, session.pending_proposal_id)) if session.pending_proposal_id else None
    proposals = db.exec(
        select(ActionProposal)
        .where(ActionProposal.session_id == session.id)
        .order_by(ActionProposal.created_at)
    ).all()
    messages = db.exec(
        select(AgentMessage)
        .where(AgentMessage.session_id == session.id)
        .order_by(AgentMessage.created_at)
    ).all()
    events = db.exec(
        select(AgentEvent).where(AgentEvent.session_id == session.id).order_by(AgentEvent.created_at)
    ).all()
    snapshots = db.exec(
        select(DataSnapshot)
        .where(DataSnapshot.graph_thread_id == thread.graph_thread_id)
        .order_by(DataSnapshot.created_at.desc())
    ).all()
    jobs = db.exec(
        select(AgentJob)
        .where(AgentJob.graph_thread_id == thread.graph_thread_id)
        .order_by(AgentJob.created_at.desc())
    ).all()

    return {
        "thread_id": thread.graph_thread_id,
        "session_id": session.id,
        "customer_id": thread.customer_id,
        "state": session.state,
        "allowed_actions": allowed_actions(SessionState(session.state)),
        "pending_proposal": pending,
        "active_needs": session.active_needs,
        "recent_context": session.recent_context,
        "messages": [
            {
                "id": message.id,
                "role": message.role,
                "content": message.content,
                "metadata": message.meta,
                "created_at": message.created_at.isoformat(),
            }
            for message in messages
        ],
        "proposals": [_proposal_dict(proposal) for proposal in proposals],
        "executions": _executions(db, proposals),
        "events": [
            {"type": event.type, "detail": event.detail, "created_at": event.created_at.isoformat()}
            for event in events
        ],
        "snapshots": [
            {
                "id": snapshot.id,
                "context_hash": snapshot.context_hash,
                "redaction_version": snapshot.redaction_version,
                "created_at": snapshot.created_at.isoformat(),
            }
            for snapshot in snapshots[:5]
        ],
        "agent_jobs": [
            {
                "id": job.id,
                "mode": job.mode,
                "status": job.status,
                "created_at": job.created_at.isoformat(),
                "updated_at": job.updated_at.isoformat(),
            }
            for job in jobs[:5]
        ],
    }


def debug_thread(db: Session, graph_thread_id: str, principal: Principal) -> dict[str, Any]:
    """Return local-dev workflow internals for `/dev`.

    This is intentionally not part of the customer-facing API. It still performs
    the normal thread/customer owner check before exposing sanitized snapshots
    and agent job artifacts.
    """

    if settings.app_env not in {"local", "dev"}:
        raise HTTPException(404, "debug view is only available in local/dev")

    thread, session = resolve_thread(db, graph_thread_id, principal)
    base = serialize_thread(db, thread)
    snapshots = db.exec(
        select(DataSnapshot)
        .where(DataSnapshot.graph_thread_id == thread.graph_thread_id)
        .order_by(DataSnapshot.created_at.desc())
    ).all()
    jobs = db.exec(
        select(AgentJob)
        .where(AgentJob.graph_thread_id == thread.graph_thread_id)
        .order_by(AgentJob.created_at.desc())
    ).all()

    graph_snapshot = None
    try:
        state = get_workflow_graph().get_state(_graph_config(thread, db, principal))
        graph_snapshot = {
            "next": list(state.next),
            "values": state.values,
            "interrupts": [interrupt.value for interrupt in state.interrupts],
        }
    except Exception as exc:  # pragma: no cover - debug surface should be best-effort
        graph_snapshot = {"error": str(exc)}

    return {
        **base,
        "runtime": {
            "agent_job_mode": settings.agent_job_mode,
            "codex_command": settings.codex_command,
        },
        "graph_snapshot": graph_snapshot,
        "debug_snapshots": [
            {
                "id": snapshot.id,
                "context_hash": snapshot.context_hash,
                "redaction_version": snapshot.redaction_version,
                "created_at": snapshot.created_at.isoformat(),
                "context": snapshot.context,
            }
            for snapshot in snapshots
        ],
        "debug_agent_jobs": [
            {
                "id": job.id,
                "mode": job.mode,
                "status": job.status,
                "input_path": job.input_path,
                "output_path": job.output_path,
                "result": job.result,
                "input_json": _read_local_job_json(job.input_path),
                "output_json": _read_local_job_json(job.output_path),
                "created_at": job.created_at.isoformat(),
                "updated_at": job.updated_at.isoformat(),
            }
            for job in jobs
        ],
    }


def _scope_for(thread: AgentThread) -> CustomerScope:
    return CustomerScope(
        tenant_id=thread.tenant_id or TENANT_ID,
        customer_id=thread.customer_id,
        agent_session_id=thread.agent_session_id,
        graph_thread_id=thread.graph_thread_id,
    )


def _graph_config(thread: AgentThread, db: Session, principal: Principal) -> dict[str, Any]:
    return {
        "configurable": {
            "thread_id": thread.graph_thread_id,
            "db": db,
            "principal": principal,
        }
    }


def _has_graph_checkpoint(thread: AgentThread, db: Session, principal: Principal) -> bool:
    try:
        state = get_workflow_graph().get_state(_graph_config(thread, db, principal))
        return bool(state.values.get("scope"))
    except Exception:
        return False


def _stream_graph(
    db: Session,
    thread: AgentThread,
    principal: Principal,
    graph_input: Any,
) -> Iterator[dict[str, Any]]:
    previous_session = serialize_thread(db, thread)
    yield {"event": "session", "data": previous_session}
    latest_stage = None
    for update in get_workflow_graph().stream(graph_input, _graph_config(thread, db, principal), stream_mode="updates"):
        latest_stage = _stage_from_stream_update(update) or latest_stage
        current_session = serialize_thread(db, thread)
        yield {
            "event": "stage",
            "data": {
                "stage": latest_stage,
                "update": update,
                "session": current_session,
            },
        }
    final_session = serialize_thread(db, thread)
    pending = final_session.get("pending_proposal")
    yield {
        "event": "complete",
        "data": {
            **final_session,
            "graph_result": {
                "stage": latest_stage,
                "pending_proposal_id": pending.get("id") if pending else None,
                "interrupt": final_session.get("state") == SessionState.USER_APPROVAL,
            },
        },
    }


def _stage_from_stream_update(update: Any) -> str | None:
    if not isinstance(update, dict):
        return None
    if "__interrupt__" in update:
        return "ApprovalInterrupt"
    for value in update.values():
        if isinstance(value, dict) and value.get("stage"):
            return str(value["stage"])
    return None


def _proposal_dict(proposal: ActionProposal | None) -> dict[str, Any] | None:
    if proposal is None:
        return None
    return {
        "id": proposal.id,
        "kind": proposal.kind,
        "summary": proposal.summary,
        "has_external_effect": proposal.has_external_effect,
        "params": proposal.params,
        "rationale": proposal.rationale,
        "status": proposal.status,
        "created_at": proposal.created_at.isoformat(),
    }


def _executions(db: Session, proposals: list[ActionProposal]) -> list[dict[str, Any]]:
    proposal_ids = [proposal.id for proposal in proposals]
    if not proposal_ids:
        return []
    rows = db.exec(select(ActionExecution).where(ActionExecution.proposal_id.in_(proposal_ids))).all()
    return [
        {
            "id": row.id,
            "proposal_id": row.proposal_id,
            "executor": row.executor,
            "status": row.status,
            "result": row.result,
            "executed_at": row.executed_at.isoformat(),
        }
        for row in rows
    ]


def _trim_graph_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": result.get("stage"),
        "pending_proposal_id": result.get("pending_proposal_id"),
        "interrupt": result.get("__interrupt__") is not None,
    }


def _read_local_job_json(path: str) -> Any:
    if not path:
        return None
    file_path = Path(path)
    try:
        root = Path(settings.agent_job_root).resolve()
        resolved = file_path.resolve()
        if root not in resolved.parents:
            return {"error": "path is outside agent job root"}
        if not resolved.exists() or resolved.stat().st_size > settings.agent_job_output_max_bytes:
            return None
        return json.loads(resolved.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"error": str(exc)}
