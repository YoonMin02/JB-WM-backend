"""에이전트 워크플로우 영속화 — 세션·신호·제안·승인·실행·이벤트."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.models.base import new_uuid, utcnow


class AgentSession(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    customer_id: str = Field(foreign_key="customer.id", index=True)
    state: str = "Monitoring"  # 03_STATE_MACHINE 상태값
    active_intents: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    agent_thread_id: str | None = None  # 추론 세션 참조 (어댑터 해석)
    pending_proposal_id: str | None = None
    recent_context: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    failure_reason: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Signal(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    session_id: str = Field(foreign_key="agentsession.id", index=True)
    source: str  # event / user_utterance
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)


class ActionProposal(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    session_id: str = Field(foreign_key="agentsession.id", index=True)
    kind: str  # book_hospital, review_insurance, cashflow_plan, ...
    summary: str
    has_external_effect: bool = False  # Policy 라우팅 입력
    params: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    rationale: str = ""  # 설명가능성
    status: str = "proposed"  # proposed/approved/rejected/deferred/executed/failed
    created_at: datetime = Field(default_factory=utcnow)


class ApprovalDecision(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    proposal_id: str = Field(foreign_key="actionproposal.id", index=True)
    decision: str  # approve / reject / revise
    decided_by: str | None = None  # 고객 id
    note: str = ""
    decided_at: datetime = Field(default_factory=utcnow)


class ActionExecution(SQLModel, table=True):
    """Executor만 생성. LLM/도구가 만들지 않는다."""

    id: str = Field(default_factory=new_uuid, primary_key=True)
    proposal_id: str = Field(foreign_key="actionproposal.id", index=True)
    executor: str
    status: str  # success / failed
    result: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    executed_at: datetime = Field(default_factory=utcnow)


class AgentEvent(SQLModel, table=True):
    """감사 로그 — Signal→Intent→Plan→Approval→Execution 전 구간."""

    id: str = Field(default_factory=new_uuid, primary_key=True)
    session_id: str = Field(foreign_key="agentsession.id", index=True)
    type: str  # state_transition / tool_call / intent / plan / approval / execution
    detail: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
