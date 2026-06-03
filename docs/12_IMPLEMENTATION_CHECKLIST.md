# 12 · 구현 체크리스트

이 문서는 설계 문서가 목표로 하는 구조와 현재 코드 사이의 구현 상태를 추적합니다.
문서와 코드가 다르더라도, 아래 항목이 "미구현/후속 구현"으로 분류되어 있으면 설계 방향은 유지합니다. 새 불일치가 발견되면 항목을 추가하고, 구현·테스트가 끝나면 체크합니다.

## Codex Thread = Customer Holistic Agent Session

- [x] `AgentReasoner` 포트에 세션 생명주기 메서드를 명확히 둔다.
  - `start_session(customer_id, ctx) -> thread_id`
  - `resume_session(thread_id)`
  - `assess_need(...)`
  - `generate_plan(...)`
- [x] `AgentSession.agent_thread_id`에 Codex thread id를 저장한다.
- [x] 기본은 고객 1명당 active holistic `AgentSession` 1개로 제한한다.
- [x] `POST /customers/{customer_id}/agent-sessions` 시 기존 active session을 재사용한다.
- [x] 이후 signal, revise 요청은 새 thread가 아니라 기존 thread를 `thread_resume()`으로 이어간다.
- [x] Codex thread 하나가 고객별 holistic agent session 하나에 대응하도록 보장한다.
- [x] intent 상태는 전문 agent 분기가 아니라 하나의 통합 agent 안의 주된 니즈 라벨임을 코드/문서/프롬프트에 반영한다.
- [x] thread 시작 시 `cwd`는 백엔드 소스가 아니라 안전한 agent workspace만 가리키게 한다.
- [x] Codex compact/요약이 발생해도 감사와 재현을 위해 원본 대화/이벤트는 DB에 별도 저장한다.

## Conversation / Transcript Persistence

- [x] 고객 발화, 시스템 신호, Codex 최종 응답/요약, 생성된 need assessment/plan을 append-only로 저장할 테이블을 추가한다.
- [x] 가능한 모델 예시:
  - `AgentMessage`: `session_id`, `role`, `content`, `metadata`, `created_at`
  - `NeedAssessmentRecord`: `session_id`, `needs`, `primary_need`, `confidence`, `rationale`, `raw_output`, `created_at`
  - `PlanRecord`: `session_id`, `explanation`, `raw_output`, `created_at`
- [x] `AgentEvent`는 타임라인/감사용 이벤트로 유지하고, 전문 대화 저장과 역할을 분리한다.
- [x] 개인정보/민감정보 보유기간과 동의 철회 시 파기 정책을 반영한다.

## MCP Read Tools

- [x] 현재 `build_context()` JSON 파일 방식은 MVP fallback으로 남기되, 실제 동적 데이터 접근은 MCP 읽기 도구로 옮긴다.
- [x] 고객 데이터 도구:
  - [x] `get_customer_profile`
  - [x] `get_health_data`
  - [x] `get_portfolio_summary`
  - [x] `get_asset_events`
  - [x] `get_insurance_summary`
  - [x] `get_loan_status`
  - [x] `get_account_balances`
  - [x] `get_account_transactions`
  - [x] `get_card_bills`
  - [x] `get_loan_switch_precheck`
  - [x] `get_customer_memory`
- [x] 통계/기준 도구:
  - [x] `get_population_stat`
- [x] 문서 검색 도구:
  - [x] `search_policy_documents`
- [x] 모든 MCP 도구는 customer/session scope를 강제한다.
- [x] 실행 도구(`book_*`, `submit_*`, `transfer_*`, `change_*`)는 MCP에도 절대 등록하지 않는다.
- [x] MCP tool call은 `AgentEvent` 또는 별도 감사 테이블에 기록한다.

## Safe Workspace / Static Context

- [x] Codex workspace에는 현재 agent session에 필요한 파일만 둔다.
- [x] 백엔드/프론트 소스 코드는 workspace에 포함하지 않는다.
- [x] 회사 내규, 상품 약관, 반복 사용 통계/정책 문서 등 비교적 정적이고 유용한 문서를 read-only 파일로 제공한다.
- [x] 고객별 민감 데이터는 workspace에 최소화하거나 MCP read tool로 제공한다.
- [x] workspace 생성, 재사용, 정리 정책을 문서화한다.

## API / Frontend Contract

- [x] 프론트가 호출하는 `GET /customers/{customer_id}/portfolio`를 백엔드에 구현한다.
- [x] API 문서의 proposal 승인 응답을 실제 구현과 맞춘다.
  - 현재 구현: 승인/거절/수정 후 최종 `Session` 객체 반환.
  - 문서 예시: `{ proposal_id, status, next_state }`.
  - 둘 중 하나로 통일한다.
- [x] 승인 후 상태를 즉시 `Monitoring`까지 완료할지, `ExecuteAction`/`VerifyResult` 중간 상태를 프론트에 노출할지 결정한다.
  - MVP 정책: 서버에서 `Monitoring`까지 완료하고, 중간 상태는 `AgentEvent`로 노출한다.
- [x] 다중 승인 proposal queue가 필요한 경우 `pending_proposal_id` 단일 필드를 확장한다.
  - MVP 정책: 단일 `pending_proposal_id` 유지. 다중 큐는 후속 확장으로 둔다.

## Data Model Alignment

- [x] 문서의 `NeedAssessment`/`Plan` 엔티티를 실제 테이블로 만들지, `AgentEvent`/`ActionProposal`로 대체할지 결정한다.
- [x] 실제 테이블을 만들 경우:
  - [x] `NeedAssessmentRecord`
  - [x] `PlanRecord`
  - [x] `PlanRecord` 1건과 `ActionProposal` N건의 관계 (`proposal_ids`로 추적)
- [x] 대체 설계는 유지하지 않는다. `05_DATA_MODEL.md`는 실제 `NeedAssessmentRecord`/`PlanRecord` 테이블 기준으로 갱신했다.
- [x] `CustomerMemory.medical_willingness`를 의료비 감내 범위/지불의향으로 확장한다.
  - [x] enum(`conservative`/`moderate`/`aggressive`)에 금액대/월 현금흐름 비율/일회성 부담 한도를 같이 둔다.
  - [x] 의료 관련 plan이 비용 범위별 재무 시나리오를 생성하도록 `Plan`/`ActionProposal` 파라미터에 의료비 감내 범위를 반영한다.
  - [x] 치료법 추천 금지와 비용 범위별 시나리오 허용을 프롬프트와 테스트에 반영한다.

## Frontend Dependencies

- [x] `JB-WM-frontend/README.md`의 기술 스택을 실제 `package.json`과 동기화한다.
- [x] React Router, Zustand, shadcn/ui, Recharts를 현재는 도입하지 않는 것으로 정리한다.
- [x] 아직 도입하지 않은 항목은 "planned"로 표시한다.

## Security / Privacy

- [x] 인증/JWT와 역할 기반 접근 제어를 구현한다.
- [x] consent 없는 건강 데이터가 도구/API에서 반환되지 않는지 테스트한다.
- [x] Codex adapter가 항상 `Sandbox.read_only`를 쓰는 회귀 테스트를 추가한다.
- [x] 고객별 workspace가 소스 파일 없이 manifest/static context만 포함하고, 민감 스냅샷은 opt-in fallback임을 회귀 테스트로 고정한다.
- [x] Codex SDK 관련 rate-limit/error handling을 API 에러로 정규화한다.
