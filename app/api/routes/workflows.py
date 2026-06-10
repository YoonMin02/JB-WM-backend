"""LangGraph workflow API used by the local React demo."""
from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.api.deps import current_principal, db_session
from app.core.auth import Principal, require_operator
from app.workflows import service

router = APIRouter(tags=["langgraph-workflows"])


class EventIn(BaseModel):
    source: Literal["event", "user_utterance"] = "event"
    payload: dict = Field(default_factory=dict)


class MessageIn(BaseModel):
    text: str


class DecisionIn(BaseModel):
    decision: Literal["approve", "reject", "revise"]
    proposal_id: str | None = None
    note: str = ""


@router.post("/customers/{customer_id}/workflow-sessions", status_code=201)
def create_workflow_session(
    customer_id: str,
    force_new: bool = False,
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> dict:
    return service.create_or_reuse_thread(db, customer_id=customer_id, principal=principal, force_new=force_new)


@router.get("/workflow-sessions/{thread_id}")
def get_workflow_session(
    thread_id: str,
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> dict:
    thread, _ = service.resolve_thread(db, thread_id, principal)
    return service.serialize_thread(db, thread)


@router.get("/workflow-sessions/{thread_id}/debug")
def get_workflow_debug(
    thread_id: str,
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> dict:
    require_operator(principal)
    return service.debug_thread(db, thread_id, principal)


@router.post("/workflow-sessions/{thread_id}/events", status_code=202)
def post_workflow_event(
    thread_id: str,
    body: EventIn,
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> dict:
    require_operator(principal)
    return service.trigger_event(
        db,
        graph_thread_id=thread_id,
        principal=principal,
        source=body.source,
        payload=body.payload,
    )


@router.post("/workflow-sessions/{thread_id}/events/stream")
def stream_workflow_event(
    thread_id: str,
    body: EventIn,
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> StreamingResponse:
    require_operator(principal)
    return _sse_response(
        service.stream_event(
            db,
            graph_thread_id=thread_id,
            principal=principal,
            source=body.source,
            payload=body.payload,
        )
    )


@router.post("/workflow-sessions/{thread_id}/messages", status_code=202)
def post_workflow_message(
    thread_id: str,
    body: MessageIn,
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> dict:
    thread, session = service.resolve_thread(db, thread_id, principal)
    if session.state == "UserApproval":
        return service.record_user_message(
            db,
            graph_thread_id=thread.graph_thread_id,
            principal=principal,
            text=body.text,
        )
    return service.trigger_event(
        db,
        graph_thread_id=thread_id,
        principal=principal,
        source="user_utterance",
        payload={"text": body.text},
    )


@router.post("/workflow-sessions/{thread_id}/messages/stream")
def stream_workflow_message(
    thread_id: str,
    body: MessageIn,
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> StreamingResponse:
    return _sse_response(
        service.stream_user_message(
            db,
            graph_thread_id=thread_id,
            principal=principal,
            text=body.text,
        )
    )


@router.post("/workflow-sessions/{thread_id}/decisions", status_code=202)
def post_workflow_decision(
    thread_id: str,
    body: DecisionIn,
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> dict:
    return service.submit_decision(
        db,
        graph_thread_id=thread_id,
        principal=principal,
        decision=body.decision,
        proposal_id=body.proposal_id,
        note=body.note,
    )


@router.post("/workflow-sessions/{thread_id}/decisions/stream")
def stream_workflow_decision(
    thread_id: str,
    body: DecisionIn,
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> StreamingResponse:
    return _sse_response(
        service.stream_decision(
            db,
            graph_thread_id=thread_id,
            principal=principal,
            decision=body.decision,
            proposal_id=body.proposal_id,
            note=body.note,
        )
    )


def _sse_response(events) -> StreamingResponse:
    def encode():
        try:
            for item in events:
                event = item.get("event", "message")
                data = json.dumps(item.get("data", {}), ensure_ascii=False, default=str)
                yield f"event: {event}\n"
                yield f"data: {data}\n\n"
        except Exception as exc:
            data = json.dumps({"title": "스트림 처리 실패", "message": str(exc)}, ensure_ascii=False)
            yield "event: error\n"
            yield f"data: {data}\n\n"

    return StreamingResponse(encode(), media_type="text/event-stream")
