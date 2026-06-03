# MVP Mock Implementation Guide

이 문서는 `docs/APIs/`의 외부 API 명세를 실제 연동 없이 MVP 개발에 사용하는 방법을
정리합니다. 현재 목표는 외부망 호출이 아니라, **원문 body 형식과 항목을 기준으로 내부
mock 데이터와 read tool contract를 안정적으로 만드는 것**입니다.

## 결론

MVP에서는 다음 순서를 따릅니다.

1. 원문 API 문서에서 request/response의 항목명, 타입, 날짜/금액 형식을 확인합니다.
2. provider 원문 응답을 [`INTERNAL_ADAPTER_CONTRACTS.md`](INTERNAL_ADAPTER_CONTRACTS.md)의 내부 DTO로 변환합니다.
3. agent에게는 [`AGENT_TOOL_MAPPING.md`](AGENT_TOOL_MAPPING.md)의 read tool 출력만 제공합니다.
4. OAuth, 핀테크이용번호, 계좌번호, 카드식별값, 증권번호, 개인실명번호는 mock 데이터에는 있을 수 있지만 agent 출력에서는 제거합니다.
5. 실제 외부 API 연결은 adapter 내부 구현으로만 추가하고, FSM/Orchestrator/Policy/Executor는 provider 원문 필드에 의존하지 않습니다.

## 개발 대상

| 우선순위 | 영역 | 원문 문서 | 내부 DTO | Agent tool | MVP 목적 |
|---|---|---|---|---|---|
| 1 | 계좌 잔액 | `account_balance.md`, `account_info_integrated_list.md` | `AccountBalance` | `get_account_balances` | 유동성, 비상자금, 현금흐름 |
| 1 | 계좌 거래 | `account_transaction_list.md` | `AccountTransaction` | `get_account_transactions` | 의료비/고정비/지출 급증 감지 |
| 1 | 보험 | `insurance_list.md`, `insurance_payment.md` | `InsurancePolicySummary` | `get_insurance_summary` | 보장 공백, 보험료 부담 |
| 1 | 대출 | `loan_lease_list.md`, `loan_lease_basic.md` | `LoanSummary` | `get_loan_summary` | 상환일, 월상환, 부채 압박 |
| 2 | 카드 | `card_list.md`, `card_issue.md`, `card_bill_basic.md`, `card_bill_detail.md` | `CardBill` | `get_card_bills` | 다음 달 청구액, 카드 의료비 |
| 2 | 대출이동 | `personal_credit_loan.md`, `mortgage_loan.md`, `jeonse_loan.md` | `LoanSwitchPrecheck` | `get_loan_switch_precheck` | 대환 가능성 사전 참고 |
| 3 | 계좌해지/잔고이전 | `account_info_close_transfer.md` | 없음 또는 Executor DTO | Agent 노출 금지 | 승인 후 실행 후보, MVP 미연결 |

## Mock Adapter 역할

Mock adapter는 실제 provider처럼 보이는 원문 응답을 그대로 agent에게 넘기지 않습니다.
대신 아래 변환 단계를 수행합니다.

```text
provider-shaped mock payload
  -> normalize amount/date/code
  -> hide provider identifiers and secrets
  -> internal DTO
  -> compact agent-facing tool result
```

예를 들어 오픈뱅킹 잔액조회 원문은 `balance_amt`, `available_amt`,
`fintech_use_num`을 포함하지만, agent-facing 출력은 다음 정도로 줄어듭니다.

```json
{
  "accounts": [
    {
      "account_id": "acct_1",
      "bank_name": "오픈은행",
      "product_name": "알뜰살뜰적금",
      "account_type": "deposit",
      "balance_krw": 1000000,
      "available_krw": 1000000,
      "last_transaction_on": "2019-10-10"
    }
  ],
  "liquidity_summary": {
    "available_cash_krw": 1000000,
    "emergency_fund_months": 1.2
  }
}
```

## 상태머신과의 관계

외부 API shape는 상태를 늘리기 위한 근거가 아닙니다. API 데이터는
`AssessNeed -> GeneratePlan`에서 필요한 근거로 쓰입니다.

`AssessNeed`는 다음 필요도를 함께 평가합니다.

- `medical_cost_need`
- `insurance_need`
- `cashflow_need`
- `asset_defense_need`
- `investment_adjust_need`
- `life_plan_need`

예를 들어 폐암 이벤트와 카드/계좌 의료비 지출이 함께 들어오면:

```text
health event + medical spending
  -> medical_cost_need high
  -> insurance_need mid/high
  -> cashflow_need high
  -> asset_defense_need mid
  -> investment_adjust_need mid/high
  -> GeneratePlan에서 통합 전략 생성
```

즉 `의료비`, `보험`, `현금흐름`, `자산방어`, `투자전략`, `장기 생애설계`는
서로 독립된 thread나 별도 agent가 아니라, 한 고객 세션 안에서 함께 평가되는 축입니다.

## Agent에게 주면 안 되는 값

아래 값은 mock 데이터에 있더라도 agent-facing tool 출력에서 제거합니다.

- `Authorization`, `access_token`, `refresh_token`
- `fintech_use_num`, `user_seq_no`
- 원 계좌번호, 상환계좌번호, 카드 식별값, 증권번호
- `customer_identity_num`
- provider 거래고유번호, 조회추적정보
- 입금이체, 출금이체, 계좌해지, 잔고이전, 대출이동 실행에 필요한 입력

## Seed 데이터 작성 기준

mock 데이터는 “예쁜 예시 하나”보다 실제 판단이 갈리는 케이스를 많이 갖는 편이 좋습니다.

- 정상 현금흐름 고객
- 의료비 급증 고객
- 보험료가 과도한 고객
- 보험 보장 공백이 있는 고객
- 카드 청구가 다음 달 현금흐름을 압박하는 고객
- 대출 상환일이 월초/월말에 몰린 고객
- 유동성은 충분하지만 고위험 자산 비중이 높은 고객
- 장기 생애설계 수정이 필요한 고객
- 단순 선호/성향 업데이트만 필요한 고객

MVP에서는 최소한 위 케이스가 `AssessNeed` 결과를 다르게 만들도록 seed를 구성합니다.

## 실제 연동으로 넘어갈 때

실제 provider API 연결은 아래 영역만 바꿉니다.

- OAuth/동의 저장소
- provider client
- provider response parser
- mock adapter를 대체하는 real adapter

아래 영역은 바꾸지 않는 것을 목표로 합니다.

- 상태머신
- `NeedAssessment`
- `Plan` / `ActionProposal`
- agent-facing read tool 출력
- Policy / Executor 승인 흐름
