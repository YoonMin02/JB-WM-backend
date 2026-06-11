"""Mock 시드 데이터 — 김영자(68세) 통합 회복탄력성 데모 시나리오.

혈압 상승 + 수면 악화 + 실손보험(심혈관 특약 없음) + 3개월 뒤 대출 상환.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlmodel import Session, select

from app.core.database import engine
from app.core.auth import hash_password
from app.models.auth import UserAccount
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


MOCK_DATA_PATH = Path(__file__).resolve().parent / "mock_data" / "demo_customers.json"


def seed_if_empty() -> str | None:
    with Session(engine) as db:
        existing = db.exec(select(Customer)).first()
        if existing:
            _seed_additional_customers(db)
            _seed_demo_accounts(db)
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

        # 통계 시드 (분류 ② — 근거 앵커)
        db.add_all([
            PopulationStat(age_band="65-69", metric="avg_net_assets",
                           value={"krw": 250_000_000}, source="KOSIS 가계금융복지조사", as_of="2024"),
            PopulationStat(age_band="65-69", metric="avg_emergency_fund_months",
                           value={"months": 6}, source="KOSIS", as_of="2024"),
            PopulationStat(age_band="65-69", metric="cardio_prevalence",
                           value={"pct": 38}, source="KNHANES", as_of="2023"),
        ])
        db.commit()
        _seed_additional_customers(db)
        _seed_demo_accounts(db)
        return c.id


def _seed_demo_accounts(db: Session) -> None:
    """Create deterministic demo login accounts for operator and seeded customers."""

    operator = db.exec(select(UserAccount).where(UserAccount.email == "operator@jbwm.local")).first()
    if operator is None:
        operator = UserAccount(
            email="operator@jbwm.local",
            password_hash=hash_password("operator1234"),
            role="operator",
            customer_id=None,
        )
    else:
        operator.password_hash = hash_password("operator1234")
        operator.role = "operator"
        operator.customer_id = None
        operator.active = True
    db.add(operator)

    customers = db.exec(select(Customer).order_by(Customer.created_at)).all()
    for idx, customer in enumerate(customers, start=1):
        email = f"customer{idx:02d}@jbwm.local"
        account = db.exec(select(UserAccount).where(UserAccount.email == email)).first()
        if account is None:
            account = UserAccount(
                email=email,
                password_hash=hash_password("customer1234"),
                role="customer",
                customer_id=customer.id,
            )
        else:
            account.password_hash = hash_password("customer1234")
            account.role = "customer"
            account.customer_id = customer.id
            account.active = True
        db.add(account)
    db.commit()


def _seed_additional_customers(db: Session) -> None:
    """로그인/시나리오 선택용 추가 데모 고객.

    기존 김영자는 상세 테스트 기준으로 유지하고, 나머지는 화면 데모에 필요한 최소 정규화 데이터를
    채운다. 이미 같은 이름이 있으면 건너뛴다.
    """
    specs = _load_demo_customer_specs()

    for idx, spec in enumerate(specs, start=2):
        name = spec["name"]
        age_band = spec["age_band"]
        scenario = spec["scenario"]
        high_risk = float(spec["portfolio"]["high_risk_weight"])
        gap = spec["insurance"].get("gap_hint")
        willingness = spec["memory"]["medical_willingness"]
        style = spec["memory"]["investment_style"]
        customer = db.exec(select(Customer).where(Customer.name == name)).first()
        if customer:
            _clear_demo_customer_domain_data(db, customer.id)
            customer.birth_date = date.fromisoformat(spec["birth_date"])
            customer.age_band = age_band
            customer.locale = "ko"
            db.add(customer)
            db.commit()
            db.refresh(customer)
        else:
            customer = Customer(
                name=name,
                birth_date=date.fromisoformat(spec["birth_date"]),
                age_band=age_band,
                locale="ko",
            )
            db.add(customer)
            db.commit()
            db.refresh(customer)

        consent_id = f"consent-{idx}"
        consent = db.get(ConsentRecord, consent_id)
        if consent is None:
            db.add(ConsentRecord(id=consent_id, customer_id=customer.id, scope="health", status="active"))
        else:
            consent.customer_id = customer.id
            consent.status = "active"
            db.add(consent)
        db.add_all(
            [
                HealthRecord(
                    customer_id=customer.id,
                    source="checkup",
                    metric="blood_pressure",
                    value=spec["health"]["blood_pressure"],
                    consent_id=consent_id,
                ),
                HealthRecord(
                    customer_id=customer.id,
                    source="checkup",
                    metric="ldl_cholesterol",
                    value=spec["health"]["ldl_cholesterol"],
                    consent_id=consent_id,
                ),
                HealthRecord(
                    customer_id=customer.id,
                    source="device",
                    metric="sleep_score",
                    value=spec["health"]["sleep_score"],
                    consent_id=consent_id,
                ),
                HealthEvent(
                    customer_id=customer.id,
                    kind="bp_rising" if "health" in scenario or scenario == "bp_rising" else "routine_check",
                    severity="mid" if "health" in scenario or scenario == "bp_rising" else "low",
                    raw_ref=spec["health"]["event_ref"],
                ),
            ]
        )

        for policy_spec in spec["insurance"]["policies"]:
            policy = InsurancePolicy(
                customer_id=customer.id,
                product_name=policy_spec["product_name"],
                policy_type=policy_spec["policy_type"],
                active=policy_spec["active"],
                external_ref={
                    "api_body": _insurance_list_item(idx, policy_spec),
                    "payment_api_body": _insurance_payment_body(idx, policy_spec),
                },
            )
            db.add(policy)
            db.commit()
            db.refresh(policy)
            for coverage in policy_spec["coverages"]:
                db.add(
                    CoverageItem(
                        policy_id=policy.id,
                        coverage_type=coverage["coverage_type"],
                        limit_amount=Decimal(coverage["limit_amount"]),
                        active=coverage["active"],
                        external_ref={"api_body": coverage},
                    )
                )

        loan = LoanAccount(
            customer_id=customer.id,
            principal=Decimal(spec["loan"]["principal"]),
            balance=Decimal(spec["loan"]["balance"]),
            next_due_date=date.today() + timedelta(days=int(spec["loan"]["next_due_in_days"])),
            monthly_payment=Decimal(spec["loan"]["monthly_payment"]),
        )
        db.add(loan)
        db.commit()
        db.refresh(loan)

        account = PortfolioAccount(customer_id=customer.id, name=f"JB 데모계좌 {idx}")
        db.add(account)
        db.commit()
        db.refresh(account)
        total = Decimal(spec["portfolio"]["total_value"])
        for holding in spec["portfolio"]["holdings"]:
            db.add(
                Holding(
                    account_id=account.id,
                    asset_type=holding["asset_type"],
                    risk_grade=holding["risk_grade"],
                    amount=total * Decimal(str(holding["weight"])),
                    weight=float(holding["weight"]),
                )
            )

        db.add(
            AssetEvent(
                customer_id=customer.id,
                kind=scenario,
                severity="high" if high_risk >= 0.65 else "mid",
                raw_ref=spec["portfolio"]["event_ref"],
            )
        )

        account_rows: list[AccountBalance] = []
        for account_spec in spec["accounts"]:
            row = AccountBalance(
                customer_id=customer.id,
                bank_name=account_spec["bank_name"],
                product_name=account_spec["product_name"],
                account_type=account_spec["account_type"],
                balance_krw=Decimal(account_spec["balance_krw"]),
                available_krw=Decimal(account_spec["available_krw"]),
                issued_on=date.fromisoformat(account_spec["issued_on"]),
                matures_on=date.fromisoformat(account_spec["matures_on"]) if account_spec.get("matures_on") else None,
                last_transaction_on=date.today(),
                external_ref={"provider": "openbanking", "api_body": _account_balance_body(idx, account_spec)},
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            account_rows.append(row)
        checking = account_rows[0]

        txs: list[AccountTransaction] = []
        tx_pattern = spec["transactions"]
        for i in range(100):
            pattern = tx_pattern[i % len(tx_pattern)]
            direction = pattern["direction"]
            category = pattern["category_hint"]
            amount = int(pattern["amount_krw"]) + (i % 6) * 2_000
            after_balance = int(spec["accounts"][0]["balance_krw"]) - i * 18_000
            transacted_at = datetime.now() - timedelta(days=i)
            txs.append(
                AccountTransaction(
                    customer_id=customer.id,
                    account_id=checking.id,
                    transacted_at=transacted_at,
                    direction=direction,
                    transaction_type=pattern["transaction_type"],
                    description=pattern["description"],
                    amount_krw=Decimal(amount),
                    after_balance_krw=Decimal(after_balance),
                    category_hint=category,
                    external_ref={
                        "provider": "openbanking",
                        "api_body_header": _transaction_header_body(idx, account_spec=spec["accounts"][0]),
                        "api_body": _transaction_item_body(transacted_at, pattern, amount, after_balance),
                    },
                )
            )
        db.add_all(txs)

        for card_idx, card in enumerate(spec["cards"], start=1):
            db.add(
                CardBill(
                    customer_id=customer.id,
                    card_name=card["card_name"],
                    charge_month=date.today().strftime("%Y-%m"),
                    charge_krw=Decimal(card["charge_krw"]),
                    settlement_date=date.today() + timedelta(days=int(card["settlement_in_days"])),
                    credit_check_type=card["credit_check_type"],
                    details=card["details"],
                    external_ref={
                        "provider": "openbanking",
                        "card_list_api_body": _card_list_item(idx, card_idx, card),
                        "card_issue_api_body": _card_issue_body(idx, card_idx, card),
                        "bill_basic_api_body": _card_bill_basic_body(idx, card_idx, card),
                        "bill_detail_api_body": _card_bill_detail_body(idx, card_idx, card),
                    },
                )
            )
        db.add(
            LoanSwitchPrecheck(
                customer_id=customer.id,
                loan_id=loan.id,
                repayment_available=True,
                prepayment_penalty_krw=Decimal(spec["loan"]["prepayment_penalty_krw"]),
                interest_rate_type=spec["loan"]["interest_rate_type"],
                variation_cycle_months=spec["loan"].get("variation_cycle_months"),
                fixed_rate_apply_months=spec["loan"].get("fixed_rate_apply_months"),
                external_ref={"provider": "payinfo", "api_body": _loan_precheck_body(idx, spec["loan"])},
            )
        )
        db.add(
            MedicalDocument(
                customer_id=customer.id,
                doc_type=spec["health"]["document"]["doc_type"],
                issued_at=date.fromisoformat(spec["health"]["document"]["issued_at"]),
                summary=spec["health"]["document"]["summary"],
                consent_id=consent_id,
            )
        )
        db.add(
            CustomerMemory(
                customer_id=customer.id,
                medical_willingness=willingness,
                risk_preference=spec["memory"]["risk_preference"],
                medical_one_time_budget_krw=Decimal(spec["memory"]["medical_one_time_budget_krw"]),
                monthly_medical_budget_krw=Decimal(spec["memory"]["monthly_medical_budget_krw"]),
                medical_budget_ratio=float(spec["memory"]["medical_budget_ratio"]),
                hospital_preference=spec["memory"]["hospital_preference"],
                investment_style=style,
                constraints=spec["memory"]["constraints"],
            )
        )
        db.commit()


def _load_demo_customer_specs() -> list[dict]:
    with MOCK_DATA_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    return data["customers"]


def _clear_demo_customer_domain_data(db: Session, customer_id: str) -> None:
    """데모 고객의 domain mock data를 최신 JSON 기준으로 재생성한다.

    AgentSession/AgentEvent 같은 실행 이력은 지우지 않고, 고객 원천 데이터만 갱신한다.
    """
    for row in db.exec(select(HealthRecord).where(HealthRecord.customer_id == customer_id)).all():
        db.delete(row)
    for row in db.exec(select(HealthEvent).where(HealthEvent.customer_id == customer_id)).all():
        db.delete(row)
    for row in db.exec(select(MedicalDocument).where(MedicalDocument.customer_id == customer_id)).all():
        db.delete(row)

    policies = db.exec(select(InsurancePolicy).where(InsurancePolicy.customer_id == customer_id)).all()
    for policy in policies:
        for coverage in db.exec(select(CoverageItem).where(CoverageItem.policy_id == policy.id)).all():
            db.delete(coverage)
    db.flush()
    for policy in policies:
        db.delete(policy)
    db.flush()

    for row in db.exec(select(AssetEvent).where(AssetEvent.customer_id == customer_id)).all():
        db.delete(row)

    for tx in db.exec(select(AccountTransaction).where(AccountTransaction.customer_id == customer_id)).all():
        db.delete(tx)
    db.flush()
    accounts = db.exec(select(AccountBalance).where(AccountBalance.customer_id == customer_id)).all()
    for account in accounts:
        db.delete(account)
    db.flush()

    for row in db.exec(select(CardBill).where(CardBill.customer_id == customer_id)).all():
        db.delete(row)

    loans = db.exec(select(LoanAccount).where(LoanAccount.customer_id == customer_id)).all()
    for loan in loans:
        for precheck in db.exec(select(LoanSwitchPrecheck).where(LoanSwitchPrecheck.loan_id == loan.id)).all():
            db.delete(precheck)
    db.flush()
    for loan in loans:
        db.delete(loan)
    db.flush()

    portfolios = db.exec(select(PortfolioAccount).where(PortfolioAccount.customer_id == customer_id)).all()
    for portfolio in portfolios:
        for holding in db.exec(select(Holding).where(Holding.account_id == portfolio.id)).all():
            db.delete(holding)
    db.flush()
    for portfolio in portfolios:
        db.delete(portfolio)

    memory = db.get(CustomerMemory, customer_id)
    if memory:
        db.delete(memory)
    db.commit()


def _yyyymmdd(value: str | date) -> str:
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    return value.replace("-", "")


def _api_common(idx: int) -> dict:
    return {
        "api_tran_id": f"MOCKAPI{idx:02d}BHZ1324K82AL3",
        "api_tran_dtm": f"20260605{101900 + idx:06d}567",
        "rsp_code": "A0000",
        "rsp_message": "",
        "bank_tran_id": f"F123456789U{idx:09d}",
        "bank_tran_date": "20260605",
        "bank_code_tran": "097",
        "bank_rsp_code": "000",
        "bank_rsp_message": "",
    }


def _account_balance_body(idx: int, account: dict) -> dict:
    return {
        **_api_common(idx),
        "bank_name": account["bank_name"],
        "savings_bank_name": "",
        "fintech_use_num": f"12345678901234567890{idx:04d}",
        "balance_amt": str(account["balance_krw"]),
        "available_amt": str(account["available_krw"]),
        "account_type": account["openbanking_account_type"],
        "product_name": account["product_name"],
        "account_issue_date": _yyyymmdd(account["issued_on"]),
        "maturity_date": _yyyymmdd(account["matures_on"]) if account.get("matures_on") else "",
        "last_tran_date": date.today().strftime("%Y%m%d"),
    }


def _transaction_header_body(idx: int, account_spec: dict) -> dict:
    return {
        **_api_common(idx),
        "bank_name": account_spec["bank_name"],
        "savings_bank_name": "",
        "fintech_use_num": f"12345678901234567890{idx:04d}",
        "balance_amt": str(account_spec["balance_krw"]),
        "page_record_cnt": "25",
        "next_page_yn": "Y",
        "befor_inquiry_trace_info": f"TRACE{idx:04d}",
    }


def _transaction_item_body(transacted_at: datetime, pattern: dict, amount: int, after_balance: int) -> dict:
    return {
        "tran_date": transacted_at.strftime("%Y%m%d"),
        "tran_time": transacted_at.strftime("%H%M%S"),
        "inout_type": "입금" if pattern["direction"] == "in" else "출금",
        "tran_type": pattern["transaction_type"],
        "printed_content": pattern["description"],
        "tran_amt": str(amount),
        "after_balance_amt": str(after_balance),
        "branch_name": pattern.get("branch_name", "전주본점"),
    }


def _card_list_item(idx: int, card_idx: int, card: dict) -> dict:
    return {
        "card_id": f"cardMOCK{idx:02d}{card_idx:02d}ABC123abcABC123abcABC",
        "card_num_masked": card["card_num_masked"],
        "card_name": card["card_name"],
        "card_member_type": card["card_member_type"],
    }


def _card_issue_body(idx: int, card_idx: int, card: dict) -> dict:
    return {
        **_api_common(idx),
        "card_id": f"cardMOCK{idx:02d}{card_idx:02d}ABC123abcABC123abcABC",
        "card_type": card["card_type"],
        "card_name": card["card_name"],
        "card_num_masked": card["card_num_masked"],
        "issue_date": _yyyymmdd(card["issue_date"]),
        "card_member_type": card["card_member_type"],
    }


def _card_bill_basic_body(idx: int, card_idx: int, card: dict) -> dict:
    return {
        **_api_common(idx),
        "card_id": f"cardMOCK{idx:02d}{card_idx:02d}ABC123abcABC123abcABC",
        "card_type": card["card_type"],
        "charge_month": date.today().strftime("%Y%m"),
        "settlement_date": (date.today() + timedelta(days=int(card["settlement_in_days"]))).strftime("%Y%m%d"),
        "charge_amt": str(card["charge_krw"]),
    }


def _card_bill_detail_body(idx: int, card_idx: int, card: dict) -> dict:
    return {
        **_api_common(idx),
        "card_value": f"card-value-{idx:02d}-{card_idx:02d}",
        "charge_month": date.today().strftime("%Y%m"),
        "bill_detail_cnt": str(len(card["details"])),
        "bill_detail_list": [
            {
                "used_date": _yyyymmdd(item["used_on"]),
                "merchant_name": item["merchant_name"],
                "merchant_regno": item.get("merchant_regno", "0000000000"),
                "credit_check_type": card["credit_check_type"],
                "used_amt": str(item["amount_krw"]),
                "category_hint": item["category_hint"],
            }
            for item in card["details"]
        ],
    }


def _insurance_list_item(idx: int, policy: dict) -> dict:
    return {
        "insu_num": f"INSU{idx:02d}{policy['policy_no_suffix']}",
        "prod_name": policy["product_name"],
        "insu_type": policy["insu_type_code"],
        "insu_status": "02" if policy["active"] else "04",
        "issue_date": _yyyymmdd(policy["issue_date"]),
        "exp_date": _yyyymmdd(policy["exp_date"]),
    }


def _insurance_payment_body(idx: int, policy: dict) -> dict:
    return {
        **_api_common(idx),
        "bank_code_std": policy["bank_code_std"],
        "insu_num": f"INSU{idx:02d}{policy['policy_no_suffix']}",
        "pay_cycle": policy["pay_cycle"],
        "pay_due_date": policy["pay_due_date"],
        "pay_end_date": _yyyymmdd(policy["pay_end_date"]),
        "pay_amt": str(policy["pay_amt"]),
        "pay_method": policy["pay_method"],
        "auto_pay_bank_code": policy["auto_pay_bank_code"],
    }


def _loan_precheck_body(idx: int, loan: dict) -> dict:
    return {
        "loan_repayment_id": f"LRP{idx:09d}",
        "loan_contract_id": f"LC{idx:018d}",
        "loan_info_request_date": date.today().strftime("%Y%m%d"),
        "loan_repayment_available_yn": "Y",
        "loan_repayment_penalty_fee": str(loan["prepayment_penalty_krw"]),
        "loan_interestrate_type": loan["interest_rate_type"],
        "loan_interestrate_variation_cycle": str(loan.get("variation_cycle_months") or ""),
        "loan_fixedRate_apply_period": str(loan.get("fixed_rate_apply_months") or ""),
    }
