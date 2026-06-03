"""고객 도메인 데이터 조회 (프론트 표시용)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.deps import current_principal, db_session
from app.core.auth import Principal, require_customer_access
from app.models.customer import Customer
from app.tools import data_tools

router = APIRouter(prefix="/customers", tags=["customers"])


def _authorize(principal: Principal, customer_id: str) -> None:
    if isinstance(principal, Principal):
        require_customer_access(principal, customer_id)


@router.get("")
def list_customers(db: Session = Depends(db_session)) -> list[dict]:
    rows = db.exec(select(Customer)).all()
    return [{"id": c.id, "name": c.name, "age_band": c.age_band} for c in rows]


@router.get("/{customer_id}")
def get_customer(
    customer_id: str,
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> dict:
    _authorize(principal, customer_id)
    profile = data_tools.get_customer_profile(db, customer_id)
    if not profile:
        raise HTTPException(404, "고객을 찾을 수 없습니다.")
    return profile


@router.get("/{customer_id}/health")
def customer_health(
    customer_id: str,
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> dict:
    _authorize(principal, customer_id)
    return data_tools.get_health_data(db, customer_id)


@router.get("/{customer_id}/insurance")
def customer_insurance(
    customer_id: str,
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> dict:
    _authorize(principal, customer_id)
    return data_tools.get_insurance_summary(db, customer_id)


@router.get("/{customer_id}/portfolio")
def customer_portfolio(
    customer_id: str,
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> dict:
    _authorize(principal, customer_id)
    return data_tools.get_portfolio_summary(db, customer_id)


@router.get("/{customer_id}/loans")
def customer_loans(
    customer_id: str,
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> dict:
    _authorize(principal, customer_id)
    return data_tools.get_loan_status(db, customer_id)


@router.get("/{customer_id}/accounts")
def customer_accounts(
    customer_id: str,
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> dict:
    _authorize(principal, customer_id)
    return data_tools.get_account_balances(db, customer_id)


@router.get("/{customer_id}/transactions")
def customer_transactions(
    customer_id: str,
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> dict:
    _authorize(principal, customer_id)
    return data_tools.get_account_transactions(db, customer_id)


@router.get("/{customer_id}/card-bills")
def customer_card_bills(
    customer_id: str,
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> dict:
    _authorize(principal, customer_id)
    return data_tools.get_card_bills(db, customer_id)


@router.get("/{customer_id}/loan-switch-precheck")
def customer_loan_switch_precheck(
    customer_id: str,
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> dict:
    _authorize(principal, customer_id)
    return data_tools.get_loan_switch_precheck(db, customer_id)


@router.get("/{customer_id}/memory")
def customer_memory(
    customer_id: str,
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> dict:
    _authorize(principal, customer_id)
    return data_tools.get_customer_memory(db, customer_id)
