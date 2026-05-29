"""Mock 시드 데이터 — 김영자(68세) 슬라이스 1 시나리오.

혈압 상승 + 수면 악화 + 실손보험(심혈관 특약 없음) + 3개월 뒤 대출 상환.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlmodel import Session, select

from app.core.database import engine
from app.models.customer import Customer
from app.models.finance import LoanAccount
from app.models.health import HealthEvent, HealthRecord
from app.models.insurance import CoverageItem, InsurancePolicy
from app.models.memory import CustomerMemory


def seed_if_empty() -> str | None:
    with Session(engine) as db:
        existing = db.exec(select(Customer)).first()
        if existing:
            return existing.id

        c = Customer(name="김영자", birth_date=date(1958, 3, 12), age_band="65-69", locale="ko")
        db.add(c)
        db.commit()
        db.refresh(c)

        db.add_all(
            [
                HealthRecord(
                    customer_id=c.id, source="checkup", metric="blood_pressure",
                    value={"systolic": 152, "diastolic": 96}, consent_id="consent-1",
                ),
                HealthRecord(
                    customer_id=c.id, source="device", metric="sleep_score",
                    value={"score": 58}, consent_id="consent-1",
                ),
                HealthEvent(customer_id=c.id, kind="bp_rising", severity="mid",
                            raw_ref={"metric": "blood_pressure"}),
                HealthEvent(customer_id=c.id, kind="sleep_decline", severity="low",
                            raw_ref={"metric": "sleep_score"}),
            ]
        )

        policy = InsurancePolicy(customer_id=c.id, product_name="JB 실손의료보험", policy_type="실손")
        db.add(policy)
        db.commit()
        db.refresh(policy)
        db.add(
            CoverageItem(policy_id=policy.id, coverage_type="실손", limit_amount=Decimal(50_000_000), active=True)
        )
        # 심혈관특약 없음 → gaps_hint 발생

        db.add(
            LoanAccount(
                customer_id=c.id, principal=Decimal(30_000_000), balance=Decimal(12_000_000),
                next_due_date=date.today() + timedelta(days=90), monthly_payment=Decimal(800_000),
            )
        )

        db.add(
            CustomerMemory(
                customer_id=c.id, risk_preference="low", hospital_preference="전북대학교병원",
                investment_style="stable", constraints={"투자": "보류"},
            )
        )
        db.commit()
        return c.id
