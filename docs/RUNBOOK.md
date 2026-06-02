# RUNBOOK · 직접 켜고·보고·확인하기

"무슨 명령어로 뭘 켜는지 / 데이터가 어디서 오는지 / 실제로 어떻게 눈으로 보는지"를 직접 재현하기 위한 문서.

---

## 0. 구성요소 한눈에 (무엇이 무엇인가)

| 구성요소 | 정체 | 켜는 법 | 확인 |
|---|---|---|---|
| **PostgreSQL** | 모든 고객·이벤트·이력 저장소 | `sudo service postgresql start` | `psql $DATABASE_URL -c "\dt"` |
| **Backend (FastAPI)** | API + 에이전트 두뇌(상태머신·Policy·Executor·Reasoner) | `uvicorn app.main:app --reload` | `curl localhost:8000/health` |
| **Reasoner** | 판단 주체. `stub`(규칙) 또는 `codex`(LLM) | 환경변수 `REASONER=stub|codex` | `curl localhost:8000/` → `"reasoner"` |
| **Codex** | 별도 서버 아님. 백엔드 안에서 SDK가 `codex_cli_bin` 바이너리를 호출 | (백엔드가 자동) | 서버 로그 `codex 호출 #N` |
| **Frontend** | 고객 화면 (React) | `pnpm dev` | http://localhost:5173 |

> Codex는 "입력 부분"이 따로 있는 게 아니라, 백엔드가 `build_context`로 모은 데이터를 **워크스페이스 JSON 파일 + 프롬프트**로 만들어 SDK에 넘깁니다. 아래 4·6 참고.

---

## 1. 전체 켜기 (순서대로)

```bash
# (1) DB
sudo service postgresql start
psql postgresql://jbwm:jbwm@localhost:5432/jbwm_dev -c "select 1"   # 연결 확인

# (2) 백엔드 (stub = LLM 호출 없음, 기본)
cd ~/JB-WM/JB-WM-backend && source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
#   → 시작 시 init_db()로 테이블 생성 + seed_if_empty()로 김영자 시드
#   → 로그에 "seed 고객: <id>" 출력

# (2') 실제 LLM로 켜려면 (호출 비용 발생)
REASONER=codex CODEX_MODEL=gpt-5.4 uvicorn app.main:app --port 8000

# (3) 프론트 (별도 터미널)
cd ~/JB-WM/JB-WM-frontend && pnpm dev    # http://localhost:5173
```

---

## 2. 제일 쉽게 눈으로 보기 — Swagger UI

백엔드를 켠 뒤 브라우저에서:

```
http://localhost:8000/docs
```

- 모든 API가 버튼으로 나옴 → **"Try it out"** 으로 직접 입력·실행·응답 확인 (시각적).
- `GET /customers` → 고객 목록, `POST /agent-sessions/{id}/signals` → 신호 주입, `GET /agent-sessions/{id}/events` → 타임라인.

---

## 3. 판단 기준(두뇌)이 어디 있나

| 무엇 | 파일 | 내용 |
|---|---|---|
| **상태 전이 규칙** | `app/state_machine/states.py` `TRANSITIONS` | 어떤 상태에서 어디로 갈 수 있는지 (코드가 강제) |
| **승인 라우팅** | `app/policy/engine.py` | `has_external_effect` → auto vs 고객승인 |
| **규칙 기반 판단(stub)** | `app/agent/stub_reasoner.py` | if-else 의도추론·계획 (읽으면 판단 로직 그대로 보임) |
| **LLM 판단(codex)** | `app/agent/codex_adapter.py` | `SYSTEM_INSTRUCTIONS` + 프롬프트 + 출력 스키마. 실제 판단은 모델이 워크스페이스 파일+프롬프트로 수행 |
| **루프 조립** | `app/agent/orchestrator.py` | 신호→의도→계획→리스크→승인/실행 라우팅 |

> 즉 "판단 기준"은 두 곳: **결정론적 규칙(코드)** = 상태머신+Policy, **추론(LLM)** = codex_adapter의 프롬프트·스키마. 실행 권한은 둘 다 없음(Executor만).

---

## 4. 판단에 필요한 정보가 어디서 오나 (data provenance)

모든 입력은 `app/tools/data_tools.py`의 **`build_context(db, customer_id)`** 한 곳에서 모입니다. 각 항목의 출처:

| ctx 키 | 만든 함수 | 출처 테이블 |
|---|---|---|
| `profile` | `get_customer_profile` | `customer` |
| `health` | `get_health_data` | `healthrecord`, `healthevent` (consent 있는 것만) |
| `insurance` | `get_insurance_summary` | `insurancepolicy`, `coverageitem` |
| `loans` | `get_loan_status` | `loanaccount` |
| `portfolio` | `get_portfolio_summary` | `portfolioaccount`, `holding` |
| `asset_events` | `get_asset_events` | `assetevent` |
| `population` | `get_population_stat` | `populationstat` (② 통계, 출처 동반) |
| `memory` | `get_customer_memory` | `customermemory` (지불의향·의료비 감내 범위·성향·제약) |

- 이 데이터의 **초기값(mock)** 은 `app/seed.py` (김영자 68세).
- **통계**는 `populationstat` 테이블에 시드됨 (실제 출처 후보는 [STATS_SOURCES](STATS_SOURCES.md)).

**ctx를 그대로 덤프해서 보기** (LLM이 받는 정보 전체):
```bash
source .venv/bin/activate && python -c "
from sqlmodel import Session, select
from app.core.database import engine
from app.models.customer import Customer
from app.tools.data_tools import build_context
import json
with Session(engine) as db:
    cid = db.exec(select(Customer)).first().id
    print(json.dumps(build_context(db, cid), ensure_ascii=False, indent=2, default=str))
"
```

---

## 5. 입력(이벤트/요청)은 어떤 형식으로 어디서

진입은 단 하나의 엔드포인트:

```bash
POST /agent-sessions/{session_id}/signals
body: { "source": "event" | "user_utterance", "payload": { ... } }
```

| source | 의미 | payload 예시 |
|---|---|---|
| `event` | 시스템/자산 이벤트 (mock 트리거) | `{"kind": "portfolio_loss"}` |
| `user_utterance` | 고객 자연어 | `{"text": "다음 달 큰 지출 예정"}` |

세션 만들고 신호 주입하는 전체 흐름:
```bash
CID=$(curl -s localhost:8000/customers | python3 -c "import sys,json;print(json.load(sys.stdin)[0]['id'])")
SID=$(curl -s -X POST localhost:8000/customers/$CID/agent-sessions | python3 -c "import sys,json;print(json.load(sys.stdin)['session_id'])")
curl -s -X POST localhost:8000/agent-sessions/$SID/signals \
  -H 'Content-Type: application/json' -d '{"source":"event","payload":{"kind":"portfolio_loss"}}'
curl -s localhost:8000/agent-sessions/$SID/proposals     # 생성된 제안
curl -s localhost:8000/agent-sessions/$SID/events        # 감사 타임라인
```

---

## 6. Codex가 "실제로 본 것"을 파일로 확인

`REASONER=codex`일 때, 백엔드는 기본적으로 고객 민감 JSON 스냅샷을 워크스페이스에 쓰지 않고
`context_manifest.json` + `static_context/`만 둡니다. 동적 고객 데이터는 MCP read tools로 읽습니다.
기본 위치 `CODEX_WORKING_DIRECTORY=./workspace`:

```bash
ls ~/JB-WM/JB-WM-backend/workspace/         # jbwm_customer_<customer_id>/ 디렉토리들
cat ~/JB-WM/JB-WM-backend/workspace/jbwm_customer_*/context_manifest.json
ls ~/JB-WM/JB-WM-backend/workspace/jbwm_customer_*/static_context     # policy_docs 정적 문서
```
→ 샌드박스는 `read_only`. 모델은 이 파일들을 읽기만 하고 쓰지/실행하지 못합니다.
→ `CODEX_WORKSPACE_INCLUDE_SNAPSHOTS=true`일 때만 `portfolio.json`, `transactions.json`,
`memory.json` 같은 fallback 스냅샷이 생성됩니다.

---

## 7. 데이터를 직접 보기 (DB)

```bash
# 테이블 목록
psql $DATABASE_URL -c "\dt"

# 고객·자산·통계·메모리
psql $DATABASE_URL -c "select name, age_band from customer;"
psql $DATABASE_URL -c "select kind, severity from assetevent;"
psql $DATABASE_URL -c "select age_band, metric, source from populationstat;"
psql $DATABASE_URL -x -c "select * from customermemory;"

# 워크플로우 이력 (이게 '왜 이렇게 판단했나'의 기록)
psql $DATABASE_URL -c "select type from agentevent order by created_at;"
psql $DATABASE_URL -x -c "select kind, status, result from actionexecution;"
```

GUI로 보고 싶으면 DBeaver/TablePlus/pgAdmin에 `postgresql://jbwm:jbwm@localhost:5432/jbwm_dev` 연결.

---

## 8. 로깅 — 무슨 일이 일어나는지 실시간으로

- **서버 stdout**: 상태 전이(`session X: A -> B`), Codex 호출 수(`codex 호출 #N`), Executor 실행. `LOG_LEVEL=info`(.env).
- **DB `agentevent`**: 모든 단계 영속 (state_transition / tool_call / need_assessment / plan / execution / memory).
- **API `GET /agent-sessions/{id}/events`**: 그 세션의 타임라인 (프론트 Timeline 화면이 이걸 그림).
- **MCP read tools**: `REASONER=codex`일 때 `python -m app.mcp.read_server`가 thread config로
  등록됩니다. tool call은 `AgentEvent(type="tool_call", detail.via="mcp")`로 남습니다.

서버 로그를 따로 보고 싶으면:
```bash
uvicorn app.main:app --reload 2>&1 | tee /tmp/jbwm.log     # 화면+파일 동시
grep "jbwm" /tmp/jbwm.log                                   # 우리 로그만
```

---

## 9. 테스트로 한 번에 검증 (LLM 호출 없음)

```bash
source .venv/bin/activate
pytest app/tests/ -v
#   test_capability_no_execution_tools : 실행 도구 부재(권한 경계)
#   test_slice1_insurance_approval_flow: 승인 흐름 종단
#   test_slice2_asset_trigger_resilience: 자산 트리거 + 개인화(투자보류 제외)
#   test_slice2_population_stat_tool   : 통계 도구(출처 동반)
```

## 10. SDK 연결만 따로 점검

```bash
timeout 120s .venv/bin/python scripts/codex_smoke_test.py
```

이 smoke test는 seed/mock 고객 컨텍스트로 `assess_need -> generate_plan`을 실제 SDK reasoner에 호출하고, 같은 thread id가 재사용되는지 확인한다. OAuth/session 단계가 native subprocess에서 대기할 수 있으므로 shell `timeout`으로 감싼다.
