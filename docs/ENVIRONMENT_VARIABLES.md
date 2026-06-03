# 환경변수

`.env`로 런타임 설정을 관리합니다. `.env.example`만 커밋하고 `.env`는 gitignore. 변경 시 이 문서를 갱신합니다.

## Core
| 변수 | 필수 | 설명 |
|---|---|---|
| `APP_ENV` | Yes | `local` / `dev` / `staging` / `prod` |
| `APP_NAME` | No | 기본 `jb-wm-backend` |
| `API_HOST` | No | 로컬 API 호스트 |
| `API_PORT` | No | 로컬 API 포트 (기본 8000) |
| `LOG_LEVEL` | No | 로깅 레벨 |

## Database
| 변수 | 필수 | 설명 |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL 연결 문자열 |

## Auth
| 변수 | 필수 | 설명 |
|---|---|---|
| `JWT_SECRET` | Depends | JWT 사용 시 필수 |
| `SESSION_SECRET` | Depends | 세션 인증 사용 시 |

## Privacy
| 변수 | 필수 | 기본 | 설명 |
|---|---|---|---|
| `PRIVACY_SENSITIVE_RETENTION_DAYS` | No | `365` | 민감 transcript 보유일수. 초과 `AgentMessage`는 purge 대상 |

## Codex / 추론
| 변수 | 필수 | 기본 | 설명 |
|---|---|---|---|
| `REASONER` | No | `stub` | 추론 백엔드 선택. `stub`(규칙·무료·결정론적) / `codex`(실제 LLM). 테스트는 항상 stub |
| `CODEX_MODEL` | No | `gpt-5.4` | codex일 때 모델. 사용 가능: gpt-5.5 / gpt-5.4 / gpt-5.4-mini / gpt-5.3-codex / gpt-5.2 |
| `CODEX_MAX_CALLS_PER_MINUTE` | No | `30` | 분당 Codex 호출 한도 (쿼터 보호). 초과 시 API 429. `0`=무제한 |
| `CODEX_MAX_CALLS_TOTAL` | No | `500` | 프로세스 총 Codex 호출 한도. `0`=무제한 |
| `OPENAI_API_KEY` | No | — | **선택**. `codex login` OAuth 세션이 있으면 불필요. CLI 세션 없는 환경(CI 등)에서만 `login_api_key`용 |
| `CODEX_WORKING_DIRECTORY` | No | `./workspace` | 에이전트 워크스페이스 루트 (세션별 하위 디렉토리 생성) |
| `CODEX_WORKSPACE_INCLUDE_SNAPSHOTS` | No | `false` | 고객 JSON 스냅샷을 workspace에 쓸지 여부. 기본은 MCP read tools만 사용해 민감 데이터 파일화를 최소화 |

> 기본 경로는 **OAuth 세션 재사용**입니다 ([CODEX_ADAPTER.md](CODEX_ADAPTER.md) 인증). `OPENAI_API_KEY`는 대체 수단일 뿐 필수가 아닙니다.
> 호출 한도는 `app/agent/codex_adapter.py`의 rate guard가 강제합니다.

## Storage
| 변수 | 필수 | 설명 |
|---|---|---|
| `FILE_STORAGE_DRIVER` | No | `local` (MVP) / `s3` / `r2` |
| `LOCAL_STORAGE_PATH` | No | 로컬 파일 경로 |
| `POLICY_DOCS_PATH` | No | 규정·약관 파일 디렉토리 (③ 비정형, read-only 워크스페이스에 동기화) |

## Statistics (선택)
| 변수 | 필수 | 설명 |
|---|---|---|
| `STATS_DATASET_PATH` | No | 통계 데이터셋 경로 (② KOSIS/KIDI/KNHANES) |

## Queue / 관측 (나중)
| 변수 | 필수 | 설명 |
|---|---|---|
| `REDIS_URL` | Later | 이벤트 큐/캐시 |
| `SENTRY_DSN` | No | 에러 추적 |

## `.env.example`
```dotenv
APP_ENV=local
APP_NAME=jb-wm-backend
API_HOST=127.0.0.1
API_PORT=8000
LOG_LEVEL=info

DATABASE_URL=postgresql://jbwm:jbwm@localhost:5432/jbwm_dev
JWT_SECRET=change-me
PRIVACY_SENSITIVE_RETENTION_DAYS=365

# 추론: stub(기본, 무료·결정론적) / codex(실제 LLM)
REASONER=stub
CODEX_MODEL=gpt-5.4
CODEX_MAX_CALLS_PER_MINUTE=30
CODEX_MAX_CALLS_TOTAL=500
# Codex: codex login OAuth 세션 사용 시 불필요
# OPENAI_API_KEY=sk-...
CODEX_WORKING_DIRECTORY=./workspace
CODEX_WORKSPACE_INCLUDE_SNAPSHOTS=false

FILE_STORAGE_DRIVER=local
LOCAL_STORAGE_PATH=./storage
POLICY_DOCS_PATH=./policy_docs
```
