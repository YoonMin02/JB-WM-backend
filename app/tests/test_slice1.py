"""핵심 루프 종단 테스트 — StubReasoner로 승인/통합 회복탄력성 루프 검증."""
from __future__ import annotations

import json
import sys
import types

import pytest
from sqlalchemy import inspect, text
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


def test_mcp_read_tools_are_scoped_and_audited(db: Session):
    from app.mcp.read_tools import call_read_tool, list_read_tools
    from app.models.agent import AgentEvent

    session = _new_session(db)
    tools = {tool["name"] for tool in list_read_tools()}
    assert "get_health_data" in tools
    assert "get_customer_memory" in tools
    assert "search_policy_documents" in tools
    for forbidden in ("book_hospital", "submit_claim", "transfer_money", "change_portfolio"):
        assert forbidden not in tools

    result = call_read_tool(
        db,
        session_id=session.id,
        customer_id=session.customer_id,
        name="get_customer_profile",
        arguments={"customer_id": "malicious-other-customer"},
    )
    assert result["id"] == session.customer_id

    events = db.exec(select(AgentEvent).where(AgentEvent.session_id == session.id)).all()
    assert any(
        event.type == "tool_call"
        and event.detail["via"] == "mcp"
        and event.detail["tool"] == "get_customer_profile"
        and "customer_id" not in event.detail["arguments"]
        for event in events
    )


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
                    agent_thread_id VARCHAR,
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

    s = _new_session(db)

    r = await Orchestrator().handle_signal(db, s, "event", {"kind": "portfolio_loss"})
    assert r.state == "UserApproval"
    assert r.active_needs["primary_need"] == "cashflow"
    assert r.active_needs["needs"]["cashflow_need"] == "high"
    assert r.active_needs["needs"]["asset_defense_need"] == "high"

    proposals = db.exec(select(ActionProposal).where(ActionProposal.session_id == r.id)).all()
    kinds = {p.kind: p for p in proposals}

    assert kinds["report"].status == "executed"
    assert kinds["cashflow_plan"].status == "executed"
    assert kinds["review_insurance"].has_external_effect is True
    assert kinds["review_insurance"].params["one_time_budget_krw"] == 1_500_000
    assert kinds["review_insurance"].params["monthly_budget_krw"] == 250_000
    assert kinds["cashflow_plan"].params["medical_budget_ratio"] == 0.08
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
    assert first["session_id"] == second["session_id"]
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
    assert records["need_assessments"][0]["primary_need"] == "cashflow"
    assert records["plans"][0]["proposal_ids"]


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


def test_codex_workspace_contains_only_context_snapshots(db: Session, monkeypatch, tmp_path):
    from app.agent.codex_adapter import _mcp_config, _write_workspace
    from app.core.config import settings
    from app.tools.data_tools import build_context

    monkeypatch.setattr(settings, "codex_working_directory", str(tmp_path))
    policy_docs = tmp_path / "policy_docs"
    policy_docs.mkdir()
    (policy_docs / "boundary.md").write_text("read-only policy", encoding="utf-8")
    (policy_docs / "script.py").write_text("print('do not copy')", encoding="utf-8")
    monkeypatch.setattr(settings, "policy_docs_path", str(policy_docs))
    ctx = build_context(db, _customer_id(db))
    ctx["agent_session_id"] = "session-for-mcp"

    workspace = _write_workspace(ctx)
    mcp_config = _mcp_config(ctx)
    files = {p.name for p in workspace.iterdir()}

    assert "customer_id.json" not in files
    assert "profile.json" in files
    assert "accounts.json" in files
    assert "transactions.json" in files
    assert "memory.json" in files
    assert not any(name.endswith(".py") for name in files)
    assert (workspace / "static_context" / "boundary.md").exists()
    assert not (workspace / "static_context" / "script.py").exists()
    server = mcp_config["mcp_server_config"]["jbwm-read-tools"]
    assert server["args"] == ["-m", "app.mcp.read_server"]
    assert server["env"]["JBWM_MCP_CUSTOMER_ID"] == ctx["customer_id"]
    assert server["env"]["JBWM_MCP_SESSION_ID"] == "session-for-mcp"
    assert server["env"]["PYTHONPATH"].endswith("JB-WM-backend")
    assert server["env"]["POLICY_DOCS_PATH"].endswith("policy_docs")

    accounts = json.loads((workspace / "accounts.json").read_text(encoding="utf-8"))
    assert accounts["liquidity_summary"]["available_cash_krw"] > 0


def test_codex_parse_error_is_normalized():
    from app.agent.codex_adapter import CodexOutputError, _parse
    from app.agent.schemas import NeedAssessment

    with pytest.raises(CodexOutputError):
        _parse("{not json", NeedAssessment)


@pytest.mark.asyncio
async def test_signal_route_normalizes_reasoner_errors(db: Session, monkeypatch):
    from fastapi import HTTPException

    from app.agent.codex_adapter import CodexUnavailable
    import app.api.routes.sessions as sessions_route

    class FailingOrchestrator:
        async def handle_signal(self, db: Session, session, source: str, payload: dict):
            raise CodexUnavailable("OAuth 세션을 찾을 수 없습니다.")

    session = _new_session(db)
    monkeypatch.setattr(sessions_route, "Orchestrator", FailingOrchestrator)

    with pytest.raises(HTTPException) as exc:
        await sessions_route.post_signal(
            session.id,
            sessions_route.SignalIn(source="event", payload={"kind": "portfolio_loss"}),
            db,
        )

    assert exc.value.status_code == 503
    assert exc.value.detail["error"] == "codex_unavailable"
    assert "OAuth" in exc.value.detail["message"]


@pytest.mark.asyncio
async def test_codex_adapter_starts_thread_read_only(monkeypatch, tmp_path):
    from app.agent.codex_adapter import CodexReasoner
    from app.agent.schemas import NeedAssessment
    from app.core.config import settings

    captured: dict[str, object] = {}

    class FakeSandbox:
        read_only = "read_only"

    class FakeThread:
        id = "thread-readonly"

        async def run(self, prompt: str, output_schema: dict):
            return types.SimpleNamespace(
                status="completed",
                error=None,
                final_response=json.dumps(
                    {
                        "medical_cost_need": "none",
                        "insurance_need": "none",
                        "cashflow_need": "high",
                        "asset_defense_need": "mid",
                        "investment_adjust_need": "low",
                        "life_plan_need": "none",
                        "primary_need": "cashflow",
                        "confidence": 0.8,
                        "rationale": "fake",
                        "preference_update_only": False,
                        "no_action": False,
                        "clarifying_question": None,
                    }
                ),
            )

    class FakeCodex:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def thread_start(self, **kwargs):
            captured.update(kwargs)
            return FakeThread()

    fake_module = types.SimpleNamespace(AsyncCodex=FakeCodex, Sandbox=FakeSandbox)
    monkeypatch.setitem(sys.modules, "openai_codex", fake_module)
    monkeypatch.setattr(settings, "codex_working_directory", str(tmp_path))

    reasoner = CodexReasoner()
    result = await reasoner._run(
        "fake prompt",
        {"customer_id": "customer-1", "profile": {"name": "김영자"}},
        NeedAssessment,
    )

    assert result.primary_need == "cashflow"
    assert captured["sandbox"] == FakeSandbox.read_only
    assert "JB-WM-backend/app" not in str(captured["cwd"])


@pytest.mark.asyncio
async def test_customer_session_reuses_reasoner_thread_ref(db: Session):
    from app.agent.orchestrator import Orchestrator
    from app.agent.schemas import NeedAssessment, Plan

    class RecordingReasoner:
        def __init__(self) -> None:
            self.last_thread_id: str | None = None
            self.calls: list[tuple[str, str | None]] = []

        async def start_session(self, customer_id: str, ctx: dict) -> str:
            self.calls.append(("start", None))
            self.last_thread_id = f"thread-{customer_id}"
            return self.last_thread_id

        async def resume_session(self, session_ref: str) -> str:
            self.calls.append(("resume", session_ref))
            self.last_thread_id = session_ref
            return session_ref

        async def assess_need(self, signal: dict, ctx: dict, session_ref: str | None = None) -> NeedAssessment:
            self.calls.append(("assess", session_ref))
            self.last_thread_id = session_ref
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
            session_ref: str | None = None,
        ) -> Plan:
            self.calls.append(("plan", session_ref))
            self.last_thread_id = session_ref
            return Plan(explanation="제안 없음", assessment=assessment)

    reasoner = RecordingReasoner()
    session = _new_session(db)
    orchestrator = Orchestrator(reasoner=reasoner)

    first = await orchestrator.handle_signal(db, session, "event", {"kind": "portfolio_loss"})
    assert first.state == "Monitoring"
    assert first.agent_thread_id == f"thread-{first.customer_id}"

    second = await orchestrator.handle_signal(db, first, "event", {"kind": "spending_spike"})
    assert second.state == "Monitoring"
    assert second.agent_thread_id == f"thread-{first.customer_id}"
    assert reasoner.calls == [
        ("start", None),
        ("assess", f"thread-{first.customer_id}"),
        ("plan", f"thread-{first.customer_id}"),
        ("resume", f"thread-{first.customer_id}"),
        ("assess", f"thread-{first.customer_id}"),
        ("plan", f"thread-{first.customer_id}"),
    ]
