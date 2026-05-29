"""상태 전이 적용 + 가드. LLM이 아니라 이 코드가 전이를 강제한다."""
from __future__ import annotations

from sqlmodel import Session

from app.core.logging import logger
from app.models.agent import AgentEvent, AgentSession
from app.models.base import utcnow
from app.state_machine.states import TRANSITIONS, State


class InvalidTransition(Exception):
    """허용되지 않은 상태 전이."""


def can_transition(current: State, target: State) -> bool:
    return target in TRANSITIONS.get(current, set())


def transition(db: Session, session: AgentSession, target: State, *, detail: dict | None = None) -> AgentSession:
    """세션 상태를 target으로 전이. 허용되지 않으면 InvalidTransition."""
    current = State(session.state)
    if not can_transition(current, target):
        raise InvalidTransition(f"{current} -> {target} 은(는) 허용되지 않음")

    session.state = target
    session.updated_at = utcnow()
    db.add(session)
    db.add(
        AgentEvent(
            session_id=session.id,
            type="state_transition",
            detail={"from": str(current), "to": str(target), **(detail or {})},
        )
    )
    db.commit()
    db.refresh(session)
    logger.info("session %s: %s -> %s", session.id, current, target)
    return session


def log_event(db: Session, session_id: str, type_: str, detail: dict) -> None:
    db.add(AgentEvent(session_id=session_id, type=type_, detail=detail))
    db.commit()
