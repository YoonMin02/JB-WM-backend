"""슬라이스 1 종단 테스트 — StubReasoner로 InsuranceIntent 루프 1바퀴.

SQLite in-memory로 DB 격리. PostgreSQL 불필요.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine
from sqlmodel.pool import StaticPool


@pytest.fixture
def client(monkeypatch):
    # 격리된 in-memory DB로 교체
    import app.core.database as database

    test_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    monkeypatch.setattr(database, "engine", test_engine)

    import app.models  # noqa: F401  테이블 등록

    SQLModel.metadata.create_all(test_engine)

    # seed / data_tools / orchestrator가 참조하는 engine도 교체
    import app.seed as seed_mod

    monkeypatch.setattr(seed_mod, "engine", test_engine)

    from app.main import app

    with TestClient(app) as c:
        yield c


def _seed_customer(client) -> str:
    return client.get("/customers").json()[0]["id"]


def test_capability_no_execution_tools():
    """에이전트 도구 표면에 실행 동사가 없어야 한다 (capability 회귀)."""
    from app.tools import data_tools

    names = [n for n in dir(data_tools) if not n.startswith("_")]
    for verb in ("book_", "submit_", "transfer_", "change_"):
        assert not any(n.startswith(verb) for n in names), f"실행 도구 노출됨: {verb}"


def test_slice1_insurance_approval_flow(client):
    customer_id = _seed_customer(client)

    # 1. 세션 생성 — Monitoring
    s = client.post(f"/customers/{customer_id}/agent-sessions").json()
    sid = s["session_id"]
    assert s["state"] == "Monitoring"

    # 2. 건강 이벤트 신호 주입 → InsuranceIntent → 계획 → 승인 대기
    r = client.post(
        f"/agent-sessions/{sid}/signals",
        json={"source": "event", "payload": {"kind": "bp_rising"}},
    ).json()
    assert r["state"] == "UserApproval"
    assert r["pending_proposal"] is not None
    assert r["pending_proposal"]["has_external_effect"] is True
    assert "approve" in r["allowed_actions"]

    # 부작용 없는 report 제안은 이미 자동 실행됨
    proposals = client.get(f"/agent-sessions/{sid}/proposals").json()["proposals"]
    assert any(p["kind"] == "report" and p["status"] == "executed" for p in proposals)

    # 3. 고객 승인 → 실행(Executor, LLM 미경유) → 루프 종료 → Monitoring
    pid = r["pending_proposal"]["id"]
    done = client.post(f"/proposals/{pid}/approve").json()
    assert done["state"] == "Monitoring"
    assert done["pending_proposal"] is None

    # 실행된 청구 제안 확인
    proposals = client.get(f"/agent-sessions/{sid}/proposals").json()["proposals"]
    claim = next(p for p in proposals if p["kind"] == "review_insurance")
    assert claim["status"] == "executed"

    # 4. 감사 타임라인에 전 구간 기록
    events = client.get(f"/agent-sessions/{sid}/events").json()["events"]
    types = [e["type"] for e in events]
    assert "intent" in types and "plan" in types and "execution" in types
    assert types.count("state_transition") >= 6


def test_reject_flow(client):
    customer_id = _seed_customer(client)
    sid = client.post(f"/customers/{customer_id}/agent-sessions").json()["session_id"]
    r = client.post(
        f"/agent-sessions/{sid}/signals", json={"source": "event", "payload": {"kind": "bp_rising"}}
    ).json()
    pid = r["pending_proposal"]["id"]
    done = client.post(f"/proposals/{pid}/reject").json()
    assert done["state"] == "Monitoring"
    proposals = client.get(f"/agent-sessions/{sid}/proposals").json()["proposals"]
    claim = next(p for p in proposals if p["kind"] == "review_insurance")
    assert claim["status"] == "rejected"
