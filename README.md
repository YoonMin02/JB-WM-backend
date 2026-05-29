# JB WM — Backend

> **JB WM Agent** — 고객의 건강·자산·보험·대출 데이터를 **상시 관찰**하다가, 변화가 감지되면 고객의 **잠재 의도를 추론**하고, 계획을 세워 **고객 승인 후** 실제 액션까지 연결하는 **능동형 Life Event Agent**.

이 저장소는 백엔드(FastAPI)입니다. 워크플로우 상태, 데이터 접근, 권한 경계, 액션 실행, 그리고 LLM 추론(Codex SDK)을 담당합니다.

JB금융그룹 해커톤 출품작 (Lifelong WM × Health).

---

## 한눈에 보는 제품

기존 금융 서비스는 **고객이 직접** 해야 합니다.

```
건강검진 결과 확인 → 병원 갈지 판단 → 보험 보장 범위 찾기
→ 의료비가 자산계획에 주는 영향 계산 → 투자 비중 고민 → 상담사 문의
```

JB WM Agent는 이 과정을 **에이전트가 대신** 수행합니다. 고객(주 타깃: 고령층)은 데이터를 제공하기만 하고, 나머지는 에이전트가 관찰·판단·제안하며, **민감한 행동은 반드시 고객 승인**을 받습니다.

> 핵심 차별점: **(1) 능동성** — 고객이 요청하지 않아도 먼저 감지하고 판단. **(2) 건강↔금융 연계** — 건강 이벤트를 보험·자산·투자 액션으로 연결. **(3) 의도=상태** — 고객의 잠재 의도를 상태 그래프로 관리.

---

## 시스템 아키텍처

```mermaid
flowchart TB
    subgraph Client["프론트엔드"]
        UI[대시보드 / 챗 / 알림]
    end

    subgraph Backend["백엔드 (FastAPI) — 권한·상태의 주인"]
        API[API 레이어]
        ORCH[Agent Orchestrator]
        FSM[상태머신<br/>결정론적]
        POLICY[Policy Engine<br/>리스크 게이트]
        EXEC[Executor<br/>실제 실행 · LLM 미경유]
        MEM[Memory Store<br/>단기 / 장기 개인화]
    end

    subgraph Reasoning["추론 레이어 (교체 가능)"]
        PORT[[AgentReasoner 포트]]
        ADP[Codex 어댑터]
        SDK[(Codex SDK<br/>블랙박스)]
    end

    subgraph Data["데이터 / 도구"]
        MCP[MCP 읽기 도구<br/>고객·통계]
        WS[read-only 워크스페이스<br/>규정·약관 파일]
        DB[(PostgreSQL)]
    end

    UI --> API --> ORCH
    ORCH --> FSM
    ORCH --> MEM
    FSM --> POLICY --> EXEC
    ORCH --> PORT --> ADP --> SDK
    ADP -. 읽기 전용 .-> MCP
    ADP -. 읽기 전용 .-> WS
    MCP --> DB
    EXEC --> DB
    EXEC -.->|예약·청구·송금<br/>실제 API| External[(외부 시스템 / mock)]
```

**역할 분리가 이 시스템의 전부입니다:**

| 구성요소 | 책임 | 비고 |
|---|---|---|
| **상태머신 (FSM)** | 현재 상태, 허용 전이, 실행 가능 여부 | 결정론적. LLM이 못 건드림 |
| **Policy Engine** | 리스크 평가 → auto vs 고객승인 라우팅 | 코드 규칙 |
| **Executor** | 승인된 액션의 실제 실행 | **LLM을 거치지 않음** |
| **Memory Store** | 단기(진행상황) + 장기(성향·선호) | 개인화의 핵심 |
| **AgentReasoner (포트)** | 추론 인터페이스 (공급자 무관) | 우리가 영구 소유 |
| **Codex 어댑터** | 포트의 Codex 구현 | 교체 가능 (Gemini/Anthropic) |

---

## 에이전트 상태머신 (FSM)

이 그래프가 서비스 로직의 본체입니다. LLM이 아니라 **코드가** 이 전이를 강제합니다.

```mermaid
stateDiagram-v2
    [*] --> Monitoring

    Monitoring --> SignalDetected: 데이터 이벤트 감지
    Monitoring --> SignalDetected: 고객 자연어 입력

    SignalDetected --> IntentUnknown: 의도 불명확
    SignalDetected --> HealthCareIntent: 의료 대응 필요
    SignalDetected --> InsuranceIntent: 보험 점검/청구 필요
    SignalDetected --> AssetDefenseIntent: 현금흐름/자산 방어 필요
    SignalDetected --> InvestmentAdjustIntent: 투자전략 조정 필요
    SignalDetected --> LifePlanIntent: 장기 생애설계 수정 필요

    IntentUnknown --> ClarifyUser: 고객에게 질문
    ClarifyUser --> HealthCareIntent
    ClarifyUser --> InsuranceIntent
    ClarifyUser --> AssetDefenseIntent
    ClarifyUser --> InvestmentAdjustIntent
    ClarifyUser --> PreferenceUpdate: 성향/제약만 변경
    ClarifyUser --> NoAction: 지금은 원치 않음

    HealthCareIntent --> GeneratePlan
    InsuranceIntent --> GeneratePlan
    AssetDefenseIntent --> GeneratePlan
    InvestmentAdjustIntent --> GeneratePlan
    LifePlanIntent --> GeneratePlan

    GeneratePlan --> RiskCheck: 의료/금융/법적 리스크 검토
    RiskCheck --> AutoExecutable: 부작용 없는 액션
    RiskCheck --> NeedApproval: 외부 효과 있는 액션

    NeedApproval --> UserApproval
    UserApproval --> ExecuteAction: 승인
    UserApproval --> RevisePlan: 수정 요청
    UserApproval --> NoAction: 거절
    RevisePlan --> GeneratePlan

    AutoExecutable --> ExecuteAction

    ExecuteAction --> VerifyResult: 실행 결과 확인
    VerifyResult --> UpdateMemory: 고객 선호/제약 반영
    PreferenceUpdate --> UpdateMemory
    NoAction --> UpdateMemory
    UpdateMemory --> Monitoring
```

### 진입 트리거 2종

| 트리거 | 예시 | 성격 |
|---|---|---|
| 데이터/이벤트 | 건강검진 업로드, 소비 급증, 대출 만기 접근, 보험 만기 | 수동 (시스템 감지) |
| 고객 자연어 | "투자는 당분간 보수적으로 갈래" | 능동 (고객 발화) |

자연어 입력만으로 금융 액션 없이 **성향/제약이 바뀌고 장기 Memory에 저장**될 수 있습니다 (`PreferenceUpdate`).

### 의도(Intent) = 고객의 숨은 니즈

| 상태 | 고객의 숨은 의도 |
|---|---|
| `HealthCareIntent` | "검진/진료를 받아야 하나?" |
| `InsuranceIntent` | "내 보험으로 커버되나?" |
| `AssetDefenseIntent` | "당장 현금흐름 괜찮나?" |
| `InvestmentAdjustIntent` | "투자 위험도를 낮춰야 하나?" |
| `LifePlanIntent` | "장기 계획 자체를 바꿔야 하나?" |

---

## 안전 모델 — Capability 기반 (프롬프트가 아니라 권한)

LLM에게 "하지 마"라고 **부탁하지 않습니다.** 애초에 **실행 권한 자체를 주지 않습니다.**

```mermaid
sequenceDiagram
    participant A as Codex 에이전트
    participant F as 상태머신 + Policy
    participant U as 고객
    participant E as Executor (코드)
    participant X as 외부 시스템

    A->>A: 데이터 읽기·분석 (read-only)
    A->>F: ActionProposal("병원 예약")
    Note over A: 에이전트는 실행 도구가 없음<br/>제안만 생성 가능
    F->>U: 이 액션 1건 승인 요청
    U->>F: 승인
    F->>E: 승인 이벤트 전달 (LLM 미경유)
    E->>X: 실제 예약 API 호출
    X->>E: 결과
    E->>F: 완료 → VerifyResult
```

- 에이전트의 도구 = **읽기·분석·제안만** (`get_health_data`, `get_portfolio_summary`, `search_policy_documents`, `generate_plan`)
- `book_hospital()`, `submit_claim()`, `transfer_money()` 같은 **실행 도구는 에이전트에 존재하지 않음**
- Codex 샌드박스 = `read_only`, 동적 도구 = **읽기 전용 MCP** → 환각·프롬프트 인젝션이 있어도 **물리적으로 실행 불가**
- 승인은 **그 액션 1건에만** 스코핑됨 (전권 위임 아님). 승인 이벤트는 LLM을 거치지 않고 결정론적 Executor로 직행

자세히는 [docs/07_ACTION_EXECUTION.md](docs/07_ACTION_EXECUTION.md), [docs/10_SECURITY_PRIVACY.md](docs/10_SECURITY_PRIVACY.md).

---

## LLM 공급자 경계 (마이그레이션)

추론 백엔드는 교체 가능합니다. Codex SDK는 어댑터 뒤의 **블랙박스**입니다.

```mermaid
flowchart LR
    subgraph Own["우리 소유 — 공급자 무관"]
        D[도메인 / FSM / Policy / Executor / Memory / Tools]
        P[[AgentReasoner 포트]]
    end
    subgraph Swap["교체 가능 어댑터"]
        C[CodexReasoner]
        G[GeminiReasoner *미래]
        AN[AnthropicReasoner *미래]
    end
    D --> P
    P --> C
    P -.-> G
    P -.-> AN
    C --> SDK[(Codex SDK · OAuth · JSON-RPC)]
```

| 구분 | 내용 | 마이그레이션 시 |
|---|---|---|
| 블랙박스 (SDK) | 모델 통신, OAuth, 전송계층, 토큰 | 신경 안 씀 |
| 우리 소유 (포트) | 프롬프트→구조화출력, 도구 노출, 도구 루프, thread 연속 | 그대로 |
| 어댑터 | 포트의 Codex 구현 | **여기만 다시 씀** |

자세히는 [docs/04_AGENT_RUNTIME.md](docs/04_AGENT_RUNTIME.md), [docs/CODEX_ADAPTER.md](docs/CODEX_ADAPTER.md).

---

## 기술 스택

| 레이어 | 기술 |
|---|---|
| 런타임 | Python 3.12+ |
| API | FastAPI |
| 검증 | Pydantic v2 |
| DB | PostgreSQL |
| ORM | SQLModel |
| 마이그레이션 | Alembic |
| 추론 | Codex Python SDK (`openai-codex`) — OAuth 세션 |
| 워크플로우 | 자체 유한 상태머신 (FSM) |
| 도구 노출 | MCP (동적 데이터) + read-only 워크스페이스 (정적 규정) |
| 패키지 | uv |
| 테스트 | pytest |

---

## 디렉토리 구조 (목표)

```
app/
├── main.py                  FastAPI 진입점
├── core/                    설정 · DB · 로깅 · 보안
├── api/                     라우트 · 의존성
├── domains/                 customer · health · portfolio · insurance · loan
├── agent/
│   ├── runtime.py           AgentReasoner 포트 + Orchestrator
│   ├── codex_adapter.py     Codex SDK 구현 (유일한 SDK import 지점)
│   ├── schemas.py           Intent / Plan / ActionProposal 구조화 스키마
│   └── prompts.py
├── state_machine/           states · transitions · guards
├── policy/                  리스크 규칙 · 승인 라우팅
├── executor/                결정론적 액션 실행 (LLM 미경유)
├── memory/                  단기 / 장기 개인화
├── tools/                   MCP 읽기 도구 (고객 · 통계 · 규정검색)
└── tests/
```

---

## 빠른 시작

> 시스템 도구(Node·uv·Codex CLI·PostgreSQL) 사전 설치가 필요합니다. [docs/SETUP.md](docs/SETUP.md) 참고.

```bash
# 1. 가상환경 + 의존성
bash scripts/install.sh
source .venv/bin/activate

# 2. Codex 인증 (1회) — OAuth 세션
codex login

# 3. 환경변수
cp .env.example .env

# 4. 개발 서버
uvicorn app.main:app --reload   # GET /health
```

---

## 문서

설계 컨텍스트는 [`docs/`](docs/)에 있습니다. **구현 전 반드시 [docs/00_READING_ORDER.md](docs/00_READING_ORDER.md) 순서대로 읽으세요.**

| # | 문서 | 내용 |
|---|---|---|
| 00 | READING_ORDER | 읽는 순서 + 용어집 |
| 01 | PRODUCT_CONTEXT | 제품 정의 · 사용자 · MVP 시나리오 |
| 02 | SYSTEM_ARCHITECTURE | 전체 구조 · 데이터 3분류 · capability 보안 |
| 03 | STATE_MACHINE | 상태 · 전이 · 트리거 · 승인 게이트 |
| 04 | AGENT_RUNTIME | 공급자 무관 루프 + AgentReasoner 포트 |
| 05 | DATA_MODEL | 엔티티 (건강·메모리·의도·대출·액션제안) |
| 06 | TOOL_CONTRACTS | 읽기/분석/제안 도구 · 데이터 접근 |
| 07 | ACTION_EXECUTION | Policy Engine + Executor |
| 08 | MEMORY | 단기/장기 · 개인화 |
| 09 | API_SPEC | REST 엔드포인트 |
| 10 | SECURITY_PRIVACY | 규제 · capability 보안 |
| 11 | IMPLEMENTATION_ROADMAP | 수직 슬라이스 |
| — | CODEX_ADAPTER | Codex SDK 구체 연동 (실제 소스 기준) |
