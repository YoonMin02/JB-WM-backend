# external/codex-sdk · 공식 SDK 참조 스냅샷

이 폴더는 Codex SDK 공식/패키지 문서를 이해하기 위한 참조입니다. **프로젝트 정책을 정의하지 않습니다** — 정책은 [`../../04_AGENT_RUNTIME.md`](../../04_AGENT_RUNTIME.md)와 [`../../CODEX_ADAPTER.md`](../../CODEX_ADAPTER.md)에 있습니다.

## 진실의 출처

실제 소스는 이 저장소가 아니라 **`~/codex/sdk/python`** (JB-AI/JB-WM과 같은 상위 디렉토리, 해커톤 시점 최신)입니다.

| 파일 | 내용 |
|---|---|
| `~/codex/sdk/python/README.md` | 설치·인증·퀵스타트 |
| `~/codex/sdk/python/docs/api-reference.md` | 공개 API 전체 (Codex/AsyncCodex/Thread/TurnResult/Sandbox/Input/errors) |
| `~/codex/sdk/python/docs/getting-started.md` | 단계별 가이드 |
| `~/codex/sdk/python/docs/faq.md` | sync vs async 등 |
| `~/codex/sdk/python/src/openai_codex/__init__.py` | 공개 표면 (`__all__`) |

## 검증된 핵심 사실 (실제 소스 확인)

- 패키지 `openai-codex`, 모듈 `openai_codex`. 구버전 `codex_app_server`는 **폐기**.
- 임포트: `from openai_codex import AsyncCodex, Sandbox, ApprovalMode, retry_on_overload, ServerBusyError, ...`
- Python ≥ 3.10. async 앱은 `AsyncCodex`.
- 인증: 기존 `codex login` OAuth 세션 자동 재사용. `login_chatgpt()` / `login_chatgpt_device_code()` / `login_api_key()`.
- thread: `thread_start(model=, sandbox=, developer_instructions=, cwd=, config=)`, `thread_resume(id)`, `thread_fork`, `thread_list`, `thread_archive`.
- 턴: `thread.run(input, output_schema=) -> TurnResult(.final_response, .items, .usage, .status, .error)`; 스트리밍 `thread.turn(...).stream()`.
- 샌드박스: `read_only` / `workspace_write` / `full_access`. **우리는 항상 `read_only`**.
- MCP 지원: `McpToolCall*` 알림, `mcp_server_config`. 동적 도구는 읽기 전용 MCP로 노출.
- 에러: `ServerBusyError`(재시도), `InvalidParamsError`/`MethodNotFoundError`(재시도 금지), `retry_on_overload`, `is_retryable_error`.

## 동기화 절차

SDK가 업데이트되면 `~/codex/sdk/python`을 다시 읽고 위 사실 + [`../../CODEX_ADAPTER.md`](../../CODEX_ADAPTER.md)를 갱신합니다. 이 폴더의 파일은 스냅샷일 뿐, 코드가 직접 import하지 않습니다.
