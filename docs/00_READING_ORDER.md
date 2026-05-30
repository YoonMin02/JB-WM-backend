# 00 · 읽는 순서 & 용어집

이 디렉토리는 JB WM 백엔드의 구현 컨텍스트입니다. 구현은 관련 설계 문서를 검토한 뒤 시작합니다.

## 읽는 순서

1. [`01_PRODUCT_CONTEXT.md`](01_PRODUCT_CONTEXT.md) — 제품 정의, 사용자, MVP 시나리오
2. [`02_SYSTEM_ARCHITECTURE.md`](02_SYSTEM_ARCHITECTURE.md) — 전체 구조, 데이터 3분류, capability 보안
3. [`03_STATE_MACHINE.md`](03_STATE_MACHINE.md) — 상태·전이·트리거·승인 게이트 (**서비스 로직의 본체**)
4. [`04_AGENT_RUNTIME.md`](04_AGENT_RUNTIME.md) — 공급자 무관 에이전트 루프 + `AgentReasoner` 포트
5. [`05_DATA_MODEL.md`](05_DATA_MODEL.md) — 엔티티와 영속화 모델
6. [`06_TOOL_CONTRACTS.md`](06_TOOL_CONTRACTS.md) — 에이전트에 노출하는 도구 + 데이터 접근
7. [`07_ACTION_EXECUTION.md`](07_ACTION_EXECUTION.md) — Policy Engine + 결정론적 Executor
8. [`08_MEMORY.md`](08_MEMORY.md) — 단기/장기 메모리, 개인화
9. [`09_API_SPEC.md`](09_API_SPEC.md) — REST 엔드포인트
10. [`10_SECURITY_PRIVACY.md`](10_SECURITY_PRIVACY.md) — 규제, capability 보안
11. [`11_IMPLEMENTATION_ROADMAP.md`](11_IMPLEMENTATION_ROADMAP.md) — 수직 슬라이스 구현 계획
12. [`12_IMPLEMENTATION_CHECKLIST.md`](12_IMPLEMENTATION_CHECKLIST.md) — 문서 목표와 현재 코드 사이의 남은 구현 항목

**Codex SDK / 에이전트 런타임을 건드리는 작업 전**: [`04_AGENT_RUNTIME.md`](04_AGENT_RUNTIME.md) → [`CODEX_ADAPTER.md`](CODEX_ADAPTER.md) → `external/codex-sdk/` 순으로 읽으세요.

참고 자료 (번호 없음, 필요 시):
- [`CODEX_ADAPTER.md`](CODEX_ADAPTER.md) — Codex SDK 구체 연동 (실제 `~/codex/sdk/python` 기준)
- [`ENVIRONMENT_VARIABLES.md`](ENVIRONMENT_VARIABLES.md) — 환경변수
- `external/codex-sdk/` — 공식 SDK 문서 스냅샷

## 용어집 (Glossary)

문서·코드 전반에서 일관되게 사용합니다.

### 상태 (State) — FSM 노드

| 용어 | 의미 |
|---|---|
| `Monitoring` | 명시적 의도 없음. 데이터 관찰 중 (기본 상태) |
| `SignalDetected` | 이벤트/발화 감지됨. 의도 분류 대기 |
| `IntentUnknown` | 의도 불명확 → 고객에게 질문 필요 |
| `ClarifyUser` | 고객에게 명확화 질문 중 |
| `*Intent` | 추론된 고객 의도 (HealthCare / Insurance / AssetDefense / InvestmentAdjust / LifePlan) |
| `GeneratePlan` | 의도에 맞는 액션 계획 생성 |
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
| **Intent** | 신호로부터 추론된 고객의 잠재 의도. 상태로 표현됨 |
| **Plan** | 의도를 충족하기 위한 액션들의 집합 (LLM 생성) |
| **ActionProposal** | LLM이 생성한 실행 *제안*. 실행 그 자체가 아님 |
| **Policy Engine** | 리스크를 평가해 auto vs 고객승인을 결정하는 코드 규칙 |
| **Executor** | 승인된 액션을 실제 수행하는 결정론적 코드. **LLM을 거치지 않음** |
| **Memory (단기)** | 진행 중 task, 승인 대기, 최근 대화 |
| **Memory (장기)** | 고객 성향·선호·제약·지불의향 (개인화) |
| **AgentReasoner** | 추론 백엔드의 공급자 무관 인터페이스 (포트) |
| **Codex 어댑터** | `AgentReasoner`의 Codex SDK 구현 |
| **이중 capability 경계** | ① 실행 경계(실행 권한 없음) ② 의료 경계(의료 권고 생성 안 함). 프롬프트 가드레일과 대비 |

### 데이터 3분류 (자세히는 02, 06)

| 분류 | 예시 | 접근 |
|---|---|---|
| ① 고객 개인 데이터 | 포트폴리오·건강·보험·대출 | MCP 읽기 도구 (per-customer 스코핑) |
| ② 통계/기준 데이터 | 연령대별 자산·위험률·생명표 | 파라미터 쿼리 도구 (≠ RAG) |
| ③ 비정형 텍스트 | 약관·내규·규정 | 파일 읽기 (MVP) → RAG (나중) |

## 문서 유지 규칙

- API 변경 → `09_API_SPEC.md`
- 데이터 모델 변경 → `05_DATA_MODEL.md`
- 도구 변경 → `06_TOOL_CONTRACTS.md`
- 상태 전이 변경 → `03_STATE_MACHINE.md`
- 환경변수 변경 → `ENVIRONMENT_VARIABLES.md`
- Codex SDK 연동 변경 → `04_AGENT_RUNTIME.md` + `CODEX_ADAPTER.md`
