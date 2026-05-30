"""에이전트 구조화 입출력 스키마 (Pydantic, DB 아님).

reasoner는 자유 텍스트가 아니라 이 스키마로 결과를 반환한다.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

IntentState = Literal[
    "HealthCareIntent",
    "InsuranceIntent",
    "AssetDefenseIntent",
    "InvestmentAdjustIntent",
    "LifePlanIntent",
    "IntentUnknown",
]

ActionKind = Literal[
    "book_hospital",
    "review_insurance",
    "cashflow_plan",
    "rebalance_portfolio",
    "notify",
    "report",
]


class IntentInference(BaseModel):
    state: IntentState
    confidence: float = 0.0
    rationale: str = ""
    clarifying_question: str | None = None

    @property
    def is_unknown(self) -> bool:
        return self.state == "IntentUnknown"


class ActionProposalSchema(BaseModel):
    kind: ActionKind
    summary: str
    has_external_effect: bool = False
    params: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class Plan(BaseModel):
    proposals: list[ActionProposalSchema] = Field(default_factory=list)
    explanation: str = ""


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

    def to_plan(self) -> Plan:
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
        )
