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
| `REASONER` | `stub` | `stub` 또는 `pydantic_ai` |
| `CODEX_MODEL` | `gpt-5.4` | Codex SDK에 넘길 모델명 |
| `CODEX_MODEL_REASONING_EFFORT` | `high` | Codex 모델 추론 effort |
| `LLM_MAX_CALLS_PER_MINUTE` | `30` | 분당 LLM 호출 한도. `0`이면 무제한 |
| `LLM_MAX_CALLS_TOTAL` | `500` | 프로세스 총 LLM 호출 한도. `0`이면 무제한 |

기본값은 `REASONER=stub`이라 로컬 데모와 테스트는 Codex 세션 없이 동작합니다. 실제 LLM 모드는 서버에서 `codex login`을 1회 수행한 OAuth 세션을 사용합니다.

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
CODEX_MODEL=gpt-5.4
CODEX_MODEL_REASONING_EFFORT=high
LLM_MAX_CALLS_PER_MINUTE=30
LLM_MAX_CALLS_TOTAL=500

FILE_STORAGE_DRIVER=local
LOCAL_STORAGE_PATH=./storage
POLICY_DOCS_PATH=./policy_docs

ACTION_EXECUTION_MODE=mock_apply
```
