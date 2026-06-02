"""AgentReasoner 포트 — 공급자 무관 추론 인터페이스.

Codex/Gemini/Anthropic 등이 이 인터페이스를 구현한다. 도메인 코드는
구체 SDK가 아니라 이 포트에만 의존한다. (docs/04_AGENT_RUNTIME.md)
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

    if settings.reasoner == "codex":
        from app.agent.codex_adapter import CodexReasoner

        return CodexReasoner()
    from app.agent.stub_reasoner import StubReasoner

    return StubReasoner()
