"""건강 데이터 — 정적 기록 + 감지된 이벤트."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.models.base import new_uuid, utcnow


class HealthRecord(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    customer_id: str = Field(foreign_key="customer.id", index=True)
    source: str  # checkup / device / self_reported
    metric: str  # blood_pressure, sleep_score, bmi, ...
    value: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    measured_at: datetime = Field(default_factory=utcnow)
    consent_id: str | None = None  # 동의 근거 (10_SECURITY_PRIVACY)


class HealthEvent(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    customer_id: str = Field(foreign_key="customer.id", index=True)
    kind: str  # bp_rising, sleep_decline, med_cost_spike
    severity: str  # low / mid / high
    detected_at: datetime = Field(default_factory=utcnow)
    raw_ref: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class MedicalDocument(SQLModel, table=True):
    """고객 제출 객관 문서 — 질병 평가의 앵커 (05_DATA_MODEL, 10).

    주관 진술이 아니라 진단서·검진내역 같은 객관 문서로 판단한다.
    """

    id: str = Field(default_factory=new_uuid, primary_key=True)
    customer_id: str = Field(foreign_key="customer.id", index=True)
    doc_type: str  # diagnosis / checkup / prescription
    issued_at: date | None = None
    summary: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    file_ref: str | None = None
    consent_id: str | None = None
