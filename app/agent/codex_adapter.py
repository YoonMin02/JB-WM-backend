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
from pathlib import Path

from app.agent.schemas import IntentInference, Plan
from app.core.config import settings
from app.core.logging import logger

SYSTEM_INSTRUCTIONS = (
    "당신은 JB WM의 분석 보조 에이전트입니다. 워크스페이스의 고객 데이터 파일"
    "(profile/health/insurance/loans/memory.json)과 규정 파일을 읽고 분석합니다. "
    "당신은 읽기·분석·제안만 합니다. 어떤 실제 행동(예약·청구·송금)도 실행하지 않으며, "
    "그럴 권한도 없습니다. 항상 요청된 JSON 스키마에 맞는 결과만 반환하세요."
)


def _write_workspace(ctx: dict) -> Path:
    """현재 고객 컨텍스트를 read-only 워크스페이스 파일로 기록."""
    root = Path(tempfile.mkdtemp(prefix="jbwm_ws_", dir=settings.codex_working_directory or None))
    for name in ("profile", "health", "insurance", "loans", "memory"):
        (root / f"{name}.json").write_text(
            json.dumps(ctx.get(name, {}), ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return root


def _parse(raw: str | None, model: type):
    if not raw:
        raise ValueError("Codex가 빈 응답을 반환했습니다.")
    data = json.loads(raw)
    return model.model_validate(data)


class CodexReasoner:
    async def _run(self, prompt: str, ctx: dict, schema_model: type):
        # 지연 import: stub reasoner 사용 시 openai_codex 미설치여도 동작하도록
        from openai_codex import AsyncCodex, Sandbox

        workspace = _write_workspace(ctx)
        async with AsyncCodex() as codex:
            # 기존 `codex login` OAuth 세션 자동 재사용.
            thread = await codex.thread_start(
                model=settings.codex_model,
                sandbox=Sandbox.read_only,  # ★ capability 보안
                developer_instructions=SYSTEM_INSTRUCTIONS,
                cwd=str(workspace),
            )
            result = await thread.run(prompt, output_schema=schema_model.model_json_schema())
            if result.status == "failed":
                raise RuntimeError(f"Codex turn 실패: {result.error}")
            logger.info("codex turn ok (thread=%s)", thread.id)
            return _parse(result.final_response, schema_model)

    async def infer_intent(self, signal: dict, ctx: dict) -> IntentInference:
        prompt = (
            "워크스페이스의 고객 데이터를 읽고, 아래 신호로부터 고객의 잠재 의도를 추론하세요.\n"
            f"신호: {json.dumps(signal, ensure_ascii=False)}\n"
            "IntentInference 스키마(JSON)로만 답하세요."
        )
        return await self._run(prompt, ctx, IntentInference)

    async def generate_plan(self, intent: IntentInference, ctx: dict, memory: dict) -> Plan:
        prompt = (
            "워크스페이스의 고객 데이터와 장기 메모리(memory.json, 고객 성향·제약)를 반영하여 "
            "의도를 충족할 액션 제안 계획을 만드세요. 외부 효과가 있는 액션은 "
            "has_external_effect=true로 표시하세요. 실제 실행은 하지 않습니다.\n"
            f"의도: {intent.model_dump_json()}\n"
            "Plan 스키마(JSON)로만 답하세요."
        )
        return await self._run(prompt, ctx, Plan)
