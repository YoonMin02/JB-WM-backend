"""고객 장기 메모리 (개인화)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.models.base import utcnow


class CustomerMemory(SQLModel, table=True):
    customer_id: str = Field(foreign_key="customer.id", primary_key=True)
    risk_preference: str = "mid"  # low / mid / high
    hospital_preference: str | None = None
    investment_style: str = "balanced"  # stable / balanced / aggressive
    constraints: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=utcnow)
