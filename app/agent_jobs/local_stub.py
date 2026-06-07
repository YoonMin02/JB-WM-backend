"""Deterministic local planning worker for tests and the React demo."""
from __future__ import annotations

from app.planning.schemas import ActionProposalSchema, NeedAssessment, Plan
from app.signals.schemas import SignalEnvelope


def build_local_stub_output(signal: SignalEnvelope, context: dict) -> dict:
    kind = signal.kind.lower()
    insurance = context.get("insurance", {})
    has_gap = bool(insurance.get("gaps_hint"))
    memory = context.get("memory", {})

    asset_signal = any(
        marker in kind
        for marker in (
            "portfolio_loss",
            "repayment",
            "spending",
            "income_drop",
            "card_payment_pressure",
        )
    )
    if asset_signal:
        assessment = NeedAssessment(
            primary_need="investment_adjust" if "portfolio_loss" in kind else "cashflow",
            medical_cost_need="mid",
            insurance_need="mid" if has_gap else "low",
            cashflow_need="high",
            asset_defense_need="high",
            investment_adjust_need="high" if "portfolio_loss" in kind else "mid",
            life_plan_need="low",
            confidence=0.84,
            rationale="금융 API 데이터에서 현금흐름/자산방어 신호가 감지되었습니다.",
        )
        plan = _asset_plan(assessment, context, memory)
        return {
            "assessment": assessment.model_dump(),
            "plan": plan.model_dump(),
            "message": plan.explanation,
        }

    if has_gap or "insurance" in kind:
        assessment = NeedAssessment(
            primary_need="insurance",
            medical_cost_need="low",
            insurance_need="high",
            cashflow_need="mid",
            asset_defense_need="low",
            investment_adjust_need="none",
            life_plan_need="low",
            confidence=0.78,
            rationale="보험 보장 공백 또는 보험료 점검 필요성이 감지되었습니다.",
        )
        plan = _insurance_plan(assessment, context, memory)
        return {
            "assessment": assessment.model_dump(),
            "plan": plan.model_dump(),
            "message": plan.explanation,
        }

    assessment = NeedAssessment(
        primary_need="none",
        confidence=0.4,
        rationale="강한 조치 필요 신호는 없고 정기 점검 메시지만 생성합니다.",
        no_action=True,
    )
    plan = Plan(assessment=assessment, explanation="현재는 실행할 액션 없이 정기 점검만 기록했습니다.")
    return {"assessment": assessment.model_dump(), "plan": plan.model_dump(), "message": plan.explanation}


def _asset_plan(assessment: NeedAssessment, context: dict, memory: dict) -> Plan:
    high_risk = float(context.get("portfolio", {}).get("high_risk_weight") or 0)
    available_cash = int(
        context.get("accounts", {}).get("liquidity_summary", {}).get("available_cash_krw") or 0
    )
    upcoming_card = int(context.get("card_bills", {}).get("upcoming_card_payment_krw") or 0)
    gap = context.get("insurance", {}).get("gaps_hint")
    proposals = [
        ActionProposalSchema(
            kind="report",
            summary="현금흐름·자산방어 리스크 리포트 생성",
            has_external_effect=False,
            params={"available_cash_krw": available_cash, "upcoming_card_payment_krw": upcoming_card},
            rationale="계좌 잔액, 카드 청구, 대출 상환, 포트폴리오 위험도를 종합합니다.",
        ),
        ActionProposalSchema(
            kind="cashflow_plan",
            summary="3개월 현금흐름 방어 플랜 생성",
            has_external_effect=False,
            params={"available_cash_krw": available_cash},
            rationale="다음 결제와 상환 전 가용 현금 완충을 계산합니다.",
        ),
    ]
    if high_risk >= 0.55:
        proposals.append(
            ActionProposalSchema(
                kind="rebalance_portfolio",
                summary="고위험 비중을 45%로 낮추는 방어형 리밸런싱",
                has_external_effect=True,
                params={"target_high_risk_weight": 0.45, "target_low_risk_weight": 0.55},
                rationale="실제 포트폴리오 변경은 고객 승인 후 Executor만 수행합니다.",
            )
        )
    if gap:
        proposals.append(
            ActionProposalSchema(
                kind="review_insurance",
                summary=f"보장 공백 점검: {gap}",
                has_external_effect=True,
                params={"reason": gap, "willingness": memory.get("medical_willingness")},
                rationale="보장 점검 요청은 외부효과가 있을 수 있어 승인 후 진행합니다.",
            )
        )
    return Plan(
        proposals=proposals,
        explanation=(
            "금융 데이터 기준으로 현금흐름과 자산방어를 먼저 점검해야 합니다. "
            "자동 리포트는 생성하고, 실제 변경 액션은 승인 후 진행합니다."
        ),
        assessment=assessment,
    )


def _insurance_plan(assessment: NeedAssessment, context: dict, memory: dict) -> Plan:
    gap = context.get("insurance", {}).get("gaps_hint") or "보험 보장 공백"
    proposals = [
        ActionProposalSchema(
            kind="report",
            summary=f"보험 보장 공백 분석 리포트 ({gap})",
            has_external_effect=False,
            rationale="현재 보험 목록과 납입 정보를 정규화해 공백을 요약합니다.",
        ),
        ActionProposalSchema(
            kind="review_insurance",
            summary=f"보장 공백 점검 요청: {gap}",
            has_external_effect=True,
            params={"reason": gap, "willingness": memory.get("medical_willingness")},
            rationale="보험 점검/청구 준비는 고객 승인 후 Executor가 처리합니다.",
        ),
    ]
    return Plan(
        proposals=proposals,
        explanation="보험 데이터에서 점검할 항목이 감지되어 리포트와 승인 필요 액션을 준비했습니다.",
        assessment=assessment,
    )

