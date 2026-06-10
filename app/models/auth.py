"""Authentication and notification registration models."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.models.base import new_uuid, utcnow


class UserAccount(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    role: str = Field(index=True)  # customer / advisor / operator
    customer_id: str | None = Field(default=None, foreign_key="customer.id", index=True)
    active: bool = True
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    last_login_at: datetime | None = None


class PushSubscription(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    user_account_id: str = Field(foreign_key="useraccount.id", index=True)
    customer_id: str | None = Field(default=None, foreign_key="customer.id", index=True)
    endpoint: str = Field(index=True)
    p256dh: str
    auth: str
    user_agent: str = ""
    status: str = Field(default="active", index=True)  # active / revoked
    meta: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    last_seen_at: datetime = Field(default_factory=utcnow)
