"""StubReasoner — 결정론적 가짜 추론기."""
from __future__ import annotations

from app.agent.schemas import ActionProposalSchema, NeedAssessment, Plan


def _format_krw(value: int | float) -> str:
    return f"{int(value):,}원"


class StubReasoner:
    async def assess_need(self, signal: dict, ctx: dict) -> NeedAssessment:
        payload = signal.get("payload", {})
        kind = str(payload.get("kind", "")).lower()
        text = str(payload.get("text", "")).lower()
        insurance = ctx.get("insurance", {})
        has_gap = bool(insurance.get("gaps_hint"))

        # 자산 신호(손실/상환압박/지출급증/소득감소) → 통합 필요도 평가 (선제 메인)
        asset_signal = any(
            k in kind for k in ("portfolio_loss", "repayment", "spending", "income_drop")
        ) or any(w in text for w in ("지출", "상환", "손실"))
        if asset_signal:
            investment_need = "high" if "portfolio_loss" in kind or "손실" in text else "mid"
            return NeedAssessment(
                primary_need="investment_adjust" if investment_need == "high" else "cashflow",
                medical_cost_need="mid",
                insurance_need="mid" if has_gap else "low",
                cashflow_need="high",
                asset_defense_need="high",
                investment_adjust_need=investment_need,
                life_plan_need="low",
                confidence=0.84,
                rationale=(
                    "투자 손실/현금흐름 압박이 감지되어, 의료비 대비와 함께 "
                    "고위험 비중 축소 중심의 투자전략 재점검이 필요합니다."
                ),
            )

        # 건강 이벤트(혈압/수면/의료비) + 보험 공백 → 의료비/보험 필요도 상승
        health_signal = any(k in kind for k in ("bp_", "sleep", "med_cost", "health"))
        if health_signal and has_gap:
            return NeedAssessment(
                primary_need="insurance",
                medical_cost_need="mid",
                insurance_need="high",
                cashflow_need="mid",
                asset_defense_need="low",
                investment_adjust_need="none",
                life_plan_need="low",
                confidence=0.82,
                rationale="건강 이벤트가 감지되었고 현재 보험에 관련 보장 공백이 있어 보험 점검이 필요합니다.",
            )
        if "보험" in text or "insurance" in text:
            return NeedAssessment(
                primary_need="insurance",
                insurance_need="high",
                medical_cost_need="low",
                cashflow_need="low",
                confidence=0.7,
                rationale="고객이 보험 확인을 직접 요청했습니다.",
            )
        if health_signal:
            return NeedAssessment(
                primary_need="medical_cost",
                medical_cost_need="mid",
                insurance_need="low",
                cashflow_need="low",
                confidence=0.6,
                rationale="건강 이벤트가 감지되어 의료비 감내 범위 검토가 필요합니다.",
            )
        if "보수" in text or "투자" in text:
            return NeedAssessment(
                primary_need="preference_update",
                investment_adjust_need="low",
                preference_update_only=True,
                confidence=0.72,
                rationale="고객 발화가 투자 성향/제약 변경에 가깝습니다.",
            )
        return NeedAssessment(
            confidence=0.3,
            rationale="신호만으로 의도를 특정하기 어렵습니다.",
            clarifying_question="어떤 부분을 먼저 봐드릴까요? (보험 / 현금흐름 / 투자)",
        )

    async def generate_plan(self, assessment: NeedAssessment, ctx: dict, memory: dict) -> Plan:
        if assessment.asset_defense_need in ("mid", "high") or assessment.investment_adjust_need in ("mid", "high"):
            return self._asset_defense_plan(assessment, ctx, memory)
        if assessment.insurance_need == "none" and assessment.medical_cost_need == "none":
            return Plan(assessment=assessment, explanation="실행 가능한 필요도가 낮아 제안을 생성하지 않았습니다.")

        insurance = ctx.get("insurance", {})
        gap = insurance.get("gaps_hint", "심혈관 특약 없음")
        willingness = memory.get("medical_willingness", "moderate")
        one_time_budget = int(memory.get("medical_one_time_budget_krw") or 0)
        monthly_budget = int(memory.get("monthly_medical_budget_krw") or 0)
        budget_ratio = float(memory.get("medical_budget_ratio") or 0)

        proposals = [
            # 부작용 없는 분석 → AutoExecutable
            ActionProposalSchema(
                kind="report",
                summary=f"실손보험 보장 공백 분석 리포트 ({gap})",
                has_external_effect=False,
                rationale="현재 보장 범위와 건강 이벤트, 의료비 감내 범위를 매칭한 분석 결과입니다.",
            ),
            # 외부 효과 있음 → NeedApproval (고객 승인 필요)
            ActionProposalSchema(
                kind="review_insurance",
                summary="심혈관 관련 실손 보험 청구 서류를 준비·접수합니다.",
                has_external_effect=True,
                params={
                    "coverage": "실손",
                    "reason": gap,
                    "willingness": willingness,
                    "one_time_budget_krw": one_time_budget,
                    "monthly_budget_krw": monthly_budget,
                    "budget_ratio": budget_ratio,
                },
                rationale=(
                    "보장 가능성이 있어 청구 절차 진행을 제안합니다. "
                    "실제 접수 전 고객 승인이 필요합니다."
                ),
            ),
        ]

        # 개인화: 투자 보류 제약이 있으면 투자 관련 제안을 추가하지 않음 (이미 미포함)
        explanation = (
            "건강 이벤트와 보험 공백을 근거로 보험 점검·청구를 제안합니다. "
            f"의료비 감내범위=일회성 {_format_krw(one_time_budget)}, "
            f"월 {_format_krw(monthly_budget)}, 현금흐름 {budget_ratio * 100:.0f}%."
        )
        if memory.get("constraints", {}).get("투자") == "보류":
            explanation += " (고객 제약에 따라 투자 조정 제안은 제외했습니다.)"
        return Plan(proposals=proposals, explanation=explanation, assessment=assessment)

    def _asset_defense_plan(self, assessment: NeedAssessment, ctx: dict, memory: dict) -> Plan:
        """자산 트리거 → 통합 회복탄력성 계획. 통계 앵커 + 지불의향·제약 개인화."""
        pop = ctx.get("population", {})
        avg_fund = pop.get("avg_emergency_fund_months", {}).get("value", {}).get("months")
        fund_src = pop.get("avg_emergency_fund_months", {}).get("source", "")
        high_risk = ctx.get("portfolio", {}).get("high_risk_weight", 0)
        gap = ctx.get("insurance", {}).get("gaps_hint")
        willingness = memory.get("medical_willingness", "moderate")
        one_time_budget = int(memory.get("medical_one_time_budget_krw") or 0)
        monthly_budget = int(memory.get("monthly_medical_budget_krw") or 0)
        budget_ratio = float(memory.get("medical_budget_ratio") or 0)
        invest_hold = memory.get("constraints", {}).get("투자") == "보류"

        anchor = (
            f"또래(65–69) 권장 비상자금 {avg_fund}개월({fund_src}) 대비 현금 완충이 부족"
            if avg_fund
            else "현금 완충 부족"
        )

        proposals = [
            # 통계 앵커 분석 리포트 (부작용 없음 → auto)
            ActionProposalSchema(
                kind="report",
                summary=f"현금흐름·의료 대비 리스크 분석 ({anchor}, 고위험 비중 {int(high_risk*100)}%)",
                has_external_effect=False,
                rationale=f"포트폴리오 손실 + 3개월 후 상환 + 통계 기준({fund_src})을 종합한 근거.",
            ),
            # 비상자금 플랜 (내부 계산 → auto)
            ActionProposalSchema(
                kind="cashflow_plan",
                summary="3개월 비상자금 확보 플랜 생성",
                has_external_effect=False,
                params={
                    "one_time_medical_budget_krw": one_time_budget,
                    "monthly_medical_budget_krw": monthly_budget,
                    "medical_budget_ratio": budget_ratio,
                },
                rationale=(
                    "상환·잠재 의료비 대비 현금흐름 플랜. "
                    f"고객 의료비 감내범위는 일회성 {_format_krw(one_time_budget)}, "
                    f"월 {_format_krw(monthly_budget)}, 현금흐름 {budget_ratio * 100:.0f}%입니다."
                ),
            ),
        ]

        # 보장 공백 있으면 점검(외부 효과 → 승인). 지불의향이 낮으면 저비용 점검으로 한정.
        if gap:
            proposals.append(
                ActionProposalSchema(
                    kind="review_insurance",
                    summary=f"보장 공백({gap}) 점검 및 청구 가능성 확인",
                    has_external_effect=True,
                    params={
                        "coverage": "실손",
                        "willingness": willingness,
                        "one_time_budget_krw": one_time_budget,
                        "monthly_budget_krw": monthly_budget,
                        "budget_ratio": budget_ratio,
                    },
                    rationale="의료비 대비 보장을 점검합니다. 실제 청구 접수 전 고객 승인 필요.",
                )
            )

        # 투자 손실 신호에서는 고객의 '투자 보류' 제약을 신규 매수 금지가 아니라
        # 고위험 노출 축소만 허용하는 안전 범위로 해석한다.
        explanation = (
            "자산 손실·현금흐름 압박을 통계 기준에 앵커해 대비책을 제안합니다. "
            f"지불의향={willingness}, 의료비 감내범위=일회성 {_format_krw(one_time_budget)}, "
            f"월 {_format_krw(monthly_budget)}, 현금흐름 {budget_ratio * 100:.0f}%."
        )
        if invest_hold:
            explanation += " 고객 제약 '투자 보류'는 신규 위험자산 확대 금지로 반영하고, 손실 방어용 축소안만 제안합니다."

        rebalance = ActionProposalSchema(
            kind="rebalance_portfolio",
            summary="투자 손실 대응: 고위험 비중 70% → 45% 방어형 리밸런싱",
            has_external_effect=True,
            params={
                "target_high_risk_weight": 0.45,
                "target_low_risk_weight": 0.55,
                "mode": "risk_reduction",
            },
            rationale="현재 고위험 비중이 높아 추가 손실 노출을 줄이는 투자전략 조정입니다. 고객 승인 전에는 실행하지 않습니다.",
        )
        # 승인 대기 1순위가 투자전략이 되도록 보험 점검보다 앞에 둔다.
        insert_at = 2
        proposals.insert(insert_at, rebalance)
        proposals.append(
            ActionProposalSchema(
                kind="notify",
                summary="담당 PB에게 방어형 투자전략 검토 요청",
                has_external_effect=True,
                params={"channel": "advisor_task", "topic": "portfolio_loss_defense"},
                rationale="리밸런싱 실행 전 사람이 검토할 수 있도록 담당자에게 검토 태스크를 남깁니다.",
            )
        )

        # 의료 경계: 의료 권고가 아니라 '재무 대비 + 통계 참고'만. 처치 권고 없음.
        return Plan(proposals=proposals, explanation=explanation, assessment=assessment)
