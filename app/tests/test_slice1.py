"""핵심 루프 종단 테스트 — StubReasoner로 승인/통합 회복탄력성 루프 검증."""
from __future__ import annotations

import pytest
from sqlmodel import SQLModel, Session, create_engine, select
from sqlmodel.pool import StaticPool


@pytest.fixture
def db(monkeypatch):
    import app.core.database as database

    test_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    monkeypatch.setattr(database, "engine", test_engine)

    import app.models  # noqa: F401  테이블 등록

    SQLModel.metadata.create_all(test_engine)

    import app.seed as seed_mod

    monkeypatch.setattr(seed_mod, "engine", test_engine)
    seed_mod.seed_if_empty()

    with Session(test_engine) as session:
        yield session


def _customer_id(db: Session) -> str:
    from app.models.customer import Customer

    return db.exec(select(Customer)).one().id


def _new_session(db: Session):
    from app.models.agent import AgentSession
    from app.state_machine.states import State

    s = AgentSession(customer_id=_customer_id(db), state=State.MONITORING)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def test_capability_no_execution_tools():
    """에이전트 도구 표면에 실행 동사가 없어야 한다 (capability 회귀)."""
    from app.tools import data_tools

    names = [n for n in dir(data_tools) if not n.startswith("_")]
    for verb in ("book_", "submit_", "transfer_", "change_"):
        assert not any(n.startswith(verb) for n in names), f"실행 도구 노출됨: {verb}"


@pytest.mark.asyncio
async def test_insurance_approval_flow(db: Session):
    from app.agent.orchestrator import Orchestrator
    from app.models.agent import ActionProposal, AgentEvent

    s = _new_session(db)

    r = await Orchestrator().handle_signal(db, s, "event", {"kind": "bp_rising"})
    assert r.state == "UserApproval"
    assert r.pending_proposal_id is not None
    assert r.active_intents["primary_need"] == "insurance"
    assert r.active_intents["needs"]["insurance_need"] == "high"

    proposals = db.exec(select(ActionProposal).where(ActionProposal.session_id == r.id)).all()
    assert any(p.kind == "report" and p.status == "executed" for p in proposals)
    pending = db.get(ActionProposal, r.pending_proposal_id)
    assert pending is not None
    assert pending.has_external_effect is True

    done = await Orchestrator().apply_decision(db, r, "approve")
    assert done.state == "Monitoring"
    assert done.pending_proposal_id is None

    db.refresh(pending)
    assert pending.status == "executed"

    events = db.exec(select(AgentEvent).where(AgentEvent.session_id == r.id)).all()
    types = [e.type for e in events]
    assert "need_assessment" in types and "plan" in types and "execution" in types
    assert types.count("state_transition") >= 6


@pytest.mark.asyncio
async def test_reject_flow(db: Session):
    from app.agent.orchestrator import Orchestrator
    from app.models.agent import ActionProposal

    s = _new_session(db)
    r = await Orchestrator().handle_signal(db, s, "event", {"kind": "bp_rising"})
    pid = r.pending_proposal_id
    assert pid is not None

    done = await Orchestrator().apply_decision(db, r, "reject")
    assert done.state == "Monitoring"
    claim = db.get(ActionProposal, pid)
    assert claim is not None
    assert claim.status == "rejected"


@pytest.mark.asyncio
async def test_asset_trigger_resilience(db: Session):
    from app.agent.orchestrator import Orchestrator
    from app.models.agent import ActionProposal

    s = _new_session(db)

    r = await Orchestrator().handle_signal(db, s, "event", {"kind": "portfolio_loss"})
    assert r.state == "UserApproval"
    assert r.active_intents["primary_need"] == "cashflow"
    assert r.active_intents["needs"]["cashflow_need"] == "high"
    assert r.active_intents["needs"]["asset_defense_need"] == "high"

    proposals = db.exec(select(ActionProposal).where(ActionProposal.session_id == r.id)).all()
    kinds = {p.kind: p for p in proposals}

    assert kinds["report"].status == "executed"
    assert kinds["cashflow_plan"].status == "executed"
    assert kinds["review_insurance"].has_external_effect is True
    assert "rebalance_portfolio" not in kinds

    done = await Orchestrator().apply_decision(db, r, "approve")
    assert done.state == "Monitoring"


def test_population_stat_tool(db: Session):
    from app.tools.data_tools import get_population_stat

    stat = get_population_stat(db, "65-69", "avg_emergency_fund_months")
    assert stat["value"]["months"] == 6
    assert stat["source"]


def test_customer_portfolio_route_contract(db: Session):
    from app.api.routes.customers import customer_portfolio

    portfolio = customer_portfolio(_customer_id(db), db)
    assert portfolio["total_value"] == 100_000_000
    assert portfolio["high_risk_weight"] == 0.7


def test_customer_agent_session_is_reused(db: Session):
    from app.api.routes.sessions import create_session

    customer_id = _customer_id(db)
    first = create_session(customer_id, db)
    second = create_session(customer_id, db)
    assert first["session_id"] == second["session_id"]
    assert first["customer_id"] == customer_id


def test_api_shaped_mock_data_has_100_plus_records(db: Session):
    from app.models.finance import AccountTransaction, CardBill, LoanSwitchPrecheck

    customer_id = _customer_id(db)
    transactions = db.exec(
        select(AccountTransaction).where(AccountTransaction.customer_id == customer_id)
    ).all()
    card_bills = db.exec(select(CardBill).where(CardBill.customer_id == customer_id)).all()
    prechecks = db.exec(
        select(LoanSwitchPrecheck).where(LoanSwitchPrecheck.customer_id == customer_id)
    ).all()

    assert len(transactions) >= 100
    assert len(card_bills) >= 2
    assert len(prechecks) >= 1


def test_financial_read_tools_hide_provider_identifiers(db: Session):
    from app.tools.data_tools import (
        build_context,
        get_account_balances,
        get_account_transactions,
        get_card_bills,
        get_loan_switch_precheck,
    )

    customer_id = _customer_id(db)
    balances = get_account_balances(db, customer_id)
    transactions = get_account_transactions(db, customer_id)
    card_bills = get_card_bills(db, customer_id)
    precheck = get_loan_switch_precheck(db, customer_id)
    context = build_context(db, customer_id)

    assert balances["liquidity_summary"]["available_cash_krw"] > 0
    assert transactions["spending_summary"]["record_count"] >= 90
    assert transactions["spending_summary"]["medical_spending_krw"] > 0
    assert card_bills["upcoming_card_payment_krw"] > 0
    assert precheck["repayment_available"] is True
    assert "accounts" in context and "transactions" in context and "card_bills" in context

    serialized = str({"balances": balances, "transactions": transactions, "card_bills": card_bills, "precheck": precheck})
    for hidden in ("fintech_use_num", "user_seq_no", "card_value", "api_tran_id", "bank_tran_id"):
        assert hidden not in serialized
