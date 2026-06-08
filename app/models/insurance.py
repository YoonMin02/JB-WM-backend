"""보험 — 증권 + 보장 항목."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.models.base import new_uuid


class InsurancePolicy(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    customer_id: str = Field(foreign_key="customer.id", index=True)
    product_name: str
    policy_type: str  # 실손, 종신, 건강 ...
    active: bool = True
    external_ref: dict = Field(default_factory=dict, sa_column=Column(JSON))


class CoverageItem(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    policy_id: str = Field(foreign_key="insurancepolicy.id", index=True)
    coverage_type: str  # 실손, 암, 심혈관특약 ...
    limit_amount: Decimal = Decimal(0)
    active: bool = True
    external_ref: dict = Field(default_factory=dict, sa_column=Column(JSON))
