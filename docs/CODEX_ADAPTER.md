# CODEX_ADAPTER · Codex SDK 구체 연동

`AgentReasoner` 포트([04](04_AGENT_RUNTIME.md))의 **Codex SDK 구현**입니다. 이 문서와 구현은 실제 소스 `~/codex/sdk/python` 기준입니다 (해커톤 시점 최신). SDK는 교체 가능한 블랙박스이며, 이 어댑터가 유일한 SDK import 지점입니다.

> 검증된 사실은 모두 `~/codex/sdk/python/docs/api-reference.md`, `getting-started.md`, `src/openai_codex/__init__.py`에서 확인했습니다.

## 패키지 · 임포트

```python
pip install openai-codex          # openai-codex-cli-bin 런타임 자동 설치
from openai_codex import AsyncCodex, Sandbox, ApprovalMode
```

- 패키지명 `openai-codex`, 모듈 `openai_codex`. (구버전 문서의 `codex_app_server`는 **폐기**)
- Python ≥ 3.10. FastAPI가 async이므로 **`AsyncCodex` 사용**.
- glibc Linux(WSL/Ubuntu)에서는 `openai-codex-cli-bin`이 musl 휠이라 설치 우회가 필요 → `scripts/install.sh` 참고.

## 인증 (OAuth 세션)

서버 터미널에서 **1회 `codex login`** 하면 OAuth 세션이 생기고, SDK가 자동으로 재사용합니다. 별도 API 키 불필요.

```python
# 기존 Codex 세션이 있으면 자동 재사용 — 추가 호출 불필요
async with AsyncCodex() as codex:
    ...
```

프로그래밍 방식 로그인(선택):
```python
async with AsyncCodex() as codex:
    login = await codex.login_chatgpt()        # login.auth_url 출력
    await login.wait()                          # 완료 대기
    # 또는 디바이스 코드:
    # login = await codex.login_chatgpt_device_code()  # verification_url, user_code
    # API 키가 있는 환경: await codex.login_api_key("sk-...")
```

> MVP/해커톤은 단일 서버 + 단일 OAuth 세션 + 저트래픽 전제. 다중 사용자 프로덕션 inference 백엔드로 쓰는 것은 약관·안정성상 별개 문제 ([10](10_SECURITY_PRIVACY.md)).

## Thread 모델

1 에이전트 세션 = 1 Codex thread.

```python
async with AsyncCodex() as codex:
    thread = await codex.thread_start(
        model="gpt-5.4",                       # 실제 모델명은 codex.models()로 확인
        sandbox=Sandbox.read_only,             # ★ capability 보안: 읽기 전용
        developer_instructions=SYSTEM_INSTRUCTIONS,
        cwd=session_workspace_path,            # 현재 고객 스냅샷 + 규정 파일만
        config={...},                          # MCP 서버 등 codex config 패스스루
    )
    session.agent_thread_id = thread.id        # 즉시 영속화 (재개·감사)
```

재개:
```python
thread = await codex.thread_resume(session.agent_thread_id)
```

`thread_start`/`thread_resume`/`thread_fork`/`thread_list`/`thread_archive` 지원 ([api-reference](#)). 기본 `approval_mode=ApprovalMode.auto_review` — 단, **비즈니스 액션 승인은 Codex의 승인이 아니라 우리 FSM 게이트**가 담당 ([07](07_ACTION_EXECUTION.md)).

## 턴 실행

### 블로킹 (MVP 기본)
```python
result = await thread.run(
    prompt,
    output_schema=IntentInference.model_json_schema(),   # 구조화 출력
)
result.final_response   # str | None
result.items            # list[ThreadItem]
result.usage            # ThreadTokenUsage | None
result.status           # TurnStatus
result.error            # TurnError | None
```

`run(...)`은 턴 시작 → 완료까지 대기 → `TurnResult` 반환. 평문 `str`은 `TextInput` 약칭.

### 스트리밍 (나중)
```python
handle = await thread.turn(prompt)
async for note in handle.stream():     # AsyncIterator[Notification]
    ...                                # 프론트 SSE로 진행상황
result = await handle.run()
# handle.steer(...) / handle.interrupt() 도 가능
```

## 샌드박스 (capability 핵심)

```python
Sandbox.read_only        # ★ 우리 기본값 — 파일 쓰기 불가
Sandbox.workspace_write  # 사용 안 함
Sandbox.full_access      # 사용 안 함
```

에이전트 thread는 **항상 `read_only`**. 워크스페이스(`cwd`)에는 현재 고객 데이터 스냅샷 + 규정 파일만 둡니다. → 환각·인젝션이 있어도 쓰기/실행 불가 ([10](10_SECURITY_PRIVACY.md)).

## 도구 노출 (MCP + 워크스페이스)

Codex SDK는 커스텀 함수 등록 API가 없고 **워크스페이스 + MCP** 기반입니다 ([06](06_TOOL_CONTRACTS.md)).

| 데이터 | 노출 |
|---|---|
| ① 고객 개인 (동적) | 백엔드가 띄운 **MCP 읽기 서버** (codex `config`로 등록) |
| ② 통계 | MCP 읽기 도구 |
| ③ 규정·약관 | `cwd` 워크스페이스의 **읽기 전용 파일** |

> SDK 런타임은 MCP를 지원합니다 (`McpToolCall*` 알림, `mcp_server_config`). 동적 데이터·통계 도구는 우리 백엔드 MCP 서버로 노출하고, **읽기 전용**으로 제한합니다. 실행 도구는 MCP에도 두지 않습니다.

## 에러 처리

```python
from openai_codex import (
    retry_on_overload, is_retryable_error,
    ServerBusyError, InvalidParamsError, MethodNotFoundError,
)

async def run_with_retry(thread, prompt, schema):
    return await retry_on_overload(
        lambda: thread.run(prompt, output_schema=schema)
    )
```

| 에러 | 처리 |
|---|---|
| `ServerBusyError` | `retry_on_overload` 재시도 |
| `InvalidParamsError` | 입력 수정, 재시도 금지 |
| `MethodNotFoundError` | SDK/런타임 버전 불일치, 재시도 금지 |
| `result.status == "failed"` | `result.error` 읽고 세션 `Failed` 전이 ([03](03_STATE_MACHINE.md)) |

## 어댑터 위치 & 격리

```
app/agent/
├── runtime.py          # AgentReasoner 포트 (공급자 무관) + Orchestrator
├── codex_adapter.py    # ★ 유일한 openai_codex import 지점
├── schemas.py          # IntentInference / Plan / ActionProposal
└── prompts.py          # SYSTEM_INSTRUCTIONS
```

```python
# 도메인 서비스에서 허용
from app.agent.runtime import AgentReasoner

# app/agent/codex_adapter.py 밖에서는 금지
from openai_codex import AsyncCodex
```

## 마이그레이션

다른 공급자로 바꾸려면 `app/agent/gemini_adapter.py` 등을 `AgentReasoner`로 새로 구현하고 주입만 교체. FSM·Policy·Executor·Memory·Tools·도메인은 불변 ([04](04_AGENT_RUNTIME.md)).

## 스모크 테스트

`scripts/codex_smoke_test.py`로 검증:
1. import 성공
2. `AsyncCodex` 컨텍스트 진입
3. (OAuth 세션 존재 시) `thread_start(sandbox=read_only)` thread id 반환
4. `thread.run("안녕")` → `final_response` 비어있지 않음
5. `ServerBusyError` import + `retry_on_overload` 호출 가능
