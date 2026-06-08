# JB-WM Backend

JB-WM Backend는 자산관리 고객 데이터를 읽고, 이벤트를 감지하고, LangGraph
상태 흐름 안에서 에이전트가 판단한 제안을 고객 승인 뒤에만 실행하는 FastAPI
서비스다.

이 브랜치의 핵심 목표는 기존의 `Orchestrator -> Reasoner` 방식에서 벗어나는
것이다. 기존 구조는 백엔드 안에서 LLM이 context pack을 읽고 필요도와 계획을
바로 반환하는 형태에 가까웠다. 새 구조는 다음처럼 역할을 나눈다.

```text
FastAPI/Auth
  -> 고객/thread namespace 확인
  -> LangGraph workflow
  -> scoped adapter가 고객 데이터 수집
  -> redacted DataSnapshot 생성
  -> AgentJobDispatcher가 local_stub 또는 codex exec 실행
  -> NeedAssessment / Plan / ActionProposal 검증
  -> PolicyCheck
  -> 고객 승인 대기
  -> 승인된 proposal만 Executor 실행
  -> 처리 결과 재확인
```

에이전트는 판단 worker다. DB credential, provider token, raw 계좌 식별자,
executor tool, 상태 변경 권한을 받지 않는다. 데이터 수집, 권한 확인, 승인,
실행, 감사 로그는 서버 코드가 책임진다.

## 실행 방법

### 준비물

- Python과 `uv`
- Node.js와 npm
- 실제 CLI agent job을 돌릴 경우 Codex CLI

```bash
codex --version
```

빠른 화면 테스트는 Codex CLI 없이 `AGENT_JOB_MODE=local_stub`으로 실행한다.

### 백엔드: 빠른 로컬 데모

PostgreSQL을 켜지 않고 SQLite로 바로 확인하는 방법이다.

```bash
cd ~/JB-WM/JB-WM-backend
cp .env.example .env
mkdir -p storage
DATABASE_URL=sqlite:///./storage/jbwm_demo.db \
AGENT_JOB_MODE=local_stub \
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 백엔드: 실제 Codex CLI agent job

이 모드는 이벤트마다 `codex exec` child process를 띄운다. 화면 데모보다는
느리지만, 에이전트가 샌드박스된 별도 worker로 동작한다는 경계를 검증할 수 있다.

```bash
cd ~/JB-WM/JB-WM-backend
mkdir -p storage
DATABASE_URL=sqlite:///./storage/jbwm_demo.db \
AGENT_JOB_MODE=codex_cli \
CODEX_COMMAND=codex \
AGENT_JOB_CODEX_MODEL=gpt-5.4-mini \
AGENT_JOB_CODEX_REASONING_EFFORT=low \
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

`codex_cli` 모드에서는 job마다 다음 파일이 만들어진다. 같은 정제 context payload는
agent 입력으로 `stdin`에도 전달된다. `context.json`은 `/dev`와 감사/debug에서 같은
입력을 확인하기 위한 파일이다.

```text
/tmp/jbwm-agent-jobs/{job_id}/context.json
/tmp/jbwm-agent-jobs/{job_id}/output_schema.json
/tmp/jbwm-agent-jobs/{job_id}/output.json
```

child process는 다음 조건으로 실행된다.

- `--sandbox read-only`
- `--ephemeral`
- `--model ${AGENT_JOB_CODEX_MODEL}`
- `-c model_reasoning_effort="${AGENT_JOB_CODEX_REASONING_EFFORT}"`
- job별 임시 작업 디렉터리
- `DATABASE_URL`, `JWT_SECRET`, Supabase service key, provider token 미전달
- 구조화 JSON 출력 검증

로컬에서 확인한 Codex CLI 모델 후보와 속도는
[docs/redesign/codex_cli_model_benchmark.md](docs/redesign/codex_cli_model_benchmark.md)에
정리되어 있다.

### 프론트엔드

```bash
cd ~/JB-WM/code/JB-WM-backend/webapp
npm install
npm run dev
```

브라우저에서 `http://127.0.0.1:5173`을 연다. 고객을 선택하고 금융 이벤트를
트리거하면 에이전트 분석, 제안, 승인, 처리 결과를 사용자 언어로 확인할 수 있다.

개발자 화면은 `http://127.0.0.1:5173/dev`다. 여기서는 LangGraph 단계,
agent input/output, proposal, approval, execution, debug snapshot을 볼 수 있다.

## Codex CLI 로그인

Codex CLI 로그인은 현재 터미널에만 붙는 값이 아니다. 일반적으로 현재 macOS/Linux
사용자의 `~/.codex/auth.json`에 저장되므로, 같은 사용자와 같은 `HOME`에서는 새
터미널이나 다른 프로젝트에서도 유지된다.

기본 로그인:

```bash
codex login
codex login status
```

브라우저를 열기 어려운 환경:

```bash
codex login --device-auth
```

API key로 로그인:

```bash
printenv OPENAI_API_KEY | codex login --with-api-key
```

`codex login status`가 다음처럼 실패할 수 있다.

```text
unknown variant priority, expected fast or flex
```

이 경우 현재 Codex CLI가 `service_tier = "priority"`를 읽지 못하는 상태이므로
전역 설정을 `fast`로 바꾼다.

```bash
perl -i.bak -pe 's/^service_tier = "priority"$/service_tier = "fast"/' ~/.codex/config.toml
codex login status
```

다시 로그인해야 하는 경우는 다음과 같다.

- 다른 OS 사용자 계정으로 실행
- `sudo codex ...`처럼 다른 `HOME`으로 실행
- SSH로 다른 머신 접속
- Docker/container 안에서 실행
- `HOME` 또는 `CODEX_HOME`을 다르게 지정한 shell에서 실행

## 주요 설정

로컬 기본값은 빠르고 결정론적인 stub agent다.

```dotenv
AGENT_JOB_MODE=local_stub
ACTION_EXECUTION_MODE=mock_apply
```

Codex CLI 실험용 설정:

```dotenv
AGENT_JOB_MODE=codex_cli
CODEX_COMMAND=codex
AGENT_JOB_ROOT=/tmp/jbwm-agent-jobs
AGENT_JOB_CODEX_MODEL=gpt-5.4-mini
AGENT_JOB_CODEX_REASONING_EFFORT=low
AGENT_JOB_CODEX_MODEL_CANDIDATES=gpt-5.4-mini,gpt-5.5,gpt-5.3-codex-spark,gpt-5-mini,gpt-5-nano,gpt-5.1-codex-mini,gpt-5.2-codex
```

`codex_cli`가 느린데 `runtime.input_bytes`가 작다면 앱이 불필요한 일을 많이 하는
것보다는 실제 모델 호출과 JSON schema 출력 시간이 원인일 가능성이 높다. `/dev`
화면의 `duration_seconds`, `input_bytes`, `output_bytes`로 확인한다.

## 개발자가 볼 파일 구조

```text
app/main.py
  FastAPI 앱 진입점. 라우터 등록, CORS, DB 초기화와 seed 실행을 담당한다.

app/api/routes/
  HTTP API 표면이다. 새 LangGraph 데모는 workflows.py를 사용한다.
  sessions.py/proposals.py는 기존 agent runtime 호환 경로라 당분간 유지한다.

app/core/
  설정, DB 연결, JWT 인증, 로깅 같은 애플리케이션 공통 기반이다.

app/models/
  SQLModel 테이블 정의다. workflow.py에는 AgentThread, DataSnapshot,
  AgentJob 같은 새 workflow persistence 모델이 있고, agent.py에는
  AgentSession, ActionProposal, ApprovalDecision, ActionExecution이 있다.

app/adapters/
  provider/mock 데이터를 읽어 내부 DTO와 agent context로 바꾸는 레이어다.
  현재는 app/adapters/mock/context.py가 데모 snapshot을 만든다.

app/signals/
  데이터에서 이벤트를 감지하는 코드 레이어다. 에이전트가 이벤트 존재 여부를
  invent하지 않도록 deterministic detector를 둔다.

app/workflows/
  LangGraph 상태 흐름의 중심이다. state.py는 graph state, nodes.py는 각 단계,
  wm_graph.py는 graph wiring, service.py는 API에서 쓰는 facade다.

app/agent_jobs/
  agent worker 실행 경계다. local_stub.py는 빠른 데모용, dispatcher.py는
  Codex CLI child process 실행과 output validation을 담당한다.

app/planning/
  NeedAssessment, Plan, ActionProposal schema와 validation 규칙이다.

app/policy/
  제안이 자동 처리 가능한지, 고객 승인이 필요한지 결정한다.

app/executor/
  승인된 proposal만 실제 처리한다. 현재는 mock/internal handler 중심이고,
  외부 API 실행은 별도 계약과 verifier가 생기기 전까지 막는다.

app/security/
  CustomerScope, graph scope hash 같은 고객별 namespace 보안 유틸이다.

app/agent/ 및 app/state_machine/
  이전 MVP runtime이다. 기존 테스트와 호환 API가 아직 쓰므로 바로 지우지 않는다.
  새 작업은 app/workflows/와 app/agent_jobs/를 기준으로 한다.

docs/APIs/
  계좌, 카드, 보험, 대출 관련 제공 API body를 mock/adapter 설계의 기준으로 삼는
  문서다. 의료 쪽보다 이 금융 API 문서들이 현재 재설계에서 중요하다.

docs/redesign/
  이번 브랜치의 설계 원문이다. 새로 코드를 갈아엎을 때는 README보다 먼저 이
  폴더의 읽는 순서를 따른다.

webapp/
  Vite/React 로컬 검증 UI다. 운영용 최종 UI가 아니라 LangGraph 흐름과 사용자
  안내 문구를 확인하는 테스트 하네스다.

scripts/
  개발 보조 스크립트다. benchmark_codex_cli_models.py는 Codex CLI 모델 후보를
  실제로 실행하고 결과를 docs/redesign에 남긴다.
```

## 테스트

백엔드 전체:

```bash
uv run pytest -q
```

LangGraph 재설계 집중 테스트:

```bash
uv run pytest app/tests/test_langgraph_workflow.py -q
```

프론트 빌드:

```bash
cd webapp
npm run build
```

## 배포 방향

현재 권장 방향은 다음과 같다.

- 프론트엔드: `webapp/` Vite/React 앱을 Netlify에 배포
- 백엔드/데이터: Supabase Postgres, Auth, RLS, Storage 필요 시 사용
- 민감한 실행: Supabase Edge Function 또는 private FastAPI worker에서 처리
- 에이전트 실행: Codex CLI/LangGraph 실행은 서버 내부 경계에 둠

Netlify 설정 예시:

```text
Base directory: webapp
Build command: npm run build
Publish directory: webapp/dist
```

브라우저에 노출되는 환경 변수만 `VITE_*`로 둔다.

```dotenv
VITE_API_BASE_URL=https://<backend-or-supabase-edge-endpoint>
```

Supabase service-role key, provider token, VAPID private key, Codex 관련 인증값은
브라우저나 Netlify frontend env에 넣지 않는다.

## 문서 읽는 순서

재설계는 [docs/redesign/README.md](docs/redesign/README.md)부터 읽는다.
특히 다음 문서를 먼저 보면 전체 흐름이 잡힌다.

- [docs/redesign/architecture.md](docs/redesign/architecture.md)
- [docs/redesign/workflow.md](docs/redesign/workflow.md)
- [docs/redesign/security.md](docs/redesign/security.md)
- [docs/redesign/agent_jobs.md](docs/redesign/agent_jobs.md)
- [docs/redesign/workflow_code_plan/](docs/redesign/workflow_code_plan/)

기존 번호 문서는 MVP와 제품 맥락을 이해하는 데 유용하지만, 이 브랜치에서 코드를
갈아엎을 때의 기준은 `docs/redesign/`이다.
  