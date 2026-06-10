# 재설계 아키텍처

이 문서는 JB-WM을 어떤 구조로 다시 짤지 설명한다. 핵심은 "LLM이 백엔드 안에서
함수처럼 판단하고 바로 결과를 반환하는 구조"에서 벗어나, 코드가 데이터와 실행을
통제하고 에이전트는 제한된 판단 worker로만 동작하게 만드는 것이다.

## 목표 구조

```text
API/Auth
  -> 고객 scope와 workflow thread 확인
  -> LangGraph 상태 흐름 실행
  -> Scoped Data Layer가 고객 데이터 수집
  -> DataSnapshot과 agent context 생성
  -> AgentJobDispatcher가 local_stub 또는 Codex CLI worker 실행
  -> NeedAssessment / Plan / ActionProposal 검증
  -> PolicyCheck로 승인 필요 여부 판단
  -> 고객 승인 대기 또는 자동 내부 처리
  -> Executor가 승인된 proposal만 실행
  -> Verifier가 처리 결과 재확인
  -> 감사 로그와 필요 시 알림 기록
```

이 구조에서 LangGraph는 상태 순서를 관리한다. 보안은 LangGraph가 아니라
API/Auth, 고객 scope, DB 정책, sandbox, executor gate가 맡는다.

## 레이어별 책임

| 레이어 | 책임 | 하면 안 되는 일 |
|---|---|---|
| API/Auth | JWT/principal 확인, 고객 접근권 확인, thread owner check | 사용자가 보낸 `customer_id`나 `thread_id`를 그대로 신뢰 |
| Scoped Data | 금융 API/mock adapter 호출, 원문 응답 정규화, context snapshot 생성 | provider raw id, token, 계좌번호를 agent에 노출 |
| Signals | 데이터에서 이벤트 후보를 결정론적으로 감지, 중복/쿨다운 판단 | 이벤트 존재 여부를 LLM에게 맡김 |
| LangGraph | 상태 전이, interrupt/resume, node 순서 관리 | 권한 검증 장치처럼 사용 |
| Agent Jobs | 단일 고객 context를 해석해 필요도와 제안 생성 | DB 조회, 외부 API 호출, 금융 실행, 상태 변경 |
| Planning/Validation | agent output schema 검증, 금지 id/namespace 누출 차단 | 자유 텍스트를 실행 명령으로 해석 |
| Policy | 자동 처리와 승인 필요 작업 분리 | `has_external_effect` 값을 그대로 믿고 통과 |
| Executor | 승인된 proposal을 scope 재확인 후 처리 | 승인 전 실행, 다른 고객 proposal 실행 |
| 처리 확인 | 실행 결과를 다시 읽어 실제 반영 여부 확인 | executor 응답만 믿고 "완료" 표시 |
| Notification | 확정된 상태를 사용자에게 알림 | agent가 직접 알림 발송 |

## 코드 모듈 지도

```text
app/adapters/
  금융 API 또는 mock provider 응답을 읽고 내부 DTO/context로 정규화한다.

app/signals/
  계좌, 카드, 보험, 대출, 투자 데이터에서 이벤트를 감지한다.

app/security/
  CustomerScope, scope hash, 고객별 namespace 보안 유틸을 둔다.

app/planning/
  NeedAssessment, Plan, ActionProposal schema와 출력 검증 규칙을 둔다.

app/agent_jobs/
  local_stub 또는 Codex CLI child process를 실행하고 결과를 검증한다.

app/workflows/
  LangGraph state, node, graph wiring, API service facade를 둔다.

app/policy/
  proposal이 자동 처리 가능한지, 고객 승인이 필요한지 판단한다.

app/executor/
  승인된 action을 내부/mock/external handler로 처리한다.

webapp/
  로컬 React 검증 화면이다. 운영 UI가 아니라 흐름 확인용 테스트 하네스다.
```

공식 실행 경로는 `app/workflows/`, `app/agent_jobs/`, `app/planning/`,
`app/security/`, `app/policy/`, `app/executor/`다. 고객 대면 세션 상태는
`app/workflows/session_state.py`의 작은 enum으로만 관리하고, 내부 흐름의 기준은
LangGraph node/edge다.

## 중요한 설계 결론

에이전트는 "무엇이 문제이고 어떤 제안이 필요한가"를 판단한다. 하지만 "어떤 고객의
데이터를 읽을 수 있는가", "승인 없이 실행 가능한가", "실제로 처리됐는가"는 코드가
결정한다. 이 경계를 흐리면 고객 context가 섞이거나, 프롬프트 인젝션으로 다른 고객
조회/실행이 시도될 수 있다.

따라서 앞으로 코드를 갈아엎을 때도 다음 원칙은 유지한다.

- 고객 데이터 조회는 scoped adapter만 한다.
- agent job에는 정제된 단일 고객 context payload만 전달한다.
- agent output은 저장 전에 schema와 보안 검증을 통과해야 한다.
- 외부효과가 있는 proposal은 고객 승인 전 실행하지 않는다.
- executor는 `proposal_id`로 DB를 다시 읽고 고객 scope를 재확인한다.
- verifier는 실행 후 영향을 받은 데이터를 다시 읽어 결과를 확인한다.
