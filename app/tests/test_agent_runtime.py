"""핵심 루프 종단 테스트 — StubReasoner로 승인/통합 회복탄력성 루프 검증."""
from __future__ import annotations

import json
import sys
import types
from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import inspect, text
from sqlmodel import SQLModel, Session, create_engine, select
from sqlmodel.pool import StaticPool


@pytest.fixture
def db(monkeypatch):
    import app.core.database as database
    from app.core.config import settings

    monkeypatch.setattr(settings, "reasoner", "stub")

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

    customer = db.exec(select(Customer).where(Customer.name == "김영자")).first()
    assert customer is not None
    return customer.id


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


def test_jwt_and_customer_scope_guard(db: Session):
    from app.api.routes.customers import customer_portfolio
    from app.core.auth import Principal, create_jwt, require_customer_access, verify_jwt

    customer_id = _customer_id(db)
    token = create_jwt(subject="user-1", role="customer", customer_id=customer_id)
    principal = verify_jwt(token)

    assert principal.role == "customer"
    assert principal.customer_id == customer_id
    require_customer_access(principal, customer_id)
    with pytest.raises(HTTPException) as exc:
        require_customer_access(Principal(subject="user-2", role="customer", customer_id="other"), customer_id)
    assert exc.value.status_code == 403

    portfolio = customer_portfolio(customer_id, db, principal)
    assert portfolio["total_value"] == 100_000_000
    with pytest.raises(HTTPException) as route_exc:
        customer_portfolio(customer_id, db, Principal(subject="user-2", role="customer", customer_id="other"))
    assert route_exc.value.status_code == 403


def test_agent_context_pack_is_scoped_and_includes_session_history(db: Session):
    from app.agent.context_builder import build_agent_context
    from app.models.agent import AgentMessage

    session = _new_session(db)
    db.add(
        AgentMessage(
            session_id=session.id,
            role="user",
            content="앞으로 투자 위험은 낮게 봐줘",
            meta={"source": "test"},
        )
    )
    db.commit()

    context = build_agent_context(
        db,
        session,
        current_signal={"source": "event", "payload": {"kind": "portfolio_loss"}},
    )
    assert context["customer_id"] == session.customer_id
    assert context["profile"]["id"] == session.customer_id
    assert context["transactions"]["spending_summary"]["record_count"] >= 90
    assert context["agent_session"]["id"] == session.id
    assert context["agent_session"]["current_signal"]["payload"]["kind"] == "portfolio_loss"
    assert context["session_memory"]["recent_conversation"][0]["content"] == "앞으로 투자 위험은 낮게 봐줘"
    assert "book_hospital" not in json.dumps(context, ensure_ascii=False)


def test_health_data_requires_consent(db: Session):
    from app.models.health import HealthRecord
    from app.tools.data_tools import get_health_data

    customer_id = _customer_id(db)
    db.add(
        HealthRecord(
            customer_id=customer_id,
            source="self_reported",
            metric="sensitive_note",
            value={"note": "동의 없는 건강 정보"},
            consent_id=None,
        )
    )
    db.commit()

    health = get_health_data(db, customer_id)
    metrics = {record["metric"] for record in health["records"]}
    assert "blood_pressure" in metrics
    assert "sensitive_note" not in metrics


def test_revoke_consent_deletes_sensitive_health_data(db: Session):
    from app.models.health import HealthRecord, MedicalDocument
    from app.models.privacy import ConsentRecord
    from app.privacy.service import revoke_consent
    from app.tools.data_tools import get_health_data

    customer_id = _customer_id(db)
    before_records = db.exec(
        select(HealthRecord).where(HealthRecord.customer_id == customer_id, HealthRecord.consent_id == "consent-1")
    ).all()
    before_docs = db.exec(
        select(MedicalDocument).where(
            MedicalDocument.customer_id == customer_id,
            MedicalDocument.consent_id == "consent-1",
        )
    ).all()
    assert before_records
    assert before_docs

    result = revoke_consent(db, customer_id=customer_id, consent_id="consent-1")

    assert result["status"] == "revoked"
    assert result["deleted"]["health_records"] == len(before_records)
    assert result["deleted"]["medical_documents"] == len(before_docs)
    assert get_health_data(db, customer_id)["records"] == []
    consent = db.get(ConsentRecord, "consent-1")
    assert consent is not None
    assert consent.status == "revoked"
    assert consent.revoked_at is not None


def test_retention_purge_deletes_expired_sensitive_messages(db: Session):
    from app.models.agent import AgentMessage
    from app.models.base import utcnow
    from app.privacy.service import purge_expired_sensitive_messages

    session = _new_session(db)
    old_message = AgentMessage(
        session_id=session.id,
        role="user",
        content="old sensitive transcript",
        created_at=utcnow() - timedelta(days=400),
    )
    fresh_message = AgentMessage(
        session_id=session.id,
        role="user",
        content="fresh transcript",
        created_at=utcnow(),
    )
    db.add(old_message)
    db.add(fresh_message)
    db.commit()
    db.refresh(old_message)
    db.refresh(fresh_message)

    result = purge_expired_sensitive_messages(db, retention_days=365)

    assert result["deleted"]["agent_messages"] == 1
    assert db.get(AgentMessage, old_message.id) is None
    assert db.get(AgentMessage, fresh_message.id) is not None


def test_init_db_renames_active_intents_column(monkeypatch):
    import app.core.database as database

    test_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with test_engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE agentsession (
                    id VARCHAR PRIMARY KEY,
                    customer_id VARCHAR,
                    state VARCHAR,
                    active_intents JSON,
                    pending_proposal_id VARCHAR,
                    recent_context JSON,
                    failure_reason VARCHAR,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
                """
            )
        )

    monkeypatch.setattr(database, "engine", test_engine)
    database.init_db()

    columns = {col["name"] for col in inspect(test_engine).get_columns("agentsession")}
    assert "active_needs" in columns
    assert "active_intents" not in columns


@pytest.mark.asyncio
async def test_insurance_approval_flow(db: Session):
    from app.agent.orchestrator import Orchestrator
    from app.models.agent import (
        ActionProposal,
        AgentEvent,
        AgentMessage,
        NeedAssessmentRecord,
        PlanRecord,
    )

    s = _new_session(db)

    r = await Orchestrator().handle_signal(db, s, "event", {"kind": "bp_rising"})
    assert r.state == "UserApproval"
    assert r.pending_proposal_id is not None
    assert r.active_needs["primary_need"] == "insurance"
    assert r.active_needs["needs"]["insurance_need"] == "high"

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

    messages = db.exec(select(AgentMessage).where(AgentMessage.session_id == r.id)).all()
    assessments = db.exec(
        select(NeedAssessmentRecord).where(NeedAssessmentRecord.session_id == r.id)
    ).all()
    plans = db.exec(select(PlanRecord).where(PlanRecord.session_id == r.id)).all()
    assert [m.role for m in messages] == ["system", "assistant", "assistant"]
    assert assessments[0].primary_need == "insurance"
    assert assessments[0].needs["insurance_need"] == "high"
    assert plans[0].proposal_ids
    assert plans[0].raw_output["assessment"]["primary_need"] == "insurance"


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
    from app.tools.data_tools import get_portfolio_summary

    s = _new_session(db)

    r = await Orchestrator().handle_signal(db, s, "event", {"kind": "portfolio_loss"})
    assert r.state == "UserApproval"
    assert r.active_needs["primary_need"] == "investment_adjust"
    assert r.active_needs["needs"]["cashflow_need"] == "high"
    assert r.active_needs["needs"]["asset_defense_need"] == "high"
    assert r.active_needs["needs"]["investment_adjust_need"] == "high"

    proposals = db.exec(select(ActionProposal).where(ActionProposal.session_id == r.id)).all()
    kinds = {p.kind: p for p in proposals}

    assert kinds["report"].status == "executed"
    assert kinds["cashflow_plan"].status == "executed"
    assert kinds["rebalance_portfolio"].has_external_effect is True
    assert kinds["rebalance_portfolio"].params["target_high_risk_weight"] == 0.45
    assert kinds["review_insurance"].has_external_effect is True
    assert kinds["review_insurance"].params["one_time_budget_krw"] == 1_500_000
    assert kinds["review_insurance"].params["monthly_budget_krw"] == 250_000
    assert kinds["cashflow_plan"].params["medical_budget_ratio"] == 0.08

    r.pending_proposal_id = kinds["rebalance_portfolio"].id
    db.add(r)
    db.commit()
    first = await Orchestrator().apply_decision(db, r, "approve")
    assert first.state == "UserApproval"
    assert get_portfolio_summary(db, r.customer_id)["high_risk_weight"] == 0.45

    for proposal in db.exec(
        select(ActionProposal).where(
            ActionProposal.session_id == r.id,
            ActionProposal.status == "proposed",
            ActionProposal.has_external_effect == True,  # noqa: E712
        )
    ).all():
        first.pending_proposal_id = proposal.id
        db.add(first)
        db.commit()
        first = await Orchestrator().apply_decision(db, first, "approve")

    done = first
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


def test_customer_financial_context_routes(db: Session):
    from app.api.routes.customers import (
        customer_accounts,
        customer_card_bills,
        customer_loan_switch_precheck,
        customer_transactions,
    )

    customer_id = _customer_id(db)
    accounts = customer_accounts(customer_id, db)
    transactions = customer_transactions(customer_id, db)
    card_bills = customer_card_bills(customer_id, db)
    precheck = customer_loan_switch_precheck(customer_id, db)

    assert accounts["liquidity_summary"]["available_cash_krw"] > 0
    assert transactions["spending_summary"]["record_count"] >= 90
    assert card_bills["upcoming_card_payment_krw"] > 0
    assert precheck["repayment_available"] is True


def test_customer_agent_session_is_reused(db: Session):
    from app.api.routes.sessions import create_session

    customer_id = _customer_id(db)
    first = create_session(customer_id, db)
    second = create_session(customer_id, db)
    third = create_session(customer_id, db, force_new=True)
    assert first["session_id"] == second["session_id"]
    assert third["session_id"] != first["session_id"]
    assert first["customer_id"] == customer_id
    assert "active_needs" in first
    assert "active_intents" not in first


@pytest.mark.asyncio
async def test_session_records_route(db: Session):
    from app.agent.orchestrator import Orchestrator
    from app.api.routes.sessions import get_records

    session = _new_session(db)
    result = await Orchestrator().handle_signal(db, session, "event", {"kind": "portfolio_loss"})
    records = get_records(result.id, db)

    assert len(records["messages"]) >= 3
    assert records["need_assessments"][0]["primary_need"] == "investment_adjust"
    assert records["plans"][0]["proposal_ids"]


def test_seed_has_demo_customers(db: Session):
    from app.models.customer import Customer

    customers = db.exec(select(Customer)).all()
    assert len(customers) >= 10
    assert any(customer.name == "김영자" for customer in customers)


def test_seed_can_refresh_demo_customers_without_reset(db: Session):
    from app.models.customer import Customer
    from app.models.finance import AccountBalance, AccountTransaction
    import app.seed as seed_mod

    seed_mod.seed_if_empty()
    seed_mod.seed_if_empty()

    customers = db.exec(select(Customer)).all()
    demo = db.exec(select(Customer).where(Customer.name == "박민수")).first()
    assert len(customers) >= 10
    assert demo is not None
    accounts = db.exec(select(AccountBalance).where(AccountBalance.customer_id == demo.id)).all()
    transactions = db.exec(select(AccountTransaction).where(AccountTransaction.customer_id == demo.id)).all()
    assert accounts
    assert len(transactions) >= 100


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
    assert context["memory"]["medical_one_time_budget_krw"] == 1_500_000
    assert context["memory"]["monthly_medical_budget_krw"] == 250_000
    assert context["memory"]["medical_budget_ratio"] == 0.08

    serialized = str({"balances": balances, "transactions": transactions, "card_bills": card_bills, "precheck": precheck})
    for hidden in ("fintech_use_num", "user_seq_no", "card_value", "api_tran_id", "bank_tran_id"):
        assert hidden not in serialized


def test_context_builder_injects_policy_docs_without_code_files(db: Session, monkeypatch, tmp_path):
    from app.agent.context_builder import build_agent_context
    from app.core.config import settings

    policy_docs = tmp_path / "policy_docs"
    policy_docs.mkdir()
    (policy_docs / "boundary.md").write_text("read-only policy", encoding="utf-8")
    (policy_docs / "script.py").write_text("print('do not copy')", encoding="utf-8")
    monkeypatch.setattr(settings, "policy_docs_path", str(policy_docs))

    session = _new_session(db)
    context = build_agent_context(db, session)
    policy_docs_context = context["policy_context"]

    assert [doc["path"] for doc in policy_docs_context] == ["boundary.md"]
    assert policy_docs_context[0]["content"] == "read-only policy"
    assert "script.py" not in json.dumps(context, ensure_ascii=False)


@pytest.mark.asyncio
async def test_pydantic_ai_reasoner_uses_structured_output(monkeypatch):
    from app.agent.schemas import NeedAssessment
    from app.agent.pydantic_ai_reasoner import PydanticAIReasoner
    from app.core.config import settings

    captured: dict[str, object] = {}

    class FakeSandbox:
        read_only = "read_only"

    class FakeThread:
        async def run(self, prompt: str, output_schema=None):
            captured["prompt"] = prompt
            captured["output_schema"] = output_schema
            return types.SimpleNamespace(
                final_response=json.dumps(
                    {
                        "medical_cost_need": "none",
                        "insurance_need": "none",
                        "cashflow_need": "high",
                        "asset_defense_need": "mid",
                        "investment_adjust_need": "low",
                        "life_plan_need": "none",
                        "primary_need": "cashflow",
                        "confidence": 0.82,
                        "rationale": "테스트 구조화 출력",
                        "preference_update_only": False,
                        "no_action": False,
                        "clarifying_question": None,
                    }
                )
            )

    class FakeCodex:
        async def __aenter__(self):
            captured["opened"] = True
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def thread_start(self, **kwargs):
            captured["thread_start"] = kwargs
            return FakeThread()

    monkeypatch.setitem(
        sys.modules,
        "openai_codex",
        types.SimpleNamespace(AsyncCodex=FakeCodex, Sandbox=FakeSandbox),
    )
    monkeypatch.setattr(settings, "codex_model", "gpt-test")

    result = await PydanticAIReasoner().assess_need(
        {"source": "event", "payload": {"kind": "spending_spike"}},
        {"customer_id": "customer-1", "session_memory": {"recent_conversation": []}},
    )

    assert result.primary_need == "cashflow"
    assert captured["thread_start"]["model"] == "gpt-test"
    assert captured["thread_start"]["sandbox"] == FakeSandbox.read_only
    assert captured["output_schema"] is None
    assert "NeedAssessment JSON" in str(captured["prompt"])
    assert "외부 도구" in str(captured["prompt"])


@pytest.mark.asyncio
async def test_signal_route_normalizes_reasoner_errors(db: Session, monkeypatch):
    from fastapi import HTTPException

    from app.agent.errors import ReasonerUnavailable
    import app.api.routes.sessions as sessions_route

    class FailingOrchestrator:
        async def handle_signal(self, db: Session, session, source: str, payload: dict):
            raise ReasonerUnavailable("LLM provider unavailable")

    session = _new_session(db)
    monkeypatch.setattr(sessions_route, "Orchestrator", FailingOrchestrator)

    with pytest.raises(HTTPException) as exc:
        await sessions_route.post_signal(
            session.id,
            sessions_route.SignalIn(source="event", payload={"kind": "portfolio_loss"}),
            db,
    )

    assert exc.value.status_code == 503
    assert exc.value.detail["error"] == "reasoner_unavailable"
    assert "LLM provider" in exc.value.detail["message"]
    db.refresh(session)
    assert session.state == "Monitoring"
    assert "LLM provider" in (session.failure_reason or "")


@pytest.mark.asyncio
async def test_customer_session_reinjects_context_history(db: Session):
    from app.agent.orchestrator import Orchestrator
    from app.agent.schemas import NeedAssessment, Plan

    class RecordingReasoner:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, int]] = []

        async def assess_need(self, signal: dict, ctx: dict) -> NeedAssessment:
            self.calls.append(
                (
                    "assess",
                    signal["payload"]["kind"],
                    len(ctx["session_memory"]["recent_conversation"]),
                )
            )
            return NeedAssessment(
                primary_need="cashflow",
                cashflow_need="high",
                asset_defense_need="mid",
                confidence=0.9,
                rationale="테스트용 현금흐름 필요도",
            )

        async def generate_plan(
            self,
            assessment: NeedAssessment,
            ctx: dict,
            memory: dict,
        ) -> Plan:
            self.calls.append(
                (
                    "plan",
                    assessment.primary_need,
                    len(ctx["session_memory"]["recent_conversation"]),
                )
            )
            return Plan(explanation="제안 없음", assessment=assessment)

    reasoner = RecordingReasoner()
    session = _new_session(db)
    orchestrator = Orchestrator(reasoner=reasoner)

    first = await orchestrator.handle_signal(db, session, "event", {"kind": "portfolio_loss"})
    assert first.state == "Monitoring"
    assert first.pending_proposal_id is None

    second = await orchestrator.handle_signal(db, first, "event", {"kind": "spending_spike"})
    assert second.state == "Monitoring"
    assert second.pending_proposal_id is None
    assert reasoner.calls == [
        ("assess", "portfolio_loss", 1),
        ("plan", "cashflow", 1),
        ("assess", "spending_spike", 4),
        ("plan", "cashflow", 4),
    ]
