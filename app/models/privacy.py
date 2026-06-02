"""Privacy and consent records."""
from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.base import utcnow


class ConsentRecord(SQLModel, table=True):
    id: str = Field(primary_key=True)
    customer_id: str = Field(foreign_key="customer.id", index=True)
    scope: str = "health"
    status: str = "active"  # active / revoked
    granted_at: datetime = Field(default_factory=utcnow)
    revoked_at: datetime | None = None
