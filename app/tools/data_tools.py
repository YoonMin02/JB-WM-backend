"""읽기 전용 데이터 도구 (분류 ① 고객 개인 데이터).

reasoner에 주입할 컨텍스트를 구성한다. 모두 customer_id로 스코핑된 읽기 전용.
실제 배포에서는 이 함수들이 backend ContextBuilder를 통해 LLM context pack에 주입된다.
실행 동사(book_*/submit_*/transfer_*)는 여기에 존재하지 않는다.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import Session, select

from app.models.customer import Customer
from app.models.finance import (
    AccountBalance,
    AccountTransaction,
    AssetEvent,
    CardBill,
    Holding,
    LoanAccount,
    LoanSwitchPrecheck,
    PortfolioAccount,
)
from app.models.health import HealthEvent, HealthRecord
from app.models.health import MedicalDocument
from app.models.insurance import CoverageItem, InsurancePolicy
from app.models.memory import CustomerMemory
from app.models.stats import PopulationStat


def get_customer_profile(db: Session, customer_id: str) -> dict:
    c = db.get(Customer, customer_id)
    if not c:
        return {}
    return {"id": c.id, "name": c.name, "age_band": c.age_band, "locale": c.locale}


def get_health_data(db: Session, customer_id: str) -> dict:
    records = db.exec(select(HealthRecord).where(HealthRecord.customer_id == customer_id)).all()
    events = db.exec(select(HealthEvent).where(HealthEvent.customer_id == customer_id)).all()
    docs = db.exec(select(MedicalDocument).where(MedicalDocument.customer_id == customer_id)).all()
    return {
        # consent 있는 기록만 반환 (10_SECURITY_PRIVACY)
        "records": [
            {
                "source": r.source,
                "metric": r.metric,
                "value": r.value,
                "measured_at": r.measured_at.isoformat(),
            }
            for r in records
            if r.consent_id
        ],
        "events": [
            {"kind": e.kind, "severity": e.severity, "detected_at": e.detected_at.isoformat(), "raw_ref": e.raw_ref}
            for e in events
        ],
        "documents": [
            {
                "doc_type": d.doc_type,
                "issued_at": d.issued_at.isoformat() if d.issued_at else None,
                "summary": d.summary,
            }
            for d in docs
            if d.consent_id
        ],
    }


def get_insurance_summary(db: Session, customer_id: str) -> dict:
    policies = db.exec(
        select(InsurancePolicy).where(InsurancePolicy.customer_id == customer_id)
    ).all()
    out = []
    covered_types: set[str] = set()
    for p in policies:
        items = db.exec(select(CoverageItem).where(CoverageItem.policy_id == p.id)).all()
        for it in items:
            if it.active:
                covered_types.add(it.coverage_type)
        out.append(
            {
                "product_name": p.product_name,
                "type": p.policy_type,
                "active": p.active,
                "coverages": [
                    {"coverage_type": it.coverage_type, "limit": float(it.limit_amount), "active": it.active}
                    for it in items
                ],
            }
        )
    # 단순 공백 힌트: 심혈관 특약 미보유 시
    has_cardio = "심혈관특약" in covered_types or "심혈관" in covered_types
    gaps_hint = None if has_cardio else "심혈관 특약 없음"
    return {"policies": out, "gaps_hint": gaps_hint}


def get_loan_status(db: Session, customer_id: str) -> dict:
    loans = db.exec(select(LoanAccount).where(LoanAccount.customer_id == customer_id)).all()
    return {
        "loans": [
            {
                "balance": float(loan.balance),
                "principal": float(loan.principal),
                "next_due_date": loan.next_due_date.isoformat() if loan.next_due_date else None,
                "monthly_payment": float(loan.monthly_payment),
            }
            for loan in loans
        ]
    }


def get_account_balances(db: Session, customer_id: str) -> dict:
    accounts = db.exec(select(AccountBalance).where(AccountBalance.customer_id == customer_id)).all()
    available_cash = sum(float(a.available_krw) for a in accounts if a.account_type in {"checking", "deposit"})
    monthly_outflow = _monthly_outflow_krw(db, customer_id)
    emergency_months = round(available_cash / monthly_outflow, 2) if monthly_outflow else None
    return {
        "accounts": [
            {
                "account_id": a.id,
                "bank_name": a.bank_name,
                "product_name": a.product_name,
                "account_type": a.account_type,
                "balance_krw": int(a.balance_krw),
                "available_krw": int(a.available_krw),
                "last_transaction_on": a.last_transaction_on.isoformat() if a.last_transaction_on else None,
            }
            for a in accounts
        ],
        "liquidity_summary": {
            "available_cash_krw": int(available_cash),
            "emergency_fund_months": emergency_months,
        },
    }


def get_account_transactions(
    db: Session,
    customer_id: str,
    from_date: date | None = None,
    to_date: date | None = None,
) -> dict:
    from_date = from_date or (date.today() - timedelta(days=90))
    to_date = to_date or date.today()
    rows = db.exec(
        select(AccountTransaction)
        .where(AccountTransaction.customer_id == customer_id)
        .order_by(AccountTransaction.transacted_at.desc())
    ).all()
    rows = [r for r in rows if from_date <= r.transacted_at.date() <= to_date]
    visible = rows[:30]
    monthly_outflow = _monthly_outflow_krw(db, customer_id, rows)
    medical_spending = sum(float(r.amount_krw) for r in rows if r.direction == "out" and r.category_hint == "medical")
    fixed_cost = sum(float(r.amount_krw) for r in rows if r.direction == "out" and r.category_hint == "fixed_cost")
    return {
        "transactions": [
            {
                "transacted_at": r.transacted_at.isoformat(),
                "direction": r.direction,
                "description": r.description,
                "amount_krw": int(r.amount_krw),
                "category_hint": r.category_hint,
            }
            for r in visible
        ],
        "spending_summary": {
            "monthly_outflow_krw": int(monthly_outflow),
            "medical_spending_krw": int(medical_spending),
            "fixed_cost_krw": int(fixed_cost),
            "record_count": len(rows),
        },
    }


def get_card_bills(db: Session, customer_id: str) -> dict:
    bills = db.exec(select(CardBill).where(CardBill.customer_id == customer_id)).all()
    upcoming = sum(float(b.charge_krw) for b in bills)
    return {
        "bills": [
            {
                "card_name": b.card_name,
                "charge_month": b.charge_month,
                "charge_krw": int(b.charge_krw),
                "settlement_date": b.settlement_date.isoformat() if b.settlement_date else None,
                "medical_charge_krw": int(
                    sum(item.get("amount_krw", 0) for item in b.details if item.get("category_hint") == "medical")
                ),
            }
            for b in bills
        ],
        "upcoming_card_payment_krw": int(upcoming),
    }


def get_loan_switch_precheck(db: Session, customer_id: str, loan_id: str | None = None) -> dict:
    query = select(LoanSwitchPrecheck).where(LoanSwitchPrecheck.customer_id == customer_id)
    if loan_id:
        query = query.where(LoanSwitchPrecheck.loan_id == loan_id)
    row = db.exec(query).first()
    if not row:
        return {}
    return {
        "loan_id": row.loan_id,
        "repayment_available": row.repayment_available,
        "prepayment_penalty_krw": int(row.prepayment_penalty_krw),
        "note": "사전조회 mock 결과입니다. 실제 대환 실행은 고객 승인 후 Executor 영역입니다.",
    }


def get_customer_memory(db: Session, customer_id: str) -> dict:
    m = db.get(CustomerMemory, customer_id)
    if not m:
        return {}
    return {
        "medical_willingness": m.medical_willingness,  # 지불의향 (개인화 1급)
        "medical_one_time_budget_krw": int(m.medical_one_time_budget_krw),
        "monthly_medical_budget_krw": int(m.monthly_medical_budget_krw),
        "medical_budget_ratio": m.medical_budget_ratio,
        "risk_preference": m.risk_preference,
        "hospital_preference": m.hospital_preference,
        "investment_style": m.investment_style,
        "constraints": m.constraints,
    }


def get_portfolio_summary(db: Session, customer_id: str) -> dict:
    accts = db.exec(select(PortfolioAccount).where(PortfolioAccount.customer_id == customer_id)).all()
    holdings: list[Holding] = []
    for a in accts:
        holdings += db.exec(select(Holding).where(Holding.account_id == a.id)).all()
    total = sum(float(h.amount) for h in holdings)
    high_risk_weight = sum(h.weight for h in holdings if h.risk_grade == "high")
    return {
        "total_value": total,
        "allocation": [
            {"asset_type": h.asset_type, "risk_grade": h.risk_grade, "amount_krw": int(h.amount), "weight": h.weight}
            for h in holdings
        ],
        "high_risk_weight": high_risk_weight,
    }


def get_asset_events(db: Session, customer_id: str) -> dict:
    events = db.exec(select(AssetEvent).where(AssetEvent.customer_id == customer_id)).all()
    return {"events": [{"kind": e.kind, "severity": e.severity, "raw_ref": e.raw_ref} for e in events]}


def get_population_stat(db: Session, age_band: str, metric: str) -> dict:
    """② 통계/기준 — 파라미터 쿼리 (RAG 아님). 출처·기준시점 동반."""
    row = db.exec(
        select(PopulationStat).where(
            PopulationStat.age_band == age_band, PopulationStat.metric == metric
        )
    ).first()
    if not row:
        return {}
    return {"value": row.value, "source": row.source, "as_of": row.as_of}


def build_context(db: Session, customer_id: str) -> dict:
    """reasoner 주입용 읽기 전용 컨텍스트 묶음 (건강·자산 통합)."""
    profile = get_customer_profile(db, customer_id)
    age_band = profile.get("age_band", "")
    # 해당 연령대 통계 일부를 근거로 동봉 (분류 ②)
    population = {
        m: get_population_stat(db, age_band, m)
        for m in ("avg_net_assets", "avg_emergency_fund_months", "cardio_prevalence")
    }
    return {
        "customer_id": customer_id,
        "profile": profile,
        "health": get_health_data(db, customer_id),
        "insurance": get_insurance_summary(db, customer_id),
        "accounts": get_account_balances(db, customer_id),
        "transactions": get_account_transactions(db, customer_id),
        "card_bills": get_card_bills(db, customer_id),
        "loans": get_loan_status(db, customer_id),
        "loan_switch_precheck": get_loan_switch_precheck(db, customer_id),
        "portfolio": get_portfolio_summary(db, customer_id),
        "asset_events": get_asset_events(db, customer_id),
        "population": population,
        "memory": get_customer_memory(db, customer_id),
    }


def get_customer_detail_snapshot(db: Session, customer_id: str) -> dict:
    """프론트 상세 보기용 mock 원문 스냅샷.

    LLM context pack에는 provider 식별자를 숨기지만, 데모 UI에서는 `docs/APIs` body shape를
    확인할 수 있도록 DB의 mock 원문 응답을 별도 endpoint로 노출한다.
    """
    policies = db.exec(select(InsurancePolicy).where(InsurancePolicy.customer_id == customer_id)).all()
    accounts = db.exec(select(AccountBalance).where(AccountBalance.customer_id == customer_id)).all()
    transactions = db.exec(
        select(AccountTransaction)
        .where(AccountTransaction.customer_id == customer_id)
        .order_by(AccountTransaction.transacted_at.desc())
    ).all()
    cards = db.exec(select(CardBill).where(CardBill.customer_id == customer_id)).all()
    loans = db.exec(select(LoanAccount).where(LoanAccount.customer_id == customer_id)).all()
    prechecks = db.exec(select(LoanSwitchPrecheck).where(LoanSwitchPrecheck.customer_id == customer_id)).all()
    health_records = db.exec(select(HealthRecord).where(HealthRecord.customer_id == customer_id)).all()
    health_events = db.exec(select(HealthEvent).where(HealthEvent.customer_id == customer_id)).all()
    medical_docs = db.exec(select(MedicalDocument).where(MedicalDocument.customer_id == customer_id)).all()
    portfolio_accounts = db.exec(select(PortfolioAccount).where(PortfolioAccount.customer_id == customer_id)).all()
    holdings: list[Holding] = []
    for account in portfolio_accounts:
        holdings += db.exec(select(Holding).where(Holding.account_id == account.id)).all()

    insurance_details = []
    for policy in policies:
        coverages = db.exec(select(CoverageItem).where(CoverageItem.policy_id == policy.id)).all()
        insurance_details.append(
            {
                "normalized": {
                    "product_name": policy.product_name,
                    "policy_type": policy.policy_type,
                    "active": policy.active,
                    "coverages": [
                        {
                            "coverage_type": item.coverage_type,
                            "limit_amount": int(item.limit_amount),
                            "active": item.active,
                            "api_body": item.external_ref.get("api_body", {}),
                        }
                        for item in coverages
                    ],
                },
                "api_body": policy.external_ref.get("api_body", {}),
                "payment_api_body": policy.external_ref.get("payment_api_body", {}),
            }
        )

    return {
        "health": {
            "records": [
                {
                    "source": row.source,
                    "metric": row.metric,
                    "value": row.value,
                    "measured_at": row.measured_at.isoformat(),
                }
                for row in health_records
                if row.consent_id
            ],
            "events": [
                {
                    "kind": row.kind,
                    "severity": row.severity,
                    "detected_at": row.detected_at.isoformat(),
                    "raw_ref": row.raw_ref,
                }
                for row in health_events
            ],
            "medical_documents": [
                {
                    "doc_type": row.doc_type,
                    "issued_at": row.issued_at.isoformat() if row.issued_at else None,
                    "summary": row.summary,
                }
                for row in medical_docs
                if row.consent_id
            ],
        },
        "insurance": insurance_details,
        "accounts": [
            {
                "normalized": {
                    "bank_name": row.bank_name,
                    "product_name": row.product_name,
                    "account_type": row.account_type,
                    "balance_krw": int(row.balance_krw),
                    "available_krw": int(row.available_krw),
                },
                "api_body": row.external_ref.get("api_body", {}),
            }
            for row in accounts
        ],
        "transactions": {
            "api_body": {
                **(transactions[0].external_ref.get("api_body_header", {}) if transactions else {}),
                "res_list": [row.external_ref.get("api_body", {}) for row in transactions[:80]],
            }
        },
        "cards": [
            {
                "normalized": {
                    "card_name": row.card_name,
                    "charge_month": row.charge_month,
                    "charge_krw": int(row.charge_krw),
                    "settlement_date": row.settlement_date.isoformat() if row.settlement_date else None,
                },
                "card_list_api_body": row.external_ref.get("card_list_api_body", {}),
                "card_issue_api_body": row.external_ref.get("card_issue_api_body", {}),
                "bill_basic_api_body": row.external_ref.get("bill_basic_api_body", {}),
                "bill_detail_api_body": row.external_ref.get("bill_detail_api_body", {}),
            }
            for row in cards
        ],
        "loans": [
            {
                "normalized": {
                    "principal": int(row.principal),
                    "balance": int(row.balance),
                    "monthly_payment": int(row.monthly_payment),
                    "next_due_date": row.next_due_date.isoformat() if row.next_due_date else None,
                }
            }
            for row in loans
        ],
        "loan_switch_prechecks": [
            {
                "normalized": {
                    "loan_id": row.loan_id,
                    "repayment_available": row.repayment_available,
                    "prepayment_penalty_krw": int(row.prepayment_penalty_krw),
                    "interest_rate_type": row.interest_rate_type,
                    "variation_cycle_months": row.variation_cycle_months,
                    "fixed_rate_apply_months": row.fixed_rate_apply_months,
                },
                "api_body": row.external_ref.get("api_body", {}),
            }
            for row in prechecks
        ],
        "portfolio": {
            "accounts": [{"id": row.id, "name": row.name} for row in portfolio_accounts],
            "holdings": [
                {
                    "asset_type": row.asset_type,
                    "risk_grade": row.risk_grade,
                    "amount_krw": int(row.amount),
                    "weight": row.weight,
                }
                for row in holdings
            ],
        },
    }


def _monthly_outflow_krw(
    db: Session,
    customer_id: str,
    rows: list[AccountTransaction] | None = None,
) -> float:
    rows = rows if rows is not None else db.exec(
        select(AccountTransaction).where(AccountTransaction.customer_id == customer_id)
    ).all()
    outflow = sum(float(r.amount_krw) for r in rows if r.direction == "out")
    return outflow / 3 if rows else 0.0
