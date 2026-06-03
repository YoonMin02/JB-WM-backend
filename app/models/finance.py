"""금융 — 포트폴리오 / 보유자산 / 대출 / API-shaped mock data."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.models.base import new_uuid, utcnow


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


class AccountBalance(SQLModel, table=True):
    """정규화된 계좌 잔액 mock DTO.

    원문 `fintech_use_num` 등 provider 식별자는 external_ref에만 두고 agent tool에는 숨긴다.
    """

    id: str = Field(default_factory=new_uuid, primary_key=True)
    customer_id: str = Field(foreign_key="customer.id", index=True)
    bank_name: str
    product_name: str
    account_type: str  # checking, deposit, securities
    balance_krw: Decimal = Decimal(0)
    available_krw: Decimal = Decimal(0)
    issued_on: date | None = None
    matures_on: date | None = None
    last_transaction_on: date | None = None
    external_ref: dict = Field(default_factory=dict, sa_column=Column(JSON))


class AccountTransaction(SQLModel, table=True):
    """정규화된 계좌 거래내역 mock DTO."""

    id: str = Field(default_factory=new_uuid, primary_key=True)
    customer_id: str = Field(foreign_key="customer.id", index=True)
    account_id: str = Field(foreign_key="accountbalance.id", index=True)
    transacted_at: datetime
    direction: str  # in / out
    transaction_type: str
    description: str
    amount_krw: Decimal = Decimal(0)
    after_balance_krw: Decimal = Decimal(0)
    category_hint: str = "uncategorized"
    external_ref: dict = Field(default_factory=dict, sa_column=Column(JSON))


class CardBill(SQLModel, table=True):
    """정규화된 카드 청구 mock DTO."""

    id: str = Field(default_factory=new_uuid, primary_key=True)
    customer_id: str = Field(foreign_key="customer.id", index=True)
    card_name: str
    charge_month: str  # YYYY-MM
    charge_krw: Decimal = Decimal(0)
    settlement_date: date | None = None
    credit_check_type: str = "credit"
    details: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    external_ref: dict = Field(default_factory=dict, sa_column=Column(JSON))


class LoanSwitchPrecheck(SQLModel, table=True):
    """대출이동 사전조회 mock DTO. 실행이 아니라 판단 참고값만 저장한다."""

    id: str = Field(default_factory=new_uuid, primary_key=True)
    customer_id: str = Field(foreign_key="customer.id", index=True)
    loan_id: str = Field(foreign_key="loanaccount.id", index=True)
    repayment_available: bool = False
    denial_code: str | None = None
    prepayment_penalty_krw: Decimal = Decimal(0)
    interest_rate_type: str = "fixed"
    variation_cycle_months: int | None = None
    fixed_rate_apply_months: int | None = None
    external_ref: dict = Field(default_factory=dict, sa_column=Column(JSON))


class AssetEvent(SQLModel, table=True):
    """감지된 자산 신호 — 선제 트리거 (05_DATA_MODEL). 건강과 대칭."""

    id: str = Field(default_factory=new_uuid, primary_key=True)
    customer_id: str = Field(foreign_key="customer.id", index=True)
    kind: str  # portfolio_loss, spending_spike, income_drop, repayment_pressure
    severity: str  # low / mid / high
    detected_at: datetime = Field(default_factory=utcnow)
    raw_ref: dict = Field(default_factory=dict, sa_column=Column(JSON))
