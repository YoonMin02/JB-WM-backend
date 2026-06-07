# 00 · 읽는 순서 & 용어집

이 디렉토리는 JB WM 백엔드의 구현 컨텍스트입니다. 현재 브랜치의 source of
truth는 `redesign/` 폴더입니다. 번호가 붙은 기존 문서는 제품 배경과 legacy
MVP 맥락으로 읽고, 새 구현은 LangGraph + sandboxed agent job 문서를 우선합니다.

## 읽는 순서

1. [`redesign/README.md`](redesign/README.md) — 현재 브랜치 구현 가이드
2. [`redesign/architecture.md`](redesign/architecture.md) — 레이어와 폴더 구조
3. [`redesign/workflow.md`](redesign/workflow.md) — LangGraph 상태와 node flow
4. [`redesign/security.md`](redesign/security.md) — namespace, sandboxing, 보안 불변식
5. [`redesign/agent_jobs.md`](redesign/agent_jobs.md) — Codex-with-Gmail 방식의 CLI job runner
6. [`redesign/react_demo.md`](redesign/react_demo.md) — 로컬 React 테스트 하네스
7. [`redesign/testing.md`](redesign/testing.md) — QA/테스트 기준
8. [`14_LANGGRAPH_AGENT_REDESIGN.md`](14_LANGGRAPH_AGENT_REDESIGN.md) — 초기 재기획 메모

Legacy/MVP 배경 문서:

- [`01_PRODUCT_CONTEXT.md`](01_PRODUCT_CONTEXT.md) — 제품 정의, 사용자, MVP 시나리오
- [`02_SYSTEM_ARCHITECTURE.md`](02_SYSTEM_ARCHITECTURE.md) — 기존 MVP 구조
- [`03_STATE_MACHINE.md`](03_STATE_MACHINE.md) — 기존 FSM 상태·전이
- [`04_AGENT_RUNTIME.md`](04_AGENT_RUNTIME.md) — 기존 `AgentReasoner` 포트
- [`05_DATA_MODEL.md`](05_DATA_MODEL.md) — 기존 엔티티와 영속화 모델
- [`06_TOOL_CONTRACTS.md`](06_TOOL_CONTRACTS.md) — 기존 도구/데이터 접근
- [`07_ACTION_EXECUTION.md`](07_ACTION_EXECUTION.md) — Policy Engine + Executor 배경
- [`08_MEMORY.md`](08_MEMORY.md) — 단기/장기 메모리
- [`09_API_SPEC.md`](09_API_SPEC.md) — 기존 REST 엔드포인트
- [`10_SECURITY_PRIVACY.md`](10_SECURITY_PRIVACY.md) — 기존 보안/프라이버시 메모
- [`13_LLM_DECISION_CONTEXT.md`](13_LLM_DECISION_CONTEXT.md) — 기존 LLM 판단 컨텍스트

참고 자료 (번호 없음, 필요 시):
- [`ENVIRONMENT_VARIABLES.md`](ENVIRONMENT_VARIABLES.md) — 환경변수
- [`APIs/`](APIs/) — 외부 API 원문 shape + 내부 adapter/agent tool 매핑 (MVP는 mock)

## 용어집 (Glossary)

문서·코드 전반에서 일관되게 사용합니다.

### 상태 (State) — FSM 노드

| 용어 | 의미 |
|---|---|
| `Monitoring` | 명시적 의도 없음. 데이터 관찰 중 (기본 상태) |
| `SignalDetected` | 이벤트/발화 감지됨. 의도 분류 대기 |
| `AssessNeed` | 의료비·보험·현금흐름·자산방어·투자·생애설계 필요도를 함께 평가 |
| `ClarifyUser` | 고객에게 명확화 질문 중 |
| `GeneratePlan` | 통합 필요도에 맞는 액션 계획 생성 |
| `RiskCheck` | 계획의 의료/금융/법적 리스크 평가 |
| `AutoExecutable` | 부작용 없는 액션 (승인 불필요) |
| `NeedApproval` | 외부 효과 있는 액션 (고객 승인 필요) |
| `UserApproval` | 고객 승인 대기 |
| `RevisePlan` | 고객 수정 요청 → 재계획 |
| `ExecuteAction` | 승인/자동 액션 실제 실행 |
| `VerifyResult` | 실행 결과 검증 |
| `PreferenceUpdate` | 금융 액션 없이 성향/제약만 변경 |
| `UpdateMemory` | 고객 선호/제약 메모리 반영 |
| `NoAction` | 액션 안 함 (거절/보류) |

### 핵심 개념

| 용어 | 의미 |
|---|---|
| **회복탄력성(resilience)** | 건강·자산을 합친 단일 상태. 제품의 핵심 관점 (양방향) — [01](01_PRODUCT_CONTEXT.md) |
| **Signal** | 상태 전이를 유발하는 사건 (자산 변동 선제 / 건강 제출 / 자연어) |
| **자산 트리거 / 건강 트리거** | 자산=실시간 선제 감지(메인 능동성), 건강=고객 제출 시 재평가 |
| **지불의향(medical_willingness)** | "의료에 얼마 쓸 용의" — 1급 개인화 변수 ([08](08_MEMORY.md)) |
| **NeedAssessment** | 신호와 고객 컨텍스트로부터 산출한 통합 필요도 평가 |
| **Plan** | 의도를 충족하기 위한 액션들의 집합 (LLM 생성) |
| **ActionProposal** | LLM이 생성한 실행 *제안*. 실행 그 자체가 아님 |
| **Policy Engine** | 리스크를 평가해 auto vs 고객승인을 결정하는 코드 규칙 |
| **Executor** | 승인된 액션을 실제 수행하는 결정론적 코드. **LLM을 거치지 않음** |
| **Memory (단기)** | 진행 중 task, 승인 대기, 최근 대화 |
| **Memory (장기)** | 고객 성향·선호·제약·지불의향 (개인화) |
| **AgentThread** | opaque `graph_thread_id`와 고객/session scope를 묶는 namespace row |
| **LangGraph Workflow** | 상태 오케스트레이션과 승인 interrupt/resume. 인증 경계가 아님 |
| **AgentJob** | 이벤트마다 생성되는 독립 판단 worker 실행 단위 |
| **DataSnapshot** | agent-facing redacted context pack과 hash |
| **AgentReasoner** | legacy 추론 포트. 새 구현은 `app/agent_jobs` 사용 |
| **PydanticAIReasoner** | legacy LLM 구조화 출력 구현. 새 런타임 source of truth 아님 |
| **이중 capability 경계** | ① 실행 경계(실행 권한 없음) ② 의료 경계(의료 권고 생성 안 함). 프롬프트 가드레일과 대비 |

### 데이터 3분류 (자세히는 02, 06)

| 분류 | 예시 | 접근 |
|---|---|---|
| ① 고객 개인 데이터 | 포트폴리오·건강·보험·대출 | backend read function → context pack |
| ② 통계/기준 데이터 | 연령대별 자산·위험률·생명표 | 파라미터 쿼리/정규화 함수 |
| ③ 비정형 텍스트 | 약관·내규·규정 | `policy_docs/` 주입 (MVP) → RAG (나중) |

## 문서 유지 규칙

- API 변경 → `09_API_SPEC.md`
- 데이터 모델 변경 → `05_DATA_MODEL.md`
- 도구 변경 → `06_TOOL_CONTRACTS.md`
- 상태 전이 변경 → `03_STATE_MACHINE.md`
- 환경변수 변경 → `ENVIRONMENT_VARIABLES.md`
- LLM 판단/컨텍스트 변경 → `04_AGENT_RUNTIME.md` + `13_LLM_DECISION_CONTEXT.md`
