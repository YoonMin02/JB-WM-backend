"""고객 장기 메모리 (개인화)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.models.base import utcnow


class CustomerMemory(SQLModel, table=True):
    customer_id: str = Field(foreign_key="customer.id", primary_key=True)
    # 지불의향 — 1급 개인화 변수 (08_MEMORY). conservative / moderate / aggressive
    medical_willingness: str = "moderate"
    medical_one_time_budget_krw: Decimal = Decimal(0)
    monthly_medical_budget_krw: Decimal = Decimal(0)
    medical_budget_ratio: float = 0.0
    risk_preference: str = "mid"  # low / mid / high
    hospital_preference: str | None = None
    investment_style: str = "balanced"  # stable / balanced / aggressive
    constraints: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=utcnow)
