"""AgentReasoner port — provider-neutral one-shot reasoning interface.

JB-WM owns session continuity in the DB. A reasoner call is a single structured
LLM run over an explicit context pack; it must not own workflow state, tools, or
execution authority.
"""
from __future__ import annotations

from typing import Protocol

from app.agent.schemas import NeedAssessment, Plan


class CustomerContext(Protocol):
    """reasoner에 주입되는 읽기 전용 고객 컨텍스트 (도구가 채움)."""

    customer_id: str
    profile: dict
    health: dict
    insurance: dict
    loans: dict
    memory: dict


class AgentReasoner(Protocol):
    """추론 백엔드. 판단·계획만 한다. 상태 변경·실행은 하지 않는다."""

    async def assess_need(self, signal: dict, ctx: dict) -> NeedAssessment:
        """신호 + 읽기 전용 컨텍스트 → 통합 필요도 평가."""
        ...

    async def generate_plan(self, assessment: NeedAssessment, ctx: dict, memory: dict) -> Plan:
        """통합 필요도 평가 + 컨텍스트 + 장기 메모리(개인화) → 액션 제안 계획."""
        ...


def get_reasoner() -> AgentReasoner:
    """설정에 따라 reasoner 구현 선택. 여기가 유일한 분기점."""
    from app.core.config import settings

    if settings.reasoner == "pydantic_ai":
        from app.agent.pydantic_ai_reasoner import PydanticAIReasoner

        return PydanticAIReasoner()
    from app.agent.stub_reasoner import StubReasoner

    return StubReasoner()
