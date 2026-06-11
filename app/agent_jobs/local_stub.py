"""Deterministic local planning worker for tests and the React demo."""
from __future__ import annotations

from app.planning.schemas import (
    ActionProposalSchema,
    ExecutionParams,
    ExecutionStep,
    NeedAssessment,
    Plan,
    PlanStrategy,
)
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
    plan = Plan(
        strategy=PlanStrategy(
            title="정기 점검 유지",
            objective="강한 위험 신호가 없으므로 기존 상태를 기록하고 다음 변화를 기다립니다.",
            priority_order=["none"],
            rationale="감지된 신호가 약하고 실행 가능한 조치 필요도가 낮습니다.",
            risk_controls=["고객 승인 없는 외부 실행 금지"],
        ),
        assessment=assessment,
        explanation="현재는 실행할 액션 없이 정기 점검만 기록했습니다.",
    )
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
            execution_summary="가용 현금, 카드 청구, 대출 상환, 포트폴리오 위험도를 하나의 리포트로 정리합니다.",
            execution_steps=[
                ExecutionStep(
                    action="create_report",
                    target="현금흐름·자산방어 리포트",
                    amount_krw=None,
                    current_value=f"가용 현금 {available_cash:,}원 / 예정 카드결제 {upcoming_card:,}원",
                    target_value="리스크 요약 기록",
                    reason="승인 전 고객에게 현재 부담 요인을 먼저 설명하기 위해 자동 생성합니다.",
                    requires_customer_approval=False,
                )
            ],
            execution_params=ExecutionParams(
                liquidity_buffer_krw=available_cash,
                report_focus="cashflow_asset_defense",
            ),
            params={"available_cash_krw": available_cash, "upcoming_card_payment_krw": upcoming_card},
            rationale="계좌 잔액, 카드 청구, 대출 상환, 포트폴리오 위험도를 종합합니다.",
        ),
        ActionProposalSchema(
            kind="cashflow_plan",
            summary="3개월 현금흐름 방어 플랜 생성",
            has_external_effect=False,
            execution_summary="향후 3개월 동안 결제·상환·의료비에 대비할 현금 완충 목표를 계산합니다.",
            execution_steps=[
                ExecutionStep(
                    action="create_report",
                    target="3개월 현금흐름 방어 플랜",
                    amount_krw=available_cash,
                    current_value=f"가용 현금 {available_cash:,}원",
                    target_value="3개월 완충 목표와 부족분 계산",
                    reason="투자 조정 전에 생활비와 의료비 지출을 버틸 수 있는지 확인합니다.",
                    requires_customer_approval=False,
                )
            ],
            execution_params=ExecutionParams(
                liquidity_buffer_krw=available_cash,
                report_focus="three_month_cashflow",
            ),
            params={"available_cash_krw": available_cash},
            rationale="다음 결제와 상환 전 가용 현금 완충을 계산합니다.",
        ),
    ]
    if high_risk >= 0.55:
        target_high = 0.45
        target_low = 0.55
        total_value = int(context.get("portfolio", {}).get("total_value") or 0)
        current_high_amount = int(total_value * high_risk)
        target_high_amount = int(total_value * target_high)
        reduction_amount = max(0, current_high_amount - target_high_amount)
        proposals.append(
            ActionProposalSchema(
                kind="rebalance_portfolio",
                summary="고위험 자산 일부를 현금성·저위험 자산으로 옮기는 방어형 리밸런싱",
                has_external_effect=True,
                execution_summary=(
                    f"고위험 비중을 현재 {round(high_risk * 100)}% 수준에서 "
                    f"{round(target_high * 100)}% 수준으로 낮춥니다."
                ),
                execution_steps=[
                    ExecutionStep(
                        action="sell",
                        target="고위험 보유자산 묶음",
                        amount_krw=reduction_amount,
                        current_value=f"{round(high_risk * 100)}%",
                        target_value=f"{round(target_high * 100)}%",
                        reason="최근 손실 신호와 현금흐름 압박을 반영해 변동성이 큰 자산을 줄입니다.",
                        requires_customer_approval=True,
                    ),
                    ExecutionStep(
                        action="move_to_cash",
                        target="현금성·저위험 자산 묶음",
                        amount_krw=reduction_amount,
                        current_value=f"{round((1 - high_risk) * 100)}%",
                        target_value=f"{round(target_low * 100)}%",
                        reason="의료비·카드결제·대출상환에 대응할 수 있는 방어 여력을 확보합니다.",
                        requires_customer_approval=True,
                    ),
                ],
                execution_params=ExecutionParams(
                    target_high_risk_weight=target_high,
                    target_low_risk_weight=target_low,
                    liquidity_buffer_krw=available_cash,
                    notes="mock 리밸런싱은 위험등급별 보유금액을 목표 비중으로 재배분합니다.",
                ),
                params={"target_high_risk_weight": target_high, "target_low_risk_weight": target_low},
                rationale="방향은 자산방어와 현금흐름 안정화이며, 실제 포트폴리오 변경은 고객 승인 후 Executor만 수행합니다.",
            )
        )
    if gap:
        proposals.append(
            ActionProposalSchema(
                kind="review_insurance",
                summary=f"보장 공백 점검: {gap}",
                has_external_effect=True,
                execution_summary=f"{gap} 항목을 중심으로 기존 보험 보장과 의료비 위험을 대조합니다.",
                execution_steps=[
                    ExecutionStep(
                        action="review",
                        target=gap,
                        amount_krw=None,
                        current_value="미보유 또는 부족",
                        target_value="보장 점검 완료",
                        reason="건강 이벤트와 현금흐름 부담이 겹칠 때 보장 공백이 직접 부담으로 이어질 수 있습니다.",
                        requires_customer_approval=True,
                    )
                ],
                execution_params=ExecutionParams(
                    insurance_review_reason=gap,
                    notes=f"medical_willingness={memory.get('medical_willingness')}",
                ),
                params={"reason": gap, "willingness": memory.get("medical_willingness")},
                rationale="방향은 보험 공백 확인과 의료비 부담 완화이며, 보장 점검 요청은 승인 후 진행합니다.",
            )
        )
    return Plan(
        strategy=PlanStrategy(
            title="현금흐름을 지키면서 고위험 노출을 낮추기",
            objective="손실 이벤트 이후 의료비·결제·상환에 대응할 유동성을 확보하고 포트폴리오 변동성을 낮춥니다.",
            priority_order=["cashflow", "asset_defense", "investment_adjust", "insurance", "medical_cost"],
            rationale="가용 현금, 카드 청구액, 포트폴리오 고위험 비중을 함께 보면 단순 수익률 회복보다 방어 여력 확보가 우선입니다.",
            risk_controls=[
                "외부 효과가 있는 포트폴리오 변경은 고객 승인 후 실행",
                "의료 권고가 아닌 재무 대비 관점으로만 판단",
            ],
        ),
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
            execution_summary=f"{gap} 여부와 현재 보험 보장 한도를 리포트로 정리합니다.",
            execution_steps=[
                ExecutionStep(
                    action="create_report",
                    target="보험 보장 공백 분석 리포트",
                    amount_krw=None,
                    current_value=gap,
                    target_value="보장 공백 요약 기록",
                    reason="외부 점검 요청 전에 현재 보장 상태를 고객에게 설명하기 위해 자동 생성합니다.",
                    requires_customer_approval=False,
                )
            ],
            execution_params=ExecutionParams(
                insurance_review_reason=gap,
                report_focus="insurance_gap",
            ),
            rationale="현재 보험 목록과 납입 정보를 정규화해 공백을 요약합니다.",
        ),
        ActionProposalSchema(
            kind="review_insurance",
            summary=f"보장 공백 점검 요청: {gap}",
            has_external_effect=True,
            execution_summary=f"{gap}을 중심으로 기존 보장 한도와 예상 의료비 부담을 비교합니다.",
            execution_steps=[
                ExecutionStep(
                    action="review",
                    target=gap,
                    amount_krw=None,
                    current_value="공백 감지",
                    target_value="점검 요청 및 보장 검토",
                    reason="현재 보험 목록에서 해당 보장이 확인되지 않아 의료비 부담이 커질 수 있습니다.",
                    requires_customer_approval=True,
                )
            ],
            execution_params=ExecutionParams(
                insurance_review_reason=gap,
                notes=f"medical_willingness={memory.get('medical_willingness')}",
            ),
            params={"reason": gap, "willingness": memory.get("medical_willingness")},
            rationale="방향은 보장 공백 확인과 의료비 대비이며, 보험 점검/청구 준비는 고객 승인 후 Executor가 처리합니다.",
        ),
    ]
    return Plan(
        strategy=PlanStrategy(
            title="보험 보장 공백을 먼저 확인하기",
            objective="현재 질병·의료비 위험과 보험 보장 목록을 대조해 고객 부담으로 남는 항목을 줄입니다.",
            priority_order=["insurance", "medical_cost", "cashflow"],
            rationale="보험 공백 신호가 명확하므로 투자 조정보다 보장 확인과 의료비 부담 점검이 우선입니다.",
            risk_controls=["보험 가입·변경은 고객 승인과 별도 설명 없이 실행하지 않음"],
        ),
        proposals=proposals,
        explanation="보험 데이터에서 점검할 항목이 감지되어 리포트와 승인 필요 액션을 준비했습니다.",
        assessment=assessment,
    )
