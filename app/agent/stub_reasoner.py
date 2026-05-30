"""StubReasoner — 결정론적 가짜 추론기.

Codex 호출 없이 슬라이스 1 루프를 끝까지 돌리고 테스트하기 위한 구현.
실제 추론은 CodexReasoner가 담당. 둘 다 동일한 AgentReasoner 포트를 구현한다.
"""
from __future__ import annotations

from app.agent.schemas import ActionProposalSchema, IntentInference, Plan


class StubReasoner:
    async def infer_intent(self, signal: dict, ctx: dict) -> IntentInference:
        payload = signal.get("payload", {})
        kind = str(payload.get("kind", "")).lower()
        text = str(payload.get("text", "")).lower()
        insurance = ctx.get("insurance", {})
        has_gap = bool(insurance.get("gaps_hint"))

        # 자산 신호(손실/상환압박/지출급증/소득감소) → AssetDefenseIntent (선제 메인)
        asset_signal = any(
            k in kind for k in ("portfolio_loss", "repayment", "spending", "income_drop")
        ) or any(w in text for w in ("지출", "상환", "손실"))
        if asset_signal:
            return IntentInference(
                state="AssetDefenseIntent",
                confidence=0.84,
                rationale="자산 변동(손실/현금흐름 압박)이 감지되어, 의료비 대비를 포함한 현금흐름 방어가 필요합니다.",
            )

        # 건강 이벤트(혈압/수면/의료비) + 보험 공백 → InsuranceIntent
        health_signal = any(k in kind for k in ("bp_", "sleep", "med_cost", "health"))
        if health_signal and has_gap:
            return IntentInference(
                state="InsuranceIntent",
                confidence=0.82,
                rationale="건강 이벤트가 감지되었고 현재 보험에 관련 보장 공백이 있어 보험 점검이 필요합니다.",
            )
        if "보험" in text or "insurance" in text:
            return IntentInference(
                state="InsuranceIntent", confidence=0.7, rationale="고객이 보험 확인을 요청했습니다."
            )
        if health_signal:
            return IntentInference(
                state="HealthCareIntent", confidence=0.6, rationale="건강 이벤트 감지."
            )
        return IntentInference(
            state="IntentUnknown",
            confidence=0.3,
            rationale="신호만으로 의도를 특정하기 어렵습니다.",
            clarifying_question="어떤 부분을 먼저 봐드릴까요? (보험 / 현금흐름 / 투자)",
        )

    async def generate_plan(self, intent: IntentInference, ctx: dict, memory: dict) -> Plan:
        if intent.state == "AssetDefenseIntent":
            return self._asset_defense_plan(ctx, memory)
        if intent.state != "InsuranceIntent":
            return Plan(explanation=f"{intent.state}는 아직 미구현입니다 (슬라이스 1~2 범위 밖).")

        insurance = ctx.get("insurance", {})
        gap = insurance.get("gaps_hint", "심혈관 특약 없음")

        proposals = [
            # 부작용 없는 분석 → AutoExecutable
            ActionProposalSchema(
                kind="report",
                summary=f"실손보험 보장 공백 분석 리포트 ({gap})",
                has_external_effect=False,
                rationale="현재 보장 범위와 건강 이벤트를 매칭한 분석 결과입니다.",
            ),
            # 외부 효과 있음 → NeedApproval (고객 승인 필요)
            ActionProposalSchema(
                kind="review_insurance",
                summary="심혈관 관련 실손 보험 청구 서류를 준비·접수합니다.",
                has_external_effect=True,
                params={"coverage": "실손", "reason": gap},
                rationale="보장 가능성이 있어 청구 절차 진행을 제안합니다. 실제 접수 전 고객 승인이 필요합니다.",
            ),
        ]

        # 개인화: 투자 보류 제약이 있으면 투자 관련 제안을 추가하지 않음 (이미 미포함)
        explanation = "건강 이벤트와 보험 공백을 근거로 보험 점검·청구를 제안합니다."
        if memory.get("constraints", {}).get("투자") == "보류":
            explanation += " (고객 제약에 따라 투자 조정 제안은 제외했습니다.)"
        return Plan(proposals=proposals, explanation=explanation)

    def _asset_defense_plan(self, ctx: dict, memory: dict) -> Plan:
        """자산 트리거 → 통합 회복탄력성 계획. 통계 앵커 + 지불의향·제약 개인화."""
        pop = ctx.get("population", {})
        avg_fund = pop.get("avg_emergency_fund_months", {}).get("value", {}).get("months")
        fund_src = pop.get("avg_emergency_fund_months", {}).get("source", "")
        high_risk = ctx.get("portfolio", {}).get("high_risk_weight", 0)
        gap = ctx.get("insurance", {}).get("gaps_hint")
        willingness = memory.get("medical_willingness", "moderate")
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
                rationale="상환·잠재 의료비 대비 현금흐름 플랜.",
            ),
        ]

        # 보장 공백 있으면 점검(외부 효과 → 승인). 지불의향이 낮으면 저비용 점검으로 한정.
        if gap:
            proposals.append(
                ActionProposalSchema(
                    kind="review_insurance",
                    summary=f"보장 공백({gap}) 점검 및 청구 가능성 확인",
                    has_external_effect=True,
                    params={"coverage": "실손", "willingness": willingness},
                    rationale="의료비 대비 보장을 점검합니다. 실제 청구 접수 전 고객 승인 필요.",
                )
            )

        # 개인화: 투자 보류가 아니면 리밸런싱 제안(외부 효과). 보류면 제외.
        explanation = f"자산 손실·현금흐름 압박을 통계 기준에 앵커해 대비책을 제안합니다. 지불의향={willingness}."
        if not invest_hold:
            proposals.append(
                ActionProposalSchema(
                    kind="rebalance_portfolio",
                    summary="고위험 비중을 낮춘 포트폴리오 대안",
                    has_external_effect=True,
                    rationale="손실 노출 축소를 위한 리밸런싱.",
                )
            )
        else:
            explanation += " (고객 제약 '투자 보류'에 따라 리밸런싱 제안은 제외)"

        # 의료 경계: 의료 권고가 아니라 '재무 대비 + 통계 참고'만. 처치 권고 없음.
        return Plan(proposals=proposals, explanation=explanation)
