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
    active_needs: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
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
    """감사 로그 — Signal→NeedAssessment→Plan→Approval→Execution 전 구간."""

    id: str = Field(default_factory=new_uuid, primary_key=True)
    session_id: str = Field(foreign_key="agentsession.id", index=True)
    type: str  # state_transition / tool_call / need_assessment / plan / approval / execution
    detail: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)


class AgentMessage(SQLModel, table=True):
    """전문/대화 원본 저장. UI 타임라인과 분리된 append-only 기록."""

    id: str = Field(default_factory=new_uuid, primary_key=True)
    session_id: str = Field(foreign_key="agentsession.id", index=True)
    role: str  # user / system / assistant / tool
    content: str
    meta: dict[str, Any] = Field(default_factory=dict, sa_column=Column("metadata", JSON))
    created_at: datetime = Field(default_factory=utcnow)


class NeedAssessmentRecord(SQLModel, table=True):
    """AssessNeed 구조화 결과 저장. compact와 무관한 재현/감사용 기록."""

    id: str = Field(default_factory=new_uuid, primary_key=True)
    session_id: str = Field(foreign_key="agentsession.id", index=True)
    needs: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    primary_need: str = "none"
    confidence: float = 0.0
    rationale: str = ""
    raw_output: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)


class PlanRecord(SQLModel, table=True):
    """GeneratePlan 구조화 결과 저장. ActionProposal N건과 함께 추적한다."""

    id: str = Field(default_factory=new_uuid, primary_key=True)
    session_id: str = Field(foreign_key="agentsession.id", index=True)
    explanation: str = ""
    raw_output: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    proposal_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
