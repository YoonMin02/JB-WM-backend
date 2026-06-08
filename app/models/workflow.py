"""LangGraph redesign persistence models.

These tables keep customer/thread ownership and agent-job artifacts outside the
LLM process. They are deliberately small so they can coexist with legacy
AgentSession/ActionProposal tables during migration.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.models.base import new_uuid, utcnow


class AgentThread(SQLModel, table=True):
    graph_thread_id: str = Field(default_factory=new_uuid, primary_key=True)
    tenant_id: str = "jbwm"
    customer_id: str = Field(foreign_key="customer.id", index=True)
    agent_session_id: str = Field(foreign_key="agentsession.id", index=True)
    created_by_principal_id: str = ""
    scope_hash: str = ""
    status: str = "active"
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class DataSnapshot(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    graph_thread_id: str = Field(foreign_key="agentthread.graph_thread_id", index=True)
    customer_id: str = Field(foreign_key="customer.id", index=True)
    context: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    context_hash: str = ""
    redaction_version: str = "v1"
    created_at: datetime = Field(default_factory=utcnow)


class AgentJob(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    graph_thread_id: str = Field(foreign_key="agentthread.graph_thread_id", index=True)
    customer_id: str = Field(foreign_key="customer.id", index=True)
    data_snapshot_id: str = Field(foreign_key="datasnapshot.id", index=True)
    mode: str = "local_stub"
    status: str = "queued"
    input_path: str = ""
    output_path: str = ""
    result: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
