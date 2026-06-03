"""Mock 시드 데이터 — 김영자(68세) 통합 회복탄력성 데모 시나리오.

혈압 상승 + 수면 악화 + 실손보험(심혈관 특약 없음) + 3개월 뒤 대출 상환.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlmodel import Session, select

from app.core.database import engine
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
from app.models.health import HealthEvent, HealthRecord, MedicalDocument
from app.models.insurance import CoverageItem, InsurancePolicy
from app.models.memory import CustomerMemory
from app.models.privacy import ConsentRecord
from app.models.stats import PopulationStat


def seed_if_empty() -> str | None:
    with Session(engine) as db:
        existing = db.exec(select(Customer)).first()
        if existing:
            return existing.id

        c = Customer(name="김영자", birth_date=date(1958, 3, 12), age_band="65-69", locale="ko")
        db.add(c)
        db.commit()
        db.refresh(c)
        db.add(ConsentRecord(id="consent-1", customer_id=c.id, scope="health", status="active"))

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

        loan = LoanAccount(
            customer_id=c.id, principal=Decimal(30_000_000), balance=Decimal(12_000_000),
            next_due_date=date.today() + timedelta(days=90), monthly_payment=Decimal(800_000),
        )
        db.add(loan)
        db.commit()
        db.refresh(loan)

        # 포트폴리오: 고위험 비중 70% (손실 노출)
        acct = PortfolioAccount(customer_id=c.id, name="JB 종합계좌")
        db.add(acct)
        db.commit()
        db.refresh(acct)
        db.add_all([
            Holding(account_id=acct.id, asset_type="equity", risk_grade="high",
                    amount=Decimal(70_000_000), weight=0.7),
            Holding(account_id=acct.id, asset_type="bond", risk_grade="low",
                    amount=Decimal(30_000_000), weight=0.3),
        ])

        # 자산 신호: 포트폴리오 손실 (선제 트리거)
        db.add(AssetEvent(customer_id=c.id, kind="portfolio_loss", severity="mid",
                          raw_ref={"drawdown_pct": 14, "high_risk_weight": 0.7}))

        checking = AccountBalance(
            customer_id=c.id,
            bank_name="전북은행",
            product_name="JB 주거래통장",
            account_type="checking",
            balance_krw=Decimal(5_800_000),
            available_krw=Decimal(5_800_000),
            issued_on=date(2019, 1, 10),
            last_transaction_on=date.today(),
            external_ref={"provider": "openbanking", "fintech_use_num": "hidden-fin-001"},
        )
        deposit = AccountBalance(
            customer_id=c.id,
            bank_name="전북은행",
            product_name="JB 알뜰정기예금",
            account_type="deposit",
            balance_krw=Decimal(18_000_000),
            available_krw=Decimal(18_000_000),
            issued_on=date(2023, 1, 9),
            matures_on=date.today() + timedelta(days=120),
            last_transaction_on=date.today() - timedelta(days=12),
            external_ref={"provider": "openbanking", "fintech_use_num": "hidden-fin-002"},
        )
        db.add_all([checking, deposit])
        db.commit()
        db.refresh(checking)
        db.refresh(deposit)

        txs: list[AccountTransaction] = []
        running_balance = 8_000_000
        descriptions = [
            ("국민연금", "in", "income", 640_000),
            ("전북대병원", "out", "medical", 180_000),
            ("약국", "out", "medical", 42_000),
            ("관리비", "out", "fixed_cost", 260_000),
            ("통신비", "out", "fixed_cost", 68_000),
            ("마트", "out", "living", 93_000),
            ("보험료", "out", "insurance_premium", 120_000),
            ("대출이자", "out", "loan_repayment", 800_000),
            ("식비", "out", "living", 31_000),
            ("교통", "out", "living", 18_000),
        ]
        for i in range(120):
            desc, direction, category, amount = descriptions[i % len(descriptions)]
            # 최근 3개월 의료비와 고정비가 반복적으로 잡히도록 provider-shaped mock을 정규화한 상태.
            amount_delta = amount + (i % 7) * 3_000
            signed = amount_delta if direction == "in" else -amount_delta
            running_balance += signed
            txs.append(
                AccountTransaction(
                    customer_id=c.id,
                    account_id=checking.id,
                    transacted_at=datetime.now() - timedelta(days=i),
                    direction=direction,
                    transaction_type="cash",
                    description=desc,
                    amount_krw=Decimal(amount_delta),
                    after_balance_krw=Decimal(running_balance),
                    category_hint=category,
                    external_ref={
                        "provider": "openbanking",
                        "api_tran_id": f"mock-api-tran-{i:03d}",
                        "bank_tran_id": f"mock-bank-tran-{i:03d}",
                    },
                )
            )
        db.add_all(txs)

        db.add_all(
            [
                CardBill(
                    customer_id=c.id,
                    card_name="JB 함께카드",
                    charge_month=date.today().strftime("%Y-%m"),
                    charge_krw=Decimal(740_000),
                    settlement_date=date.today() + timedelta(days=18),
                    details=[
                        {"used_on": str(date.today() - timedelta(days=9)), "merchant_name": "전북대병원", "amount_krw": 210000, "category_hint": "medical"},
                        {"used_on": str(date.today() - timedelta(days=5)), "merchant_name": "마트", "amount_krw": 83000, "category_hint": "living"},
                    ],
                    external_ref={"provider": "openbanking", "card_value": "hidden-card-001"},
                ),
                CardBill(
                    customer_id=c.id,
                    card_name="JB 생활카드",
                    charge_month=date.today().strftime("%Y-%m"),
                    charge_krw=Decimal(390_000),
                    settlement_date=date.today() + timedelta(days=24),
                    details=[
                        {"used_on": str(date.today() - timedelta(days=12)), "merchant_name": "약국", "amount_krw": 36000, "category_hint": "medical"},
                        {"used_on": str(date.today() - timedelta(days=3)), "merchant_name": "통신", "amount_krw": 68000, "category_hint": "fixed_cost"},
                    ],
                    external_ref={"provider": "openbanking", "card_value": "hidden-card-002"},
                ),
            ]
        )

        db.add(
            LoanSwitchPrecheck(
                customer_id=c.id,
                loan_id=loan.id,
                repayment_available=True,
                prepayment_penalty_krw=Decimal(0),
                interest_rate_type="fixed",
                fixed_rate_apply_months=12,
                external_ref={"provider": "payinfo", "loan_repayment_id": "hidden-loan-precheck-001"},
            )
        )

        # 객관 의료 문서: 검진 내역 (질병 평가 앵커)
        db.add(MedicalDocument(customer_id=c.id, doc_type="checkup",
                               summary={"blood_pressure": "stage1_htn", "note": "심혈관 추가관찰 권고"},
                               consent_id="consent-1"))

        # 장기 메모리: 지불의향 보수적 + 투자 보류 (개인화)
        db.add(
            CustomerMemory(
                customer_id=c.id, medical_willingness="conservative", risk_preference="low",
                medical_one_time_budget_krw=Decimal(1_500_000),
                monthly_medical_budget_krw=Decimal(250_000),
                medical_budget_ratio=0.08,
                hospital_preference="전북대학교병원", investment_style="stable",
                constraints={"투자": "보류"},
            )
        )

        # 통계 시드 (분류 ② — 근거 앵커. 실제 출처는 STATS_SOURCES)
        db.add_all([
            PopulationStat(age_band="65-69", metric="avg_net_assets",
                           value={"krw": 250_000_000}, source="KOSIS 가계금융복지조사", as_of="2024"),
            PopulationStat(age_band="65-69", metric="avg_emergency_fund_months",
                           value={"months": 6}, source="KOSIS", as_of="2024"),
            PopulationStat(age_band="65-69", metric="cardio_prevalence",
                           value={"pct": 38}, source="KNHANES", as_of="2023"),
        ])
        db.commit()
        return c.id
