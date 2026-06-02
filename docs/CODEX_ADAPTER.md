# CODEX_ADAPTER · Codex SDK 구체 연동

`AgentReasoner` 포트([04](04_AGENT_RUNTIME.md))의 **Codex SDK 구현**입니다. 이 문서와 구현은 실제 소스 `~/codex/sdk/python` 기준입니다 (해커톤 시점 최신). SDK는 교체 가능한 블랙박스이며, 이 어댑터가 유일한 SDK import 지점입니다.

> 검증된 사실은 모두 `~/codex/sdk/python/docs/api-reference.md`, `getting-started.md`, `src/openai_codex/__init__.py`에서 확인했습니다.

## 패키지 · 임포트

```bash
bash scripts/install.sh           # glibc WSL용 우회 설치 포함
```

```python
from openai_codex import AsyncCodex, Sandbox, ApprovalMode
```

- 패키지명 `openai-codex`, 모듈 `openai_codex`. (구버전 문서의 `codex_app_server`는 **폐기**)
- Python ≥ 3.10. FastAPI가 async이므로 **`AsyncCodex` 사용**.
- glibc Linux(WSL/Ubuntu)에서는 `openai-codex-cli-bin`이 musl 휠이라 일반 resolver가 실패할 수 있습니다. 따라서 SDK는 `pyproject.toml` 기본 dependency가 아니라 `scripts/install.sh`가 설치합니다.
- 일반 개발 명령(`uv run pytest`)은 SDK 전이 의존성에 걸리지 않아야 합니다. 실제 SDK 연동 검증은 설치 스크립트 후 smoke test로 수행합니다.

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

현재 구현에서는 Orchestrator가 첫 신호 처리 전에 `CodexReasoner.start_session(customer_id, ctx)`를
호출해 thread id를 먼저 만들고 DB에 저장합니다. 그 뒤 `assess_need()`와 `generate_plan()`은
항상 저장된 `session_ref`로 같은 thread를 재개합니다.

`thread_start`/`thread_resume`/`thread_fork`/`thread_list`/`thread_archive` 지원 ([api-reference](#)). 기본 `approval_mode=ApprovalMode.auto_review` — 단, **비즈니스 액션 승인은 Codex의 승인이 아니라 우리 FSM 게이트**가 담당 ([07](07_ACTION_EXECUTION.md)).

## 턴 실행

### 블로킹 (MVP 기본)
```python
result = await thread.run(
    prompt,
    output_schema=NeedAssessment.model_json_schema(),   # 구조화 출력
)
result.final_response   # str | None
result.items            # list[ThreadItem]
result.usage            # ThreadTokenUsage | None
result.status           # TurnStatus
result.error            # TurnError | None
```

`run(...)`은 턴 시작 → 완료까지 대기 → `TurnResult` 반환. 평문 `str`은 `TextInput` 약칭.

> **구조화 출력은 strict 스키마여야 함 (중요).** OpenAI strict 구조화출력은 **모든 object에 `additionalProperties: false` + 모든 키 `required`** 를 요구합니다. Pydantic의 `model_json_schema()`는 이를 안 넣으므로, 어댑터의 `_strict_schema()`가 스키마를 재귀적으로 변환해 넣습니다. 안 하면 `400 invalid_json_schema`.
> 또한 free-form `dict`(예: `ActionProposal.params`)는 strict와 충돌하므로, **LLM 출력 전용 스키마**(`LLMPlan`/`LLMActionProposal`, `params` 없음)를 쓰고 서버가 `params`를 채웁니다 ([schemas.py](#)).

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
| ① 고객 개인 (동적) | 백엔드가 띄운 **MCP 읽기 서버** (codex `config`로 등록). 건강·포트폴리오·보험·대출·**자산 이벤트**·메모리(지불의향 포함) |
| ② 통계 | MCP 읽기 도구 `get_population_stat` (또는 워크스페이스에 통계 스냅샷 파일) |
| ③ 규정·약관 | `cwd` 워크스페이스의 **읽기 전용 파일** |

> 통합 회복탄력성 판단을 위해, 워크스페이스/도구로 **건강과 자산을 함께** 제공합니다. 어댑터는 `build_context`의 JSON-like 키 — `profile/health/insurance/accounts/transactions/card_bills/loans/loan_switch_precheck/portfolio/asset_events/population/memory(.json)` — 를 워크스페이스에 materialize합니다. 단, 의료 권고는 생성하지 않도록 `developer_instructions`로 한정합니다 ([10](10_SECURITY_PRIVACY.md)).

`policy_docs/`의 정적 문서(`.md`, `.txt`, `.json`)는 workspace의 `static_context/`로 복사됩니다.
기본 샘플은 의료/금융 경계, 실행 capability 경계, 통계 사용 원칙입니다. 소스 코드나 실행 파일은
복사하지 않습니다.

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
| `result.status == "failed"` | `CodexTurnFailed`로 정규화 → API 502 |
| 빈 응답 / JSON 파싱 실패 / 스키마 검증 실패 | `CodexOutputError`로 정규화 → API 502 |
| SDK/OAuth/runtime 연결 실패 | `CodexUnavailable`로 정규화 → API 503 |
| rate guard 초과 | `CodexRateLimited` → API 429 |

API 라우트는 위 오류를 `{ error, message }` 형태의 `HTTPException.detail`로 반환합니다. 실행 실패와
추론 실패는 다릅니다. `State.Failed`는 현재 Executor 실행 실패 경로이고, Codex 추론 실패는 API 오류로
정규화합니다.

## 호출 한도 (Rate Guard)

쿼터 보호를 위해 어댑터에 프로세스 단위 가드(`_RateGuard`)가 있습니다. 매 Codex 호출 전 체크하고, 초과 시 `CodexRateLimited`를 던집니다 → API에서 **429**로 변환 (`sessions.post_signal`, `proposals._decide`).

| 설정 (env) | 기본 | 의미 |
|---|---|---|
| `CODEX_MAX_CALLS_PER_MINUTE` | 30 | 분당 한도. 0=무제한 |
| `CODEX_MAX_CALLS_TOTAL` | 500 | 프로세스 총 한도. 0=무제한 |

stub reasoner는 호출 비용이 없으므로 가드 대상이 아닙니다. 자세히는 [ENVIRONMENT_VARIABLES](ENVIRONMENT_VARIABLES.md).

## 어댑터 위치 & 격리

```
app/agent/
├── runtime.py          # AgentReasoner 포트 (공급자 무관) + Orchestrator
├── codex_adapter.py    # ★ 유일한 openai_codex import 지점
├── schemas.py          # NeedAssessment / Plan / ActionProposal
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
1. seed/mock 데이터로 고객 컨텍스트 생성
2. `CodexReasoner.assess_need(...)`가 `NeedAssessment`를 반환
3. 반환된 thread id를 `generate_plan(...)`에 넘겨 같은 고객 thread를 재사용
4. `Plan` 구조화 출력 반환
5. `portfolio_loss` mock 신호에서 actionable need 생성

실행 전 서버 터미널에서 OAuth 세션이 있어야 합니다.

```bash
timeout 120s .venv/bin/python scripts/codex_smoke_test.py
```

SDK/OAuth 진입부가 native subprocess에서 대기하면 Python 내부 timeout으로 안정적으로 끊기지 않을 수 있으므로, smoke test는 shell의 `timeout`으로 감쌉니다.

어댑터는 단계별 로그를 남깁니다. 멈춤 위치를 구분할 때 아래 로그를 봅니다.

- `codex run start`
- `codex workspace prepared`
- `codex opening client`
- `codex client opened`
- `codex thread start begin` / `codex thread resume start`
- `codex turn run begin`
- `codex turn ok`
