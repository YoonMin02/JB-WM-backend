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
        if intent.state != "InsuranceIntent":
            return Plan(explanation="슬라이스 1은 InsuranceIntent만 구현되어 있습니다.")

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
