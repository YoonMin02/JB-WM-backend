"""에이전트 구조화 입출력 스키마 (Pydantic, DB 아님).

reasoner는 자유 텍스트가 아니라 이 스키마로 결과를 반환한다.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

NeedLevel = Literal["none", "low", "mid", "high"]
PrimaryNeed = Literal[
    "medical_cost",
    "insurance",
    "cashflow",
    "asset_defense",
    "investment_adjust",
    "life_plan",
    "preference_update",
    "none",
]

ActionKind = Literal[
    "book_hospital",
    "review_insurance",
    "cashflow_plan",
    "rebalance_portfolio",
    "notify",
    "report",
]


class NeedAssessment(BaseModel):
    """통합 필요도 평가. FSM 상태가 아니라 AssessNeed 단계의 구조화 출력."""

    medical_cost_need: NeedLevel = "none"
    insurance_need: NeedLevel = "none"
    cashflow_need: NeedLevel = "none"
    asset_defense_need: NeedLevel = "none"
    investment_adjust_need: NeedLevel = "none"
    life_plan_need: NeedLevel = "none"
    primary_need: PrimaryNeed = "none"
    confidence: float = 0.0
    rationale: str = ""
    preference_update_only: bool = False
    no_action: bool = False
    clarifying_question: str | None = None

    @property
    def needs_clarification(self) -> bool:
        return self.clarifying_question is not None

    @property
    def has_actionable_need(self) -> bool:
        return any(
            level != "none"
            for level in (
                self.medical_cost_need,
                self.insurance_need,
                self.cashflow_need,
                self.asset_defense_need,
                self.investment_adjust_need,
                self.life_plan_need,
            )
        )


class ActionProposalSchema(BaseModel):
    kind: ActionKind
    summary: str
    has_external_effect: bool = False
    params: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class Plan(BaseModel):
    proposals: list[ActionProposalSchema] = Field(default_factory=list)
    explanation: str = ""
    assessment: NeedAssessment | None = None


# ── LLM 출력 전용 스키마 (strict 호환: free-form dict 없음) ──
# OpenAI strict 구조화출력은 모든 object에 additionalProperties=false를 요구하므로
# free-form `params: dict`를 LLM 스키마에서 제외한다. params는 서버가 채운다.


class LLMActionProposal(BaseModel):
    kind: ActionKind
    summary: str
    has_external_effect: bool
    rationale: str


class LLMPlan(BaseModel):
    proposals: list[LLMActionProposal]
    explanation: str

    def to_plan(self, assessment: NeedAssessment | None = None) -> Plan:
        return Plan(
            proposals=[
                ActionProposalSchema(
                    kind=p.kind,
                    summary=p.summary,
                    has_external_effect=p.has_external_effect,
                    params={},
                    rationale=p.rationale,
                )
                for p in self.proposals
            ],
            explanation=self.explanation,
            assessment=assessment,
        )
