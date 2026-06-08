"""Structured planning output shared by agent jobs and workflow validators.

The sandboxed agent job may interpret customer context, but it only returns
these schemas. State changes, approval, and execution remain owned by code.
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
    """Integrated need assessment for one scoped customer signal."""

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
    """Candidate action. This is a proposal, not execution authority."""

    kind: ActionKind
    summary: str
    has_external_effect: bool = False
    params: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class Plan(BaseModel):
    proposals: list[ActionProposalSchema] = Field(default_factory=list)
    explanation: str = ""
    assessment: NeedAssessment | None = None


class AgentJobOutput(BaseModel):
    assessment: NeedAssessment
    plan: Plan
    message: str = ""
