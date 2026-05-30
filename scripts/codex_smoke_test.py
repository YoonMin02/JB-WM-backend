"""Codex SDK 스모크 테스트 (docs/CODEX_ADAPTER.md).

실제 Codex(OAuth 세션)를 호출한다. 다음을 검증:
1. import + AsyncCodex 컨텍스트 진입
2. 사용 가능 모델 목록
3. thread_start(sandbox=read_only) + 워크스페이스 파일 읽기
4. 구조화 출력(output_schema) 턴
실행:  python scripts/codex_smoke_test.py
"""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from openai_codex import AsyncCodex, Sandbox


async def main() -> None:
    async with AsyncCodex() as codex:
        # 1. 메타/모델
        print("metadata:", codex.metadata)
        try:
            models = await codex.models()
            print("models:", models)
        except Exception as e:  # noqa: BLE001
            print("models() 실패(무시 가능):", e)

        # 2. 워크스페이스 (read-only 대상 파일)
        ws = Path(tempfile.mkdtemp(prefix="jbwm_smoke_"))
        (ws / "customer.json").write_text(
            json.dumps({"name": "테스트", "age_band": "65-69", "high_risk_weight": 0.7}, ensure_ascii=False),
            encoding="utf-8",
        )

        # 3. thread 시작 (read-only)
        thread = await codex.thread_start(sandbox=Sandbox.read_only, cwd=str(ws))
        print("thread.id:", thread.id)

        # 4. 구조화 출력 턴
        schema = {
            "type": "object",
            "properties": {"summary": {"type": "string"}, "high_risk_weight": {"type": "number"}},
            "required": ["summary", "high_risk_weight"],
            "additionalProperties": False,  # OpenAI strict 구조화출력 필수
        }
        result = await thread.run(
            "customer.json을 읽고, summary(한 문장)와 high_risk_weight를 JSON으로만 반환해.",
            output_schema=schema,
        )
        print("status:", result.status)
        print("final_response:", result.final_response)
        print("usage:", result.usage)
        try:
            print("parsed:", json.loads(result.final_response or "null"))
        except Exception as e:  # noqa: BLE001
            print("JSON 파싱 실패:", e)


if __name__ == "__main__":
    asyncio.run(main())
