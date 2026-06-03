"""SDK reasoner 스모크 테스트 (docs/CODEX_ADAPTER.md).

실제 SDK OAuth 세션을 사용해 `CodexReasoner` 포트를 호출한다. 다음을 검증:
1. seed/mock 데이터로 고객 컨텍스트 생성
2. `assess_need`가 `NeedAssessment`를 반환
3. 같은 thread id를 이어서 `generate_plan`에 전달
4. `Plan` 구조화 출력이 반환

실행:
    timeout 120s .venv/bin/python scripts/codex_smoke_test.py

주의:
    SDK/OAuth 진입부가 native subprocess에서 대기하면 Python 내부 timeout으로
    안정적으로 중단되지 않을 수 있다. 반드시 shell의 `timeout`으로 감싼다.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from sqlmodel import SQLModel, Session, create_engine, select
from sqlmodel.pool import StaticPool

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agent.codex_adapter import CodexReasoner  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402
from app.models.customer import Customer  # noqa: E402
from app.seed import seed_if_empty  # noqa: E402
from app.tools.data_tools import build_context  # noqa: E402


async def main() -> None:
    configure_logging()
    print("smoke: preparing in-memory seed data", flush=True)
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    # seed_if_empty는 app.seed.engine을 사용하므로 smoke용 in-memory engine으로 교체한다.
    import app.seed as seed_mod

    seed_mod.engine = engine
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    seed_if_empty()

    with Session(engine) as db:
        customer = db.exec(select(Customer)).one()
        ctx = build_context(db, customer.id)

    reasoner = CodexReasoner()
    signal = {"source": "event", "payload": {"kind": "portfolio_loss"}}
    print("smoke: calling assess_need", flush=True)
    assessment = await reasoner.assess_need(signal, ctx)
    first_thread_id = reasoner.last_thread_id
    print("thread.id.assess:", first_thread_id, flush=True)
    print("assessment:", assessment.model_dump_json(indent=2), flush=True)

    print("smoke: calling generate_plan with the same thread id", flush=True)
    plan = await reasoner.generate_plan(assessment, ctx, ctx.get("memory", {}), first_thread_id)
    print("thread.id.plan:", reasoner.last_thread_id, flush=True)
    print("plan:", json.dumps(plan.model_dump(), ensure_ascii=False, indent=2, default=str), flush=True)

    if not first_thread_id:
        raise RuntimeError("thread id가 반환되지 않았습니다.")
    if reasoner.last_thread_id != first_thread_id:
        raise RuntimeError("generate_plan이 assess_need의 thread를 재사용하지 않았습니다.")
    if not assessment.has_actionable_need:
        raise RuntimeError("mock portfolio_loss 신호에서 actionable need가 생성되지 않았습니다.")


if __name__ == "__main__":
    asyncio.run(main())
