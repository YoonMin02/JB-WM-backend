"""Policy Engine — 리스크 평가 → auto vs 고객승인 라우팅.

코드 규칙이다. 프롬프트로 LLM에 부탁하는 방식이 아니다. (docs/07_ACTION_EXECUTION)
"""
from __future__ import annotations

from dataclasses import dataclass

from app.planning.schemas import ActionProposalSchema

# 외부 효과가 명백한 고위험 액션 종류 (외부 효과 플래그와 별개로 강제 승인)
HIGH_RISK_KINDS = {"book_hospital", "submit_claim", "transfer_money", "rebalance_portfolio"}


@dataclass
class Routing:
    needs_approval: bool
    reason: str


def evaluate(proposal: ActionProposalSchema) -> Routing:
    """단일 제안의 라우팅 결정."""
    if proposal.has_external_effect:
        return Routing(True, "external_effect")
    if proposal.kind in HIGH_RISK_KINDS:
        return Routing(True, "high_risk_domain")
    return Routing(False, "no_side_effect")
