"""고객 엔티티."""
from __future__ import annotations

from datetime import date, datetime

from sqlmodel import Field, SQLModel

from app.models.base import new_uuid, utcnow


class Customer(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    name: str
    birth_date: date
    age_band: str = Field(index=True)  # "65-69" 등 — 통계 조회 키
    locale: str = "ko"
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
