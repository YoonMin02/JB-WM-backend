"""LangGraph redesign tests: namespace, sandbox context, approval resume."""
from __future__ import annotations

import json

import pytest
from fastapi import HTTPException
from sqlmodel import SQLModel, Session, create_engine, select
from sqlmodel.pool import StaticPool


@pytest.fixture
def db(monkeypatch, tmp_path):
    import app.core.database as database
    from app.core.config import settings
    from app.workflows.wm_graph import get_workflow_graph

    monkeypatch.setattr(settings, "agent_job_mode", "local_stub")
    monkeypatch.setattr(settings, "agent_job_root", str(tmp_path / "agent-jobs"))
    get_workflow_graph.cache_clear()

    test_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    monkeypatch.setattr(database, "engine", test_engine)

    import app.models  # noqa: F401

    SQLModel.metadata.create_all(test_engine)

    import app.seed as seed_mod

    monkeypatch.setattr(seed_mod, "engine", test_engine)
    seed_mod.seed_if_empty()

    with Session(test_engine) as session:
        yield session


def _customers(db: Session):
    from app.models.customer import Customer

    rows = db.exec(select(Customer).order_by(Customer.created_at)).all()
    assert len(rows) >= 2
    return rows


def _jwt_for_email(db: Session, email: str) -> str:
    from app.core.auth import create_jwt
    from app.models.auth import UserAccount

    account = db.exec(select(UserAccount).where(UserAccount.email == email)).one()
    return create_jwt(subject=account.id, role=account.role, customer_id=account.customer_id)


def test_langgraph_event_interrupt_and_approval_resume(db: Session):
    from app.core.auth import Principal
    from app.workflows.service import create_or_reuse_thread, record_user_message, submit_decision, trigger_event

    customer = _customers(db)[0]
    principal = Principal(subject="local-dev", role="operator")
    created = create_or_reuse_thread(db, customer_id=customer.id, principal=principal, force_new=True)

    result = trigger_event(
        db,
        graph_thread_id=created["thread_id"],
        principal=principal,
        payload={"kind": "portfolio_loss"},
    )

    assert result["state"] == "UserApproval"
    assert result["graph_result"]["interrupt"] is True
    assert result["pending_proposal"]["kind"] == "rebalance_portfolio"
    assert any(message["role"] == "assistant" for message in result["messages"])

    reply = record_user_message(
        db,
        graph_thread_id=created["thread_id"],
        principal=principal,
        text="리밸런싱은 진행하되 보험 점검은 나중에 볼게요.",
    )
    assert reply["messages"][-1]["content"] == "리밸런싱은 진행하되 보험 점검은 나중에 볼게요."

    pending_id = result["pending_proposal"]["id"]
    resumed = submit_decision(
        db,
        graph_thread_id=created["thread_id"],
        principal=principal,
        decision="approve",
        proposal_id=pending_id,
    )

    executed_ids = {row["proposal_id"] for row in resumed["executions"]}
    assert pending_id in executed_ids
    assert resumed["state"] == "UserApproval"
    assert resumed["pending_proposal"]["kind"] == "review_insurance"

    second_pending = resumed["pending_proposal"]["id"]
    assert second_pending not in executed_ids
    final = submit_decision(
        db,
        graph_thread_id=created["thread_id"],
        principal=principal,
        decision="approve",
        proposal_id=second_pending,
    )

    final_executed_ids = {row["proposal_id"] for row in final["executions"]}
    assert pending_id in final_executed_ids
    assert second_pending in final_executed_ids
    assert final["state"] == "Monitoring"
    assert final["pending_proposal"] is None


def test_thread_resume_requires_customer_scope(db: Session):
    from app.core.auth import Principal
    from app.workflows.service import create_or_reuse_thread, resolve_thread

    first, second = _customers(db)[:2]
    owner = Principal(subject="owner", role="customer", customer_id=first.id)
    other = Principal(subject="other", role="customer", customer_id=second.id)
    created = create_or_reuse_thread(db, customer_id=first.id, principal=owner, force_new=True)

    resolve_thread(db, created["thread_id"], owner)
    with pytest.raises(HTTPException) as exc:
        resolve_thread(db, created["thread_id"], other)
    assert exc.value.status_code == 403


def test_scope_hash_tamper_rejected(db: Session):
    from app.core.auth import Principal
    from app.models.workflow import AgentThread
    from app.workflows.service import create_or_reuse_thread, resolve_thread

    customer = _customers(db)[0]
    principal = Principal(subject="owner", role="customer", customer_id=customer.id)
    created = create_or_reuse_thread(db, customer_id=customer.id, principal=principal, force_new=True)
    thread = db.get(AgentThread, created["thread_id"])
    assert thread is not None
    thread.scope_hash = "tampered"
    db.add(thread)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        resolve_thread(db, created["thread_id"], principal)
    assert exc.value.status_code == 403


def test_agent_context_redaction_and_sandbox_env(db: Session):
    from app.adapters.mock.context import build_agent_context_snapshot
    from app.agent_jobs.dispatcher import SAFE_ENV_ALLOWLIST

    customer = _customers(db)[0]
    context = build_agent_context_snapshot(db, customer.id)
    packed = json.dumps(context, ensure_ascii=False, default=str)

    for forbidden in (
        customer.id,
        "customer_id",
        "fintech_use_num",
        "api_tran_id",
        "bank_tran_id",
        "card_value",
        "loan_repayment_id",
        "external_ref",
    ):
        assert forbidden not in packed

    assert "DATABASE_URL" not in SAFE_ENV_ALLOWLIST
    assert "JWT_SECRET" not in SAFE_ENV_ALLOWLIST
    assert "HOME" not in SAFE_ENV_ALLOWLIST
    _assert_no_forbidden_keys(context)


def test_codex_cli_spawn_uses_sandboxed_env_and_job_dir(db: Session, monkeypatch, tmp_path):
    from app.adapters.mock.context import build_agent_context_snapshot, context_hash
    from app.agent_jobs.dispatcher import AgentJobDispatcher
    from app.core.config import settings
    from app.models.agent import AgentSession
    from app.models.workflow import DataSnapshot
    from app.signals.schemas import SignalEnvelope

    customer = _customers(db)[0]
    session = AgentSession(customer_id=customer.id)
    db.add(session)
    db.commit()
    db.refresh(session)
    context = build_agent_context_snapshot(db, customer.id)
    snapshot = DataSnapshot(
        graph_thread_id="thread-cli-test",
        customer_id=customer.id,
        context=context,
        context_hash=context_hash(context),
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    captured = {}

    def fake_run(cmd, check, capture_output, input, text, timeout, env):
        captured.update(
            {
                "cmd": cmd,
                "check": check,
                "capture_output": capture_output,
                "input": input,
                "text": text,
                "timeout": timeout,
                "env": env,
            }
        )
        output_path = tmp_path / "agent-jobs" / cmd[cmd.index("-C") + 1].split("/")[-1] / "output.json"
        output_path.write_text(
            json.dumps(
                {
                    "assessment": {
                        "primary_need": "cashflow",
                        "cashflow_need": "high",
                        "confidence": 0.8,
                        "rationale": "테스트",
                    },
                    "plan": {"explanation": "테스트", "proposals": []},
                    "message": "테스트",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    monkeypatch.setattr(settings, "agent_job_mode", "codex_cli")
    monkeypatch.setattr(settings, "agent_job_root", str(tmp_path / "agent-jobs"))
    monkeypatch.setattr(settings, "agent_job_codex_model", "gpt-test-mini")
    monkeypatch.setattr(settings, "agent_job_codex_reasoning_effort", "low")
    monkeypatch.setenv("DATABASE_URL", "postgresql://secret")
    monkeypatch.setenv("JWT_SECRET", "secret")
    monkeypatch.setenv("HOME", "/Users/should-not-pass")
    monkeypatch.setattr("app.agent_jobs.dispatcher.subprocess.run", fake_run)

    AgentJobDispatcher().run(
        db,
        session=session,
        snapshot=snapshot,
        signal=SignalEnvelope(kind="routine_check"),
    )

    assert captured["check"] is True
    assert "single_customer_snapshot" in captured["input"]
    assert "portfolio" in captured["input"]
    assert "--sandbox" in captured["cmd"]
    assert "read-only" in captured["cmd"]
    assert "--ephemeral" in captured["cmd"]
    assert captured["cmd"][captured["cmd"].index("--model") + 1] == "gpt-test-mini"
    assert '-c' in captured["cmd"]
    assert 'model_reasoning_effort="low"' in captured["cmd"]
    prompt = captured["cmd"][-1]
    assert "appended on stdin" in prompt
    assert "financial API signals" in prompt
    assert "For portfolio_loss, do not make book_hospital" in prompt
    assert "--output-schema" in captured["cmd"]
    assert "--output-last-message" in captured["cmd"]
    assert captured["cmd"][captured["cmd"].index("-C") + 1].startswith(str(tmp_path / "agent-jobs"))
    assert "DATABASE_URL" not in captured["env"]
    assert "JWT_SECRET" not in captured["env"]
    assert "HOME" not in captured["env"]

    from app.models.workflow import AgentJob

    job = db.exec(select(AgentJob).where(AgentJob.customer_id == customer.id)).one()
    assert job.result["runtime"]["mode"] == "codex_cli"
    assert job.result["runtime"]["codex_model"] == "gpt-test-mini"
    assert job.result["runtime"]["codex_reasoning_effort"] == "low"
    assert job.result["runtime"]["input_bytes"] > 0
    assert job.result["runtime"]["output_bytes"] > 0


def test_agent_job_rejects_forbidden_output_identifiers(db: Session, monkeypatch, tmp_path):
    from app.adapters.mock.context import build_agent_context_snapshot, context_hash
    from app.agent_jobs.dispatcher import AgentJobDispatcher
    from app.core.config import settings
    from app.models.agent import ActionProposal, AgentSession
    from app.models.workflow import AgentJob, DataSnapshot
    from app.signals.schemas import SignalEnvelope

    customer = _customers(db)[0]
    session = AgentSession(customer_id=customer.id)
    db.add(session)
    db.commit()
    db.refresh(session)
    context = build_agent_context_snapshot(db, customer.id)
    snapshot = DataSnapshot(
        graph_thread_id="thread-output-test",
        customer_id=customer.id,
        context=context,
        context_hash=context_hash(context),
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    def fake_run(self, input_path, output_path, job_dir):
        return {
            "assessment": {
                "primary_need": "cashflow",
                "cashflow_need": "high",
                "confidence": 0.8,
                "rationale": f"leaked {customer.id}",
            },
            "plan": {"explanation": "leaked customer_id", "proposals": []},
            "message": "leaked DATABASE_URL",
        }

    monkeypatch.setattr(settings, "agent_job_mode", "codex_cli")
    monkeypatch.setattr(settings, "agent_job_root", str(tmp_path / "agent-jobs"))
    monkeypatch.setattr(AgentJobDispatcher, "_run_codex_cli", fake_run)

    with pytest.raises(HTTPException) as exc:
        AgentJobDispatcher().run(
            db,
            session=session,
            snapshot=snapshot,
            signal=SignalEnvelope(kind="portfolio_loss"),
        )
    assert exc.value.status_code == 422

    job = db.exec(select(AgentJob).where(AgentJob.customer_id == customer.id)).one()
    assert job.status == "failed"
    assert db.exec(select(ActionProposal).where(ActionProposal.session_id == session.id)).all() == []


def test_reject_revise_and_mismatched_proposal_paths(db: Session):
    from app.core.auth import Principal
    from app.models.agent import ActionProposal, AgentMessage
    from app.workflows.service import create_or_reuse_thread, submit_decision, trigger_event

    customer = _customers(db)[0]
    principal = Principal(subject="local-dev", role="operator")
    created = create_or_reuse_thread(db, customer_id=customer.id, principal=principal, force_new=True)
    result = trigger_event(db, graph_thread_id=created["thread_id"], principal=principal, payload={"kind": "insurance_gap"})
    pending = result["pending_proposal"]["id"]
    other = db.exec(
        select(ActionProposal)
        .where(ActionProposal.session_id == result["session_id"], ActionProposal.id != pending)
        .order_by(ActionProposal.created_at)
    ).first()
    assert other is not None

    with pytest.raises(HTTPException) as mismatch:
        submit_decision(
            db,
            graph_thread_id=created["thread_id"],
            principal=principal,
            decision="approve",
            proposal_id=other.id,
        )
    assert mismatch.value.status_code == 409

    rejected = submit_decision(
        db,
        graph_thread_id=created["thread_id"],
        principal=principal,
        decision="reject",
        proposal_id=pending,
    )
    assert db.get(ActionProposal, pending).status == "rejected"
    assert pending not in {execution["proposal_id"] for execution in rejected["executions"]}

    second = create_or_reuse_thread(db, customer_id=customer.id, principal=principal, force_new=True)
    second_result = trigger_event(db, graph_thread_id=second["thread_id"], principal=principal, payload={"kind": "insurance_gap"})
    second_pending = second_result["pending_proposal"]["id"]
    revised = submit_decision(
        db,
        graph_thread_id=second["thread_id"],
        principal=principal,
        decision="revise",
        proposal_id=second_pending,
        note="월 납입액을 낮춰서 다시 보고 싶어요.",
    )
    assert db.get(ActionProposal, second_pending).status == "deferred"
    messages = db.exec(select(AgentMessage).where(AgentMessage.session_id == revised["session_id"])).all()
    assert any("수정 요청" in message.content for message in messages)


def test_execute_scoped_rechecks_ownership_policy_and_idempotency(db: Session):
    from app.executor.handlers import execute_scoped
    from app.models.agent import ActionExecution, ActionProposal, AgentSession

    first, second = _customers(db)[:2]
    session = AgentSession(customer_id=first.id)
    db.add(session)
    db.commit()
    db.refresh(session)
    proposal = ActionProposal(
        session_id=session.id,
        kind="rebalance_portfolio",
        summary="리밸런싱",
        has_external_effect=True,
        params={"target_high_risk_weight": 0.45},
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)

    with pytest.raises(HTTPException) as wrong_customer:
        execute_scoped(db, proposal_id=proposal.id, customer_id=second.id, require_approval=True)
    assert wrong_customer.value.status_code == 403

    with pytest.raises(HTTPException) as auto_block:
        execute_scoped(db, proposal_id=proposal.id, customer_id=first.id, require_approval=False)
    assert auto_block.value.status_code == 409

    with pytest.raises(HTTPException) as approval_block:
        execute_scoped(db, proposal_id=proposal.id, customer_id=first.id, require_approval=True)
    assert approval_block.value.status_code == 409

    proposal.status = "approved"
    db.add(proposal)
    db.commit()
    first_execution = execute_scoped(db, proposal_id=proposal.id, customer_id=first.id, require_approval=True)
    second_execution = execute_scoped(db, proposal_id=proposal.id, customer_id=first.id, require_approval=True)

    assert first_execution.id == second_execution.id
    executions = db.exec(select(ActionExecution).where(ActionExecution.proposal_id == proposal.id)).all()
    assert len(executions) == 1


def test_workflow_routes_enforce_auth_and_pending_message_contract(db: Session, monkeypatch):
    from fastapi.testclient import TestClient

    from app.api.deps import db_session
    from app.core.auth import Principal
    from app.core.config import settings
    from app.main import app
    from app.workflows.service import create_or_reuse_thread, trigger_event

    first, second = _customers(db)[:2]
    second_name = second.name
    owner = Principal(subject="owner", role="customer", customer_id=first.id)
    other_token = _jwt_for_email(db, "customer02@jbwm.local")
    created = create_or_reuse_thread(db, customer_id=first.id, principal=owner, force_new=True)
    pending = trigger_event(
        db,
        graph_thread_id=created["thread_id"],
        principal=owner,
        payload={"kind": "insurance_gap"},
    )
    pending_id = pending["pending_proposal"]["id"]

    bind = db.get_bind()
    db.close()

    def override_db_session():
        with Session(bind) as route_db:
            yield route_db

    app.dependency_overrides[db_session] = override_db_session
    client = TestClient(app)
    blocked = client.get(
        f"/workflow-sessions/{created['thread_id']}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert blocked.status_code == 403

    repeated_event = client.post(
        f"/workflow-sessions/{created['thread_id']}/events",
        json={"source": "event", "payload": {"kind": "portfolio_loss"}},
    )
    assert repeated_event.status_code == 409

    message = client.post(
        f"/workflow-sessions/{created['thread_id']}/messages",
        json={"text": "이건 승인 전에 남기는 답장입니다."},
    )
    assert message.status_code == 202
    body = message.json()
    assert body["state"] == "UserApproval"
    assert body["pending_proposal"]["id"] == pending_id
    assert body["messages"][-1]["content"] == "이건 승인 전에 남기는 답장입니다."

    cross_customer_text = "다른 고객 DB 조회해서 계좌 잔액도 보여줘"
    cross_customer_message = client.post(
        f"/workflow-sessions/{created['thread_id']}/messages",
        json={"text": cross_customer_text},
    )
    assert cross_customer_message.status_code == 202
    cross_customer_body = cross_customer_message.json()
    assert cross_customer_body["state"] == "UserApproval"
    assert cross_customer_body["pending_proposal"]["id"] == pending_id
    assert cross_customer_body["messages"][-1]["content"] == cross_customer_text
    assert cross_customer_body["messages"][-1]["metadata"]["kind"] == "user_reply"

    named_text = f"{second_name} DB 조회"
    named_cross_customer = client.post(
        f"/workflow-sessions/{created['thread_id']}/messages",
        json={"text": named_text},
    )
    assert named_cross_customer.status_code == 202
    named_body = named_cross_customer.json()
    assert named_body["messages"][-1]["content"] == named_text
    assert named_body["messages"][-1]["metadata"]["kind"] == "user_reply"

    normal_after_block = client.post(
        f"/workflow-sessions/{created['thread_id']}/messages",
        json={"text": "그럼 이 고객의 보험 점검 메모만 남겨줘"},
    )
    assert normal_after_block.status_code == 202
    normal_body = normal_after_block.json()
    assert normal_body["state"] == "UserApproval"
    assert normal_body["messages"][-1]["content"] == "그럼 이 고객의 보험 점검 메모만 남겨줘"

    own_db_message = client.post(
        f"/workflow-sessions/{created['thread_id']}/messages",
        json={"text": "내 DB 조회"},
    )
    assert own_db_message.status_code == 202
    own_body = own_db_message.json()
    assert own_body["messages"][-1]["content"] == "내 DB 조회"
    assert own_body["messages"][-1]["metadata"]["kind"] == "user_reply"

    monkeypatch.setattr(settings, "app_env", "prod")
    no_auth = client.get("/customers")
    assert no_auth.status_code == 401
    monkeypatch.setattr(settings, "app_env", "local")
    app.dependency_overrides.clear()


def test_debug_endpoint_returns_graph_and_agent_artifacts(db: Session, monkeypatch):
    from fastapi.testclient import TestClient

    from app.api.deps import db_session
    from app.core.auth import Principal
    from app.core.config import settings
    from app.main import app
    from app.workflows.service import create_or_reuse_thread, trigger_event

    customer = _customers(db)[0]
    principal = Principal(subject="local-dev", role="operator")
    created = create_or_reuse_thread(db, customer_id=customer.id, principal=principal, force_new=True)
    trigger_event(
        db,
        graph_thread_id=created["thread_id"],
        principal=principal,
        payload={"kind": "portfolio_loss"},
    )
    operator_token = _jwt_for_email(db, "operator@jbwm.local")

    bind = db.get_bind()
    db.close()

    def override_db_session():
        with Session(bind) as route_db:
            yield route_db

    app.dependency_overrides[db_session] = override_db_session
    client = TestClient(app)
    debug = client.get(f"/workflow-sessions/{created['thread_id']}/debug")
    assert debug.status_code == 200
    body = debug.json()
    assert body["graph_snapshot"]["values"]["stage"] == "PolicyCheck"
    assert body["debug_agent_jobs"][0]["input_json"]["signal"]["kind"] == "portfolio_loss"
    assert body["debug_agent_jobs"][0]["output_json"]["plan"]["proposals"]
    assert body["debug_snapshots"][0]["context"]

    monkeypatch.setattr(settings, "app_env", "prod")
    blocked = client.get(
        f"/workflow-sessions/{created['thread_id']}/debug",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert blocked.status_code == 404
    monkeypatch.setattr(settings, "app_env", "local")
    app.dependency_overrides.clear()


def _assert_no_forbidden_keys(value):
    forbidden = {"api_body", "external_ref", "raw_ref"}
    if isinstance(value, dict):
        for key, child in value.items():
            assert key not in forbidden
            assert not key.endswith("_id")
            _assert_no_forbidden_keys(child)
    elif isinstance(value, list):
        for item in value:
            _assert_no_forbidden_keys(item)
