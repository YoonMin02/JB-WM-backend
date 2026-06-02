# Agent Tool Mapping

이 문서는 외부 API 원문이 JB WM agent read tool로 어떻게 노출되는지 정의합니다.
실제 외부 API 호출 여부와 무관하게, agent는 아래 tool contract만 봅니다.

MVP에서는 아래 tool들을 실제 외부 API에 연결하지 않습니다. `docs/APIs/`의 원문 body
항목을 참고해 seed/mock adapter가 같은 의미의 내부 DTO를 만들고, agent에게는 이
문서의 compact output만 제공합니다.

## Capability Boundary

Agent에게 노출 가능:

- 잔액, 출금가능금액, 최근 거래 요약
- 카드 청구 예정액/상세 요약
- 보험 상품명, 상태, 납입 주기/금액
- 대출 종류, 상환일, 상환방식, 최근 상환 거래
- 대출이동 사전조회 결과 중 수수료/가능 여부

Agent에게 노출 금지:

- OAuth access token / refresh token
- fintech_use_num
- user_seq_no
- 개인실명번호
- 원 계좌번호, 증권번호, 카드번호, 카드 식별자
- 계좌해지, 잔고이전, 입금/출금이체, 대출이동 실행 권한

## Tool Output 원칙

- tool output은 판단에 필요한 요약과 일부 근거만 포함합니다.
- provider 원문 응답 전체를 LLM context에 넣지 않습니다.
- tool output의 ID는 내부 ID입니다. provider 원문 식별자를 그대로 쓰지 않습니다.
- 실행으로 이어질 수 있는 값은 `ActionProposal`에 필요한 범위까지만 남기고, 실제 실행 입력은 Executor가 서버 내부에서 다시 조회합니다.
- 동일 고객의 건강, 보험, 현금흐름, 자산방어, 투자전략, 장기 생애설계 판단은 별도 agent가 아니라 같은 `AssessNeed`/`GeneratePlan` 흐름 안에서 종합합니다.

## Read Tools

### get_account_balances

Provider docs:

- `account_balance.md`
- `account_info_integrated_list.md`

Agent output:

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

Use:

- 의료비 감내 범위
- 현금흐름 압박
- 비상자금 부족

NeedAssessment:

- `cashflow_need`
- `asset_defense_need`
- `investment_adjust_need`

### get_account_transactions

Provider docs:

- `account_transaction_list.md`

Agent output:

```json
{
  "transactions": [
    {
      "transacted_at": "2019-09-10T11:30:00",
      "direction": "out",
      "description": "병원",
      "amount_krw": 450000,
      "category_hint": "medical"
    }
  ],
  "spending_summary": {
    "monthly_outflow_krw": 2500000,
    "medical_spending_krw": 450000,
    "fixed_cost_krw": 1200000
  }
}
```

Use:

- 의료비 지출 감지
- 고정비/소비 급증 감지
- 현금흐름 평가

NeedAssessment:

- `medical_cost_need`
- `cashflow_need`
- `asset_defense_need`

### get_card_bills

Provider docs:

- `card_list.md`
- `card_bill_basic.md`
- `card_bill_detail.md`

Agent output:

```json
{
  "bills": [
    {
      "card_name": "카드상품명",
      "charge_month": "2019-12",
      "charge_krw": 456000,
      "settlement_date": "2019-12-26",
      "medical_charge_krw": 30000
    }
  ],
  "upcoming_card_payment_krw": 456000
}
```

Use:

- 다음 달 현금흐름
- 의료비/고정비 카드 청구

NeedAssessment:

- `medical_cost_need`
- `cashflow_need`

### get_insurance_summary

Provider docs:

- `insurance_list.md`
- `insurance_payment.md`

Agent output:

```json
{
  "policies": [
    {
      "policy_id": "policy_1",
      "product_name": "오픈암보험",
      "insurance_type": "health",
      "status": "active",
      "premium_krw": 1000000,
      "pay_cycle": "monthly",
      "expires_on": "2052-02-02"
    }
  ],
  "gaps_hint": "심혈관 특약 없음",
  "monthly_premium_krw": 1000000
}
```

Use:

- 보험 보장 점검
- 보험료 현금흐름
- 의료비 리스크 흡수 가능성

NeedAssessment:

- `insurance_need`
- `cashflow_need`
- `asset_defense_need`

### get_loan_summary

Provider docs:

- `loan_lease_list.md`
- `loan_lease_basic.md`

Agent output:

```json
{
  "loans": [
    {
      "loan_id": "loan_1",
      "product_name": "오픈대출",
      "loan_type": "jeonse_collateral",
      "status": "active",
      "repayment_day": 5,
      "next_repayment_on": "2022-12-05",
      "recent_repayment_krw": 450000
    }
  ],
  "upcoming_repayment_krw": 450000
}
```

Use:

- 현금흐름 압박
- 자산방어 필요성
- 장기 생애설계 영향

NeedAssessment:

- `cashflow_need`
- `asset_defense_need`
- `life_plan_need`

### get_loan_switch_precheck

Provider docs:

- `personal_credit_loan.md`
- `mortgage_loan.md`
- `jeonse_loan.md`

Agent output:

```json
{
  "loan_id": "loan_1",
  "repayment_available": true,
  "prepayment_penalty_krw": 0,
  "note": "사전조회 mock 결과입니다. 실제 대환 실행은 고객 승인 후 Executor 영역입니다."
}
```

Use:

- 대출이동 가능성 참고
- 상환 수수료에 따른 현금흐름 영향

NeedAssessment:

- `cashflow_need`
- `asset_defense_need`
- `investment_adjust_need`

## Executor Only

아래 API는 agent read tool로 노출하지 않습니다.

| Provider doc | Action | Reason |
|---|---|---|
| `account_info_close_transfer.md` | 계좌해지·잔고이전 | 외부 효과, 고객 승인 필요 |
| 오픈뱅킹 입금이체/출금이체 | 이체 실행 | 외부 자금 이동, 고객 승인 및 Executor 필요 |
| 대출이동 실행 API | 대환 실행 | 금융 계약 변경, 고객 승인 및 Executor 필요 |
