"""금융 — 포트폴리오 / 보유자산 / 대출."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlmodel import Field, SQLModel

from app.models.base import new_uuid


class PortfolioAccount(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    customer_id: str = Field(foreign_key="customer.id", index=True)
    name: str


class Holding(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    account_id: str = Field(foreign_key="portfolioaccount.id", index=True)
    asset_type: str  # equity, bond, cash, fund
    risk_grade: str  # low / mid / high
    amount: Decimal = Decimal(0)
    weight: float = 0.0


class LoanAccount(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    customer_id: str = Field(foreign_key="customer.id", index=True)
    principal: Decimal = Decimal(0)
    balance: Decimal = Decimal(0)
    next_due_date: date | None = None
    monthly_payment: Decimal = Decimal(0)
