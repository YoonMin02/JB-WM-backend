# 09 · API 명세

FastAPI REST 표면입니다. 프론트는 상태를 렌더링하고 고객 행동을 제출합니다. 유효 전이를 독자 추론하지 않습니다 ([03](03_STATE_MACHINE.md) 프론트엔드 계약).

> 변경 시 이 문서를 갱신합니다. 모든 응답은 `locale`(ko/en)을 고려합니다.

## 엔드포인트 그룹

| 그룹 | 용도 |
|---|---|
| `/health` | 서비스 헬스 체크 |
| `/auth` | 인증·세션 |
| `/customers` | 고객 프로필·도메인 데이터 조회 |
| `/agent-sessions` | 에이전트 워크플로우 (상태·신호·승인) |
| `/signals` | 이벤트/자연어 입력 주입 |
| `/proposals` | ActionProposal 승인/거절/수정 |

## Health

```
GET /health
200 { "status": "ok" }
```

## Signals (진입 트리거)

```
POST /agent-sessions/{session_id}/signals
body: { "source": "event" | "user_utterance", "payload": {...} }
202  { "session_id", "state": "SignalDetected" }
```
- `event`: 데이터 이벤트 (MVP: mock 트리거)
- `user_utterance`: 고객 자연어 입력

## Agent Sessions

```
POST /customers/{customer_id}/agent-sessions
201  { "session_id", "state": "Monitoring" }

GET  /agent-sessions/{session_id}
200  {
       "session_id", "customer_id",
       "state": "UserApproval",
       "active_needs": {
         "primary_need": "cashflow",
         "needs": {
           "medical_cost_need": "mid",
           "insurance_need": "low",
           "cashflow_need": "high",
           "asset_defense_need": "high",
           "investment_adjust_need": "low",
           "life_plan_need": "none"
         }
       },
       "allowed_actions": ["approve", "reject", "revise"],
       "pending_proposal": { "id", "kind", "summary", "has_external_effect" },
       "failure": null
     }

GET  /agent-sessions/{session_id}/events
200  { "events": [{ "type", "detail", "created_at" }] }   # 타임라인 UI
```

> 응답에는 항상 **현재 상태 + 허용 행동 + 대기 proposal + 실패 상세**를 포함합니다.

## Proposals (승인 게이트)

```
GET  /agent-sessions/{session_id}/proposals
200  { "proposals": [{ "id", "kind", "summary", "has_external_effect", "status" }] }

POST /proposals/{proposal_id}/approve
200  { "proposal_id", "status": "approved", "next_state": "ExecuteAction" }

POST /proposals/{proposal_id}/reject
200  { "proposal_id", "status": "rejected", "next_state": "NoAction" }

POST /proposals/{proposal_id}/revise
body: { "note": "투자는 빼고 보험만" }
200  { "proposal_id", "status": "revise", "next_state": "RevisePlan" }
```

- 승인은 **해당 proposal 1건에만** 적용됩니다 ([07](07_ACTION_EXECUTION.md)).
- 승인 시 백엔드 Executor가 실행하며, **LLM을 거치지 않습니다.**

## Customers (도메인 데이터)

```
GET /customers/{id}                  → 프로필
GET /customers/{id}/health           → 건강 기록·이벤트 (consent 범위)
GET /customers/{id}/portfolio        → 포트폴리오 요약
GET /customers/{id}/insurance        → 보험 요약
GET /customers/{id}/loans            → 대출 상태
GET /customers/{id}/memory           → 장기 메모리 (성향·선호)
```

> 이 엔드포인트들은 프론트 표시용입니다. **에이전트는 이 REST가 아니라 MCP 읽기 도구로** 같은 데이터에 접근합니다 ([06](06_TOOL_CONTRACTS.md)).

## 응답 패턴

- 에러는 정규화된 형태: `{ "error": { "code", "message", "detail" } }`
- 상태 머신 위반 요청은 `409 Conflict` + 허용 행동 안내
- 입력 검증 실패는 `422`

## 스트리밍 (나중)

에이전트 진행 상황 실시간 표시는 SSE/WebSocket으로 추가 (`GET /agent-sessions/{id}/stream`). MVP는 폴링(`GET /agent-sessions/{id}`)으로 충분.

## 인증

MVP는 단순 세션/JWT. 역할: 고객 / 어드바이저 / 운영자 ([10](10_SECURITY_PRIVACY.md)). 모든 고객 데이터 접근은 인증 주체로 스코핑.
