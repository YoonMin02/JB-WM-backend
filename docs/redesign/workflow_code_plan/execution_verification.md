# 승인 후 실행과 처리 확인 코드 계획

이 문서는 workflow의 9번과 10번 상태를 실제 코드로 어떻게 구현할지 설명한다.

9. `승인 후 실행`: 고객이 승인한 일만 executor가 처리한다.
10. `처리 확인`: 처리 결과가 실제로 반영됐는지 verifier가 다시 확인한다.

핵심은 agent가 실행하지 않는다는 점이다. agent는 proposal을 만들 뿐이고, 실행 권한은
저장된 proposal, policy, approval, customer scope를 다시 확인한 서버 코드에서만 나온다.

## 9. 승인 후 실행

사용자 화면의 의미:

```text
고객님이 승인한 일만 처리했습니다.
```

사용자 화면에는 다음을 보여준다.

- 승인한 제안
- 실제로 처리한 일
- 처리 방식: 실제 연동, 내부 처리, 담당자 전달, 데모 mock
- 처리 결과
- 다시 확인한 근거

개발자 화면(`/dev`)에는 다음을 보여준다.

- `ActionProposal`
- `PolicyCheck` 결과
- approval decision
- executor input
- provider/mock request body
- provider/mock response body
- `ActionExecution`

## 절대 규칙

```text
agent는 실행하지 않는다.
agent output은 실행 명령이 아니다.
free-form chat text는 executor call이 아니다.
```

실행 권한은 다음 순서에서 나온다.

```text
graph_thread_id
  -> AgentThread owner check
  -> AgentSession
  -> pending_proposal_id
  -> ActionProposal
  -> PolicyCheck
  -> ApprovalDecision
  -> execute_scoped(customer_id, proposal_id)
```

`proposal_id`와 `customer_id`가 맞아도, 현재 pending proposal이 아니거나 승인이 없으면
실행하지 않는다.

## 현재 코드

현재 구현:

- `app/workflows/nodes.py::execute_action`
- `app/executor/handlers.py::execute_scoped`
- `app/policy/engine.py`

현재 방향은 맞다.

- proposal id를 다시 확인한다.
- customer scope를 다시 확인한다.
- 승인 필요 proposal은 자동 실행하지 않는다.
- handler는 mock/internal 중심이다.

다음 코드 개편에서는 executor를 action별 handler와 verifier로 분리한다.

## 목표 모듈

```text
app/executor/
  registry.py
  schemas.py
  service.py
  handlers/
    report.py
    notify_advisor.py
    cashflow_plan.py
    insurance_review.py
    portfolio_rebalance_mock.py
    accountinfo_close_transfer.py
    openbanking_transfer.py
    loan_switch_mock.py

app/verification/
  schemas.py
  service.py
  verifiers/
    report.py
    notification.py
    portfolio.py
    accountinfo.py
    transfer.py
    loan_switch.py
```

## executor 입력

executor는 UI나 agent output에서 계좌 id, token, 고객 id를 직접 받지 않는다. 입력은
`proposal_id`와 서버가 만든 scope만이다.

```json
{
  "customer_id": "server-owned-customer-uuid",
  "proposal_id": "proposal_...",
  "require_approval": true,
  "actor": "customer:user_..."
}
```

executor는 이 값을 기준으로 DB에서 proposal, session, approval, customer를 다시
읽는다. account id, provider transaction id, token은 서버 저장소나 provider vault에서
다시 가져온다.

## 상태 모델

권장 proposal 상태:

```text
proposed
approval_required
approved
rejected
executing
executed
verification_failed
failed
deferred
```

권장 execution 상태:

```text
pending
sent
succeeded
failed
verified
verification_failed
```

프론트는 이 값을 사용자 언어로 바꾼다. 예를 들어 `verified`는 "처리 결과를 다시
확인했습니다"로 보여준다.

## action별 실행 방식

| Action kind | 실행 방식 | 실행 권한 | 설명 |
|---|---|---|---|
| `report` | 내부 record/file 생성 | 자동 또는 승인 | 외부 금융 side effect 없음 |
| `notify` | 내부 알림/PB task | policy에 따라 자동 또는 승인 | 민감하면 승인 필요 |
| `cashflow_plan` | 내부 plan record | 자동 또는 승인 | 실제 금융 변경 없음 |
| `review_insurance` | 내부/mock review | 민감하면 승인 | 보험 계약 변경 아님 |
| `rebalance_portfolio` | mock 또는 advisor task | 승인 필수 | 공개 JB 실행 API 없음 |
| `close_dormant_account` | AccountInfo 후보 | 승인 필수 | 외부 API 계약 필요 |
| `transfer_cash` | Open Banking 후보 | 승인 필수 | 외부 API 계약 필요 |
| `loan_switch_request` | mock/advisor task | 승인 필수 | 사전조회/상담 중심 |

## 실제 실행 후보

### AccountInfo 해지/잔고이전

로컬 문서:

- `docs/APIs/account_info_close_transfer.md`

후보 순서:

```text
eligibility
  -> recipient
  -> status
  -> transfer
  -> result
```

구현 계획:

- handler: `AccountInfoCloseTransferExecutor`
- verifier: `AccountInfoCloseTransferVerifier`
- MVP mode: `mock_apply`
- 운영 mode: 계약, 동의, 전자서명, 한도, 결과조회가 준비된 뒤 `external_request`

필수 guardrail:

- 고객 승인
- fresh consent
- provider transaction id는 서버가 생성
- 계좌 식별자는 DB/provider vault에서 재조회
- 금액과 수수료를 고객에게 실행 전 표시
- 실행 후 result endpoint 또는 계좌 목록 재조회

### Open Banking 이체

공개 Open Banking 자료에는 이체 관련 API가 있다. 하지만 이 프로젝트에서 바로 실제
이체를 붙이면 안 된다.

구현 계획:

- handler: `OpenBankingTransferExecutor`
- verifier: `OpenBankingTransferVerifier`
- MVP mode: disabled 또는 mock
- 운영 mode: 계약, consent, access token vault, 한도, 거래 검증 뒤 활성화

필수 guardrail:

- agent에게 access token이나 `fintech_use_num`을 주지 않는다.
- action별 금액 한도를 둔다.
- `bank_tran_id` 중복을 막는다.
- 출금/입금 동의를 확인한다.
- 실행 후 잔액과 거래내역을 다시 조회한다.

## mock 또는 담당자 task로 둬야 하는 action

### JB자산운용 / 포트폴리오 리밸런싱

공개 자료에서 JB자산운용의 매매/리밸런싱 실행 API를 확인하지 못했다. 따라서 현재
시스템은 실제 JB자산운용 주문이 완료됐다고 말하면 안 된다.

허용되는 MVP 동작:

- `mock_applied`: 로컬 demo holdings만 변경
- `advisor_task_created`: 담당자/PB 검토 요청 생성
- `report_created`: 목표 비중과 리스크 설명 리포트만 생성
- `external_unavailable`: 현재 환경에서는 실행 불가 기록

사용자 문구는 명확해야 한다.

```text
데모 데이터에만 반영했습니다.
담당자 검토 요청을 만들었습니다.
실제 매매는 아직 실행하지 않았습니다.
```

### 대출 이동

로컬 문서는 대출 이동 사전조회/추천 근거에 가깝다. 그래서 "대출 갈아타기 완료"가
아니라 다음 중 하나로 처리한다.

- 사전조회 결과 기록
- 상담 task 생성
- mock request 생성
- 실행 불가 기록

## 10. 처리 확인

사용자 화면의 의미:

```text
처리 결과를 다시 확인했습니다.
```

이 단계는 executor 응답을 그대로 보여주는 것이 아니다. 별도 verifier가 실행 후
영향받은 데이터를 다시 읽어야 한다.

## verifier 계약

입력:

```json
{
  "execution_id": "exec_...",
  "proposal_id": "proposal_...",
  "customer_id": "server-owned-customer-uuid"
}
```

출력:

```json
{
  "status": "verified",
  "expected": "고위험 투자 비중을 45% 수준으로 낮춤",
  "observed": "데모 포트폴리오의 고위험 비중이 45%로 저장됨",
  "evidence": [
    {
      "label": "변경 전",
      "value": "72%"
    },
    {
      "label": "변경 후",
      "value": "45%"
    }
  ],
  "customer_message": "승인하신 방어형 조정을 데모 포트폴리오에 반영했고, 반영 결과를 다시 확인했습니다."
}
```

## action별 확인 방식

| Action kind | 확인 방식 |
|---|---|
| `report` | report row/file 재조회, hash 비교 |
| `notify` | notification/advisor task status 재조회 |
| `cashflow_plan` | 저장된 plan과 session 연결 재조회 |
| `review_insurance` | review artifact 또는 mock coverage 결과 재조회 |
| `rebalance_portfolio` | holdings 재조회, high-risk weight 재계산 |
| `close_dormant_account` | AccountInfo result API와 계좌 목록 재조회 |
| `transfer_cash` | 이체 결과 + 잔액/거래내역 재조회 |
| `loan_switch_request` | precheck/advisor task status 확인, "대출 변경 완료"라고 말하지 않음 |

## 실패 상태

실행 handler가 성공을 반환해도 verifier가 실패할 수 있다.

```text
executor says success
  -> verifier cannot observe expected result
  -> ActionExecution.status = verification_failed
  -> session returns to Monitoring or HumanReview
  -> UI says "처리 결과 확인이 필요합니다"
```

이 실패를 숨기면 안 된다. 금융 workflow에서는 보기 좋은 성공 문구보다 정직한 확인
실패가 낫다.

## 사용자 문구 예시

mock rebalance:

```text
무엇을 했나요?
승인하신 방어형 조정안을 데모 포트폴리오에 반영했습니다.

어떻게 확인했나요?
처리 후 포트폴리오를 다시 읽어서 고위험 투자 비중이 72%에서 45%로 바뀐 것을 확인했습니다.

주의
이 결과는 데모 데이터에만 반영됐고 실제 금융회사 주문은 실행되지 않았습니다.
```

AccountInfo 해지/잔고이전 mock:

```text
무엇을 했나요?
사용하지 않는 소액 계좌를 해지하고 잔액을 옮기는 절차를 데모로 처리했습니다.

어떻게 확인했나요?
해지 가능 여부, 예상 금액, 처리 결과 조회 단계를 모두 mock 응답으로 확인했습니다.

주의
실제 계좌 해지와 잔고이전은 외부 계약과 고객 전자서명이 연결된 뒤에만 실행됩니다.
```

## 구현 전 최소 테스트

- 승인 필요 proposal은 승인 전 실행할 수 없다.
- 올바른 `proposal_id`라도 다른 `customer_id`면 실패한다.
- 올바른 고객이라도 현재 pending proposal이 아니면 실패한다.
- 같은 proposal을 두 번 실행하면 기존 execution을 반환하거나 idempotency error가 난다.
- 실제 실행 비활성 모드에서는 fake success가 아니라 `external_unavailable`을 기록한다.
- mock rebalance verifier는 holdings를 다시 읽고 목표 비중을 확인한다.
- report verifier는 report record가 삭제되면 실패한다.
- `/dev`에서 executor input/output과 verifier input/output을 확인할 수 있다.
