"""CodexReasoner — AgentReasoner 포트의 Codex SDK 구현.

이 파일이 유일한 `openai_codex` import 지점이다 (agent_rules 불변식 5).
- 샌드박스는 항상 read_only (capability 보안).
- 고객 컨텍스트는 read-only 워크스페이스에 JSON 파일로 materialize 후 Codex가 읽는다.
- 동적/실시간 도구가 필요하면 MCP 읽기 서버를 config로 등록 (슬라이스 1은 파일로 충분).
실제 SDK 사양은 docs/CODEX_ADAPTER.md, ~/codex/sdk/python 참고.
"""
from __future__ import annotations

import json
import tempfile
import threading
import time
from pathlib import Path

from app.agent.schemas import LLMPlan, NeedAssessment, Plan
from app.core.config import settings
from app.core.logging import logger


class CodexRateLimited(RuntimeError):
    """설정된 호출 한도 초과 (쿼터 보호)."""


class _RateGuard:
    """프로세스 단위 호출 가드 — 분당 + 총량. 넉넉한 기본값."""

    def __init__(self) -> None:
        self._times: list[float] = []
        self._total = 0
        self._lock = threading.Lock()

    def check(self) -> None:
        now = time.time()
        with self._lock:
            self._times = [t for t in self._times if now - t < 60]
            if settings.codex_max_calls_total and self._total >= settings.codex_max_calls_total:
                raise CodexRateLimited(f"총 호출 한도({settings.codex_max_calls_total}) 초과")
            if (
                settings.codex_max_calls_per_minute
                and len(self._times) >= settings.codex_max_calls_per_minute
            ):
                raise CodexRateLimited(f"분당 호출 한도({settings.codex_max_calls_per_minute}) 초과")
            self._times.append(now)
            self._total += 1
            logger.info("codex 호출 #%d (최근 1분 %d건)", self._total, len(self._times))


_guard = _RateGuard()


def _make_strict(node):
    """OpenAI strict 구조화출력 규칙 적용: 모든 object에 additionalProperties=false + 전체 required."""
    if isinstance(node, dict):
        if node.get("type") == "object" and "properties" in node:
            node["additionalProperties"] = False
            node["required"] = list(node["properties"].keys())
        for v in node.values():
            _make_strict(v)
    elif isinstance(node, list):
        for v in node:
            _make_strict(v)
    return node


def _strict_schema(model: type) -> dict:
    return _make_strict(model.model_json_schema())

SYSTEM_INSTRUCTIONS = (
    "당신은 JB WM의 분석 보조 에이전트입니다. 워크스페이스의 고객 데이터 파일"
    "(profile/health/insurance/accounts/transactions/card_bills/loans/portfolio/"
    "asset_events/population/memory.json)과 규정 파일을 읽고 분석합니다. "
    "당신은 읽기·분석·제안만 합니다. 어떤 실제 행동(예약·청구·송금)도 실행하지 않으며, "
    "그럴 권한도 없습니다. 항상 요청된 JSON 스키마에 맞는 결과만 반환하세요."
)


def _write_workspace(ctx: dict) -> Path:
    """현재 고객 컨텍스트를 read-only 워크스페이스 파일로 기록.

    build_context의 모든 JSON-like 키를 각각 `<key>.json` 파일로 materialize한다.
    customer_id 같은 스칼라는 제외.
    """
    base = settings.codex_working_directory or None
    if base:
        Path(base).mkdir(parents=True, exist_ok=True)
    customer_id = str(ctx.get("customer_id") or "").replace("/", "_")
    if customer_id:
        root = Path(base or tempfile.gettempdir()) / f"jbwm_customer_{customer_id}"
        root.mkdir(parents=True, exist_ok=True)
    else:
        root = Path(tempfile.mkdtemp(prefix="jbwm_ws_", dir=base))
    for name, payload in ctx.items():
        if not isinstance(payload, (dict, list)):
            continue
        (root / f"{name}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    logger.info("codex workspace prepared path=%s files=%s", root, sorted(p.name for p in root.glob("*.json")))
    return root


def _parse(raw: str | None, model: type):
    if not raw:
        raise ValueError("Codex가 빈 응답을 반환했습니다.")
    data = json.loads(raw)
    return model.model_validate(data)


class CodexReasoner:
    def __init__(self) -> None:
        self.last_thread_id: str | None = None

    async def _run(self, prompt: str, ctx: dict, schema_model: type, session_ref: str | None = None):
        # 지연 import: stub reasoner 사용 시 openai_codex 미설치여도 동작하도록
        logger.info(
            "codex run start schema=%s resume=%s customer_id=%s",
            schema_model.__name__,
            bool(session_ref),
            ctx.get("customer_id"),
        )
        from openai_codex import AsyncCodex, Sandbox

        _guard.check()  # 쿼터 보호 — 한도 초과 시 CodexRateLimited
        workspace = _write_workspace(ctx)
        logger.info("codex opening client schema=%s", schema_model.__name__)
        async with AsyncCodex() as codex:
            logger.info("codex client opened schema=%s", schema_model.__name__)
            if session_ref:
                logger.info("codex thread resume start thread=%s", session_ref)
                thread = await codex.thread_resume(session_ref)
                logger.info("codex thread resume ok thread=%s", thread.id)
            else:
                # 기존 `codex login` OAuth 세션 자동 재사용.
                logger.info("codex thread start begin model=%s cwd=%s", settings.codex_model, workspace)
                thread = await codex.thread_start(
                    model=settings.codex_model,
                    sandbox=Sandbox.read_only,  # ★ capability 보안
                    developer_instructions=SYSTEM_INSTRUCTIONS,
                    cwd=str(workspace),
                )
                logger.info("codex thread start ok thread=%s", thread.id)
            self.last_thread_id = thread.id
            logger.info("codex turn run begin thread=%s schema=%s", thread.id, schema_model.__name__)
            result = await thread.run(prompt, output_schema=_strict_schema(schema_model))
            if result.status == "failed":
                raise RuntimeError(f"Codex turn 실패: {result.error}")
            logger.info("codex turn ok (thread=%s)", thread.id)
            return _parse(result.final_response, schema_model)

    async def assess_need(self, signal: dict, ctx: dict, session_ref: str | None = None) -> NeedAssessment:
        prompt = (
            "워크스페이스의 고객 데이터를 읽고, 아래 신호로부터 고객의 통합 필요도를 평가하세요. "
            "단일 intent로 좁히지 말고 medical_cost_need, insurance_need, cashflow_need, "
            "asset_defense_need, investment_adjust_need, life_plan_need를 각각 none/low/mid/high로 "
            "평가하세요. 고객이 직접 요청한 영역은 강하게 반영하되, 애매하면 clarifying_question을 작성하세요.\n"
            f"신호: {json.dumps(signal, ensure_ascii=False)}\n"
            "NeedAssessment 스키마(JSON)로만 답하세요."
        )
        return await self._run(prompt, ctx, NeedAssessment, session_ref=session_ref)

    async def generate_plan(
        self, assessment: NeedAssessment, ctx: dict, memory: dict, session_ref: str | None = None
    ) -> Plan:
        prompt = (
            "워크스페이스의 고객 데이터(건강·자산 통합)와 통계(population.json), "
            "장기 메모리(memory.json: 지불의향·성향·제약), 그리고 통합 필요도 평가를 반영하여 "
            "액션 제안 계획을 만드세요. 판단 순서는 생애설계 필요성, 의료비, 보험, 현금흐름, "
            "자산방어, 투자전략 종합입니다. 외부 효과(예약·청구·구매·송금·포트폴리오 변경)가 있는 액션은 "
            "has_external_effect=true로 표시하세요. 고객 제약(예: 투자 보류)은 반영해 해당 제안을 "
            "제외하세요. 의료 권고가 아니라 재무 대비·통계 참고만 합니다. 실제 실행은 하지 않습니다.\n"
            f"통합 필요도 평가: {assessment.model_dump_json()}\n"
            "LLMPlan 스키마(JSON)로만 답하세요."
        )
        llm_plan: LLMPlan = await self._run(prompt, ctx, LLMPlan, session_ref=session_ref)
        return llm_plan.to_plan(assessment=assessment)
