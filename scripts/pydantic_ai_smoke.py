"""PydanticAI reasoner smoke test.

Requires:
    REASONER=pydantic_ai
    codex login

Run:
    uv run python scripts/pydantic_ai_smoke.py
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

from app.agent.context_builder import build_agent_context  # noqa: E402
from app.agent.pydantic_ai_reasoner import PydanticAIReasoner  # noqa: E402
from app.models.agent import AgentSession  # noqa: E402
from app.models.customer import Customer  # noqa: E402
from app.seed import seed_if_empty  # noqa: E402
from app.state_machine.states import State  # noqa: E402


async def main() -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    import app.models  # noqa: F401
    import app.seed as seed_mod

    seed_mod.engine = engine
    SQLModel.metadata.create_all(engine)
    seed_if_empty()

    with Session(engine) as db:
        customer = db.exec(select(Customer)).one()
        session = AgentSession(customer_id=customer.id, state=State.MONITORING)
        db.add(session)
        db.commit()
        db.refresh(session)
        signal = {"source": "event", "payload": {"kind": "portfolio_loss"}}
        context = build_agent_context(db, session, current_signal=signal)

    reasoner = PydanticAIReasoner()
    assessment = await reasoner.assess_need(signal, context)
    plan = await reasoner.generate_plan(assessment, context, context.get("memory", {}))

    print("assessment:")
    print(assessment.model_dump_json(indent=2))
    print("plan:")
    print(json.dumps(plan.model_dump(), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
