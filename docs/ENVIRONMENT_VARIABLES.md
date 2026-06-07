# Environment Variables

`.env`로 런타임 설정을 관리합니다. `.env.example`만 커밋하고 `.env`는 로컬 전용입니다.

## Core

| 변수 | 기본 | 설명 |
|---|---|---|
| `APP_ENV` | `local` | 실행 환경 |
| `APP_NAME` | `jb-wm-backend` | 앱 이름 |
| `API_HOST` | `127.0.0.1` | 로컬 API 호스트 |
| `API_PORT` | `8000` | 로컬 API 포트 |
| `LOG_LEVEL` | `info` | 로깅 레벨 |

## Database / Auth

| 변수 | 기본 | 설명 |
|---|---|---|
| `DATABASE_URL` | `postgresql://jbwm:jbwm@localhost:5432/jbwm_dev` | DB 연결 문자열 |
| `JWT_SECRET` | `change-me` | JWT 서명 키 |

## Reasoning

| 변수 | 기본 | 설명 |
|---|---|---|
| `REASONER` | `stub` | legacy route용. 새 workflow는 `AGENT_JOB_MODE`를 사용 |
| `CODEX_MODEL` | `gpt-5.4-mini` | Codex SDK에 넘길 모델명. 기본은 실측 성공한 빠른 모델 |
| `CODEX_MODEL_REASONING_EFFORT` | `low` | Codex 모델 추론 effort. 토큰/지연을 줄이기 위해 낮게 둠 |
| `LLM_MAX_CALLS_PER_MINUTE` | `30` | 분당 LLM 호출 한도. `0`이면 무제한 |
| `LLM_MAX_CALLS_TOTAL` | `500` | 프로세스 총 LLM 호출 한도. `0`이면 무제한 |

기본값은 `AGENT_JOB_MODE=local_stub`이라 로컬 데모와 테스트는 Codex 세션 없이 동작합니다.

## LangGraph Agent Jobs

| 변수 | 기본 | 설명 |
|---|---|---|
| `AGENT_JOB_MODE` | `local_stub` | `local_stub` 또는 `codex_cli` |
| `AGENT_JOB_ROOT` | `/tmp/jbwm-agent-jobs` | job별 `context.json`/`output.json` 작업 디렉터리 |
| `CODEX_COMMAND` | `codex` | `codex_cli` 모드에서 실행할 CLI command |
| `AGENT_JOB_CODEX_MODEL` | `gpt-5.4-mini` | `codex_cli`에서 `codex exec --model`로 넘길 모델 |
| `AGENT_JOB_CODEX_REASONING_EFFORT` | `low` | `codex_cli`에서 `model_reasoning_effort`로 넘길 값 |
| `AGENT_JOB_CODEX_MODEL_CANDIDATES` | `gpt-5.4-mini,...` | 벤치 스크립트가 순차 측정할 후보 목록 |
| `AGENT_JOB_TIMEOUT_SECONDS` | `1800` | agent child process timeout |
| `AGENT_JOB_OUTPUT_MAX_BYTES` | `200000` | 구조화 출력 최대 크기 |

`codex_cli`는 `temp/Codex_with_Gmail`의 process-spawn 패턴을 JB-WM에 맞게 제한한 모드입니다. child env에는 DB/API secret을 넣지 않습니다.
현재 로컬 벤치 결과는 [`docs/redesign/codex_cli_model_benchmark.md`](redesign/codex_cli_model_benchmark.md)에 기록합니다.

## Storage / Policy

| 변수 | 기본 | 설명 |
|---|---|---|
| `FILE_STORAGE_DRIVER` | `local` | 파일 저장소 driver |
| `LOCAL_STORAGE_PATH` | `./storage` | 로컬 저장 경로 |
| `POLICY_DOCS_PATH` | `./policy_docs` | LLM 판단에 주입할 내규/정책 문서 경로 |

## Privacy

| 변수 | 기본 | 설명 |
|---|---|---|
| `PRIVACY_SENSITIVE_RETENTION_DAYS` | `365` | 민감 transcript 보유일수 |

## Action Execution

| 변수 | 기본 | 설명 |
|---|---|---|
| `ACTION_EXECUTION_MODE` | `mock_apply` | `mock_apply`: mock DB에 반영. `external_request`: 실제 외부 실행 요청 모드, 현재 미구현 |

## Example

```dotenv
APP_ENV=local
APP_NAME=jb-wm-backend
API_HOST=127.0.0.1
API_PORT=8000
LOG_LEVEL=info

DATABASE_URL=postgresql://jbwm:jbwm@localhost:5432/jbwm_dev
JWT_SECRET=change-me
PRIVACY_SENSITIVE_RETENTION_DAYS=365

REASONER=stub
CODEX_MODEL=gpt-5.4-mini
CODEX_MODEL_REASONING_EFFORT=low
LLM_MAX_CALLS_PER_MINUTE=30
LLM_MAX_CALLS_TOTAL=500

AGENT_JOB_MODE=local_stub
AGENT_JOB_ROOT=/tmp/jbwm-agent-jobs
CODEX_COMMAND=codex
AGENT_JOB_CODEX_MODEL=gpt-5.4-mini
AGENT_JOB_CODEX_REASONING_EFFORT=low
AGENT_JOB_CODEX_MODEL_CANDIDATES=gpt-5.4-mini,gpt-5.5,gpt-5.3-codex-spark,gpt-5-mini,gpt-5-nano,gpt-5.1-codex-mini,gpt-5.2-codex
AGENT_JOB_TIMEOUT_SECONDS=1800
AGENT_JOB_OUTPUT_MAX_BYTES=200000

FILE_STORAGE_DRIVER=local
LOCAL_STORAGE_PATH=./storage
POLICY_DOCS_PATH=./policy_docs

ACTION_EXECUTION_MODE=mock_apply
```
