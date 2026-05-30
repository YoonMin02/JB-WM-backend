"""읽기 전용 데이터 도구 (분류 ① 고객 개인 데이터).

reasoner에 주입할 컨텍스트를 구성한다. 모두 customer_id로 스코핑된 읽기 전용.
실제 배포에서는 이 함수들이 MCP 읽기 서버의 도구로 노출된다 (docs/06_TOOL_CONTRACTS).
실행 동사(book_*/submit_*/transfer_*)는 여기에 존재하지 않는다.
"""
from __future__ import annotations

from sqlmodel import Session, select

from app.models.customer import Customer
from app.models.finance import AssetEvent, Holding, LoanAccount, PortfolioAccount
from app.models.health import HealthEvent, HealthRecord
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
    return {
        # consent 있는 기록만 반환 (10_SECURITY_PRIVACY)
        "records": [
            {"source": r.source, "metric": r.metric, "value": r.value}
            for r in records
            if r.consent_id
        ],
        "events": [{"kind": e.kind, "severity": e.severity} for e in events],
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
                "type": p.policy_type,
                "coverages": [
                    {"coverage_type": it.coverage_type, "limit": float(it.limit_amount), "active": it.active}
                    for it in items
                ],
            }
        )
    # 단순 공백 힌트: 심혈관 특약 미보유 시
    gaps_hint = None if "심혈관특약" in covered_types else "심혈관 특약 없음"
    return {"policies": out, "gaps_hint": gaps_hint}


def get_loan_status(db: Session, customer_id: str) -> dict:
    loans = db.exec(select(LoanAccount).where(LoanAccount.customer_id == customer_id)).all()
    return {
        "loans": [
            {
                "balance": float(loan.balance),
                "next_due_date": loan.next_due_date.isoformat() if loan.next_due_date else None,
                "monthly_payment": float(loan.monthly_payment),
            }
            for loan in loans
        ]
    }


def get_customer_memory(db: Session, customer_id: str) -> dict:
    m = db.get(CustomerMemory, customer_id)
    if not m:
        return {}
    return {
        "medical_willingness": m.medical_willingness,  # 지불의향 (개인화 1급)
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
            {"asset_type": h.asset_type, "risk_grade": h.risk_grade, "weight": h.weight}
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
        "loans": get_loan_status(db, customer_id),
        "portfolio": get_portfolio_summary(db, customer_id),
        "asset_events": get_asset_events(db, customer_id),
        "population": population,
        "memory": get_customer_memory(db, customer_id),
    }
