"""PydanticAI reasoner implementation over Codex SDK transport.

The model receives an explicit DB-built context pack on every run. It does not
own a long-lived provider thread and does not receive DB/tool execution access.
"""
from __future__ import annotations

import json
import threading
import time
from typing import TypeVar

from pydantic import BaseModel

from app.agent.errors import ReasonerOutputError, ReasonerRateLimited, ReasonerUnavailable
from app.agent.schemas import LLMPlan, NeedAssessment, Plan
from app.core.config import settings
from app.core.logging import logger

T = TypeVar("T", bound=BaseModel)

SYSTEM_PROMPT = """\
당신은 JB WM의 분석 보조 에이전트입니다.

권한 경계:
- 고객 데이터, 이전 대화, 판단 기록은 모두 backend가 제공한 JSON context 안에서만 사용합니다.
- DB, 파일시스템, 외부 도구/API, 예약/송금/청구/포트폴리오 변경 도구가 있다고 가정하지 마세요.
- 실제 실행은 하지 않습니다. 실행 가능성이 있는 것은 ActionProposal로만 제안합니다.
- 의료 권고를 생성하지 않습니다. 의료 선택은 고객과 의료 전문가의 영역이며, 당신은 재무 대비,
  보험/현금흐름/자산방어/투자전략/생애설계 관점의 판단만 합니다.

판단 원칙:
- 고객의 건강과 자산을 분리하지 말고 하나의 통합 회복탄력성 상태로 봅니다.
- 신호를 단일 intent로 좁히지 말고 medical_cost, insurance, cashflow, asset_defense,
  investment_adjust, life_plan 필요도를 함께 봅니다.
- 투자전략은 의료비/보험/현금흐름/자산방어/생애설계 판단 결과를 종합한 뒤 제안합니다.
- policy_context에 회사 규정/내규/상품 제한이 있으면 우선 반영합니다.
- 이전 proposal_history에서 거절되었거나 제약으로 기록된 패턴을 반복하지 마세요.
"""


class _RateGuard:
    def __init__(self) -> None:
        self._times: list[float] = []
        self._total = 0
        self._lock = threading.Lock()

    def check(self) -> None:
        now = time.time()
        with self._lock:
            self._times = [t for t in self._times if now - t < 60]
            if settings.llm_max_calls_total and self._total >= settings.llm_max_calls_total:
                raise ReasonerRateLimited(f"총 호출 한도({settings.llm_max_calls_total}) 초과")
            if (
                settings.llm_max_calls_per_minute
                and len(self._times) >= settings.llm_max_calls_per_minute
            ):
                raise ReasonerRateLimited(f"분당 호출 한도({settings.llm_max_calls_per_minute}) 초과")
            self._times.append(now)
            self._total += 1
            logger.info("llm 호출 #%d (최근 1분 %d건)", self._total, len(self._times))


_guard = _RateGuard()


class PydanticAIReasoner:
    async def assess_need(self, signal: dict, ctx: dict) -> NeedAssessment:
        prompt = (
            "아래 신호와 context pack을 보고 통합 필요도를 평가하세요. "
            "medical_cost_need, insurance_need, cashflow_need, asset_defense_need, "
            "investment_adjust_need, life_plan_need를 각각 none/low/mid/high로 평가하고, "
            "primary_need는 가장 우선되는 대응축 하나를 고르세요. 판단이 불충분하면 "
            "clarifying_question을 작성하세요. NeedAssessment JSON 스키마로만 답하세요.\n\n"
            f"signal:\n{_json(signal)}\n\ncontext_pack:\n{_json(ctx)}"
        )
        return await self._run(prompt, NeedAssessment)

    async def generate_plan(self, assessment: NeedAssessment, ctx: dict, memory: dict) -> Plan:
        prompt = (
            "아래 통합 필요도 평가와 context pack을 바탕으로 액션 제안 계획을 만드세요. "
            "외부 효과(예약, 청구, 구매, 송금, 포트폴리오 변경, 보험 변경 요청)가 있으면 "
            "has_external_effect=true로 표시하세요. 실제 실행은 하지 마세요. "
            "제안은 action kind enum 안에서만 작성하고, params는 backend가 채우므로 설명/근거에 집중하세요.\n\n"
            f"assessment:\n{assessment.model_dump_json()}\n\n"
            f"memory:\n{_json(memory)}\n\ncontext_pack:\n{_json(ctx)}"
        )
        llm_plan = await self._run(prompt, LLMPlan)
        return llm_plan.to_plan(assessment=assessment)

    async def _run(self, prompt: str, output_type: type[T]) -> T:
        _guard.check()
        try:
            from pydantic_ai import Agent
            from app.agent.codex_sdk_model import build_codex_sdk_model

            agent = Agent(
                build_codex_sdk_model(),
                output_type=output_type,
                system_prompt=SYSTEM_PROMPT,
            )
            result = await agent.run(prompt)
            output = result.output
            if not isinstance(output, output_type):
                return output_type.model_validate(output)
            return output
        except (ReasonerRateLimited, ReasonerOutputError):
            raise
        except Exception as exc:
            logger.exception("pydantic_ai/codex reasoner failed output_type=%s", output_type.__name__)
            raise ReasonerUnavailable(f"PydanticAI+Codex SDK 실행 실패: {exc}") from exc


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)
