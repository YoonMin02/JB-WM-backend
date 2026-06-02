# Internal Adapter Contracts

외부 API 응답은 이 문서의 내부 DTO로 정규화합니다. MVP에서는 실제 외부 호출 없이
seed/mock 데이터가 같은 shape를 반환하면 됩니다.

## 공통 규칙

- provider 원문 금액 문자열은 `int` KRW로 변환합니다.
- provider 원문 날짜(`YYYYMMDD`, `YYYYMM`, timestamp)는 API 경계에서 ISO 문자열로 변환합니다.
- 원문 식별자는 내부 `external_ref` 또는 adapter 내부 저장소에만 둡니다.
- agent-facing DTO에는 token, fintech_use_num, user_seq_no, 원 계좌번호, 개인실명번호를 포함하지 않습니다.
- 원문 응답 코드는 adapter log/audit에 저장하고, 도메인에는 정규화된 success/error만 전달합니다.

## AccountBalance

원문: `account_balance.md`

```json
{
  "account_id": "internal-account-id",
  "bank_name": "오픈은행",
  "product_name": "알뜰살뜰적금",
  "account_type": "deposit",
  "balance_krw": 1000000,
  "available_krw": 1000000,
  "issued_on": "2019-01-10",
  "matures_on": "2020-01-09",
  "last_transaction_on": "2019-10-10"
}
```

| Provider field | Internal field | Note |
|---|---|---|
| `bank_name` | `bank_name` | 노출 가능 |
| `product_name` | `product_name` | 노출 가능 |
| `account_type` | `account_type` | 코드 변환 |
| `balance_amt` | `balance_krw` | int 변환 |
| `available_amt` | `available_krw` | int 변환 |
| `account_issue_date` | `issued_on` | 날짜 변환 |
| `maturity_date` | `matures_on` | 날짜 변환 |
| `last_tran_date` | `last_transaction_on` | 날짜 변환 |
| `fintech_use_num` | hidden | agent 노출 금지 |

## AccountTransaction

원문: `account_transaction_list.md`

```json
{
  "account_id": "internal-account-id",
  "bank_name": "오픈은행",
  "balance_krw": 1000000,
  "transactions": [
    {
      "transacted_at": "2019-09-10T11:30:00",
      "direction": "in",
      "transaction_type": "cash",
      "description": "통장인자내용",
      "amount_krw": 450000,
      "after_balance_krw": -1000000,
      "category_hint": "uncategorized"
    }
  ],
  "next_page": {
    "has_next": true,
    "cursor": "1T201806171"
  }
}
```

| Provider field | Internal field | Note |
|---|---|---|
| `inout_type` | `direction` | 입금=`in`, 출금=`out` |
| `tran_date` + `tran_time` | `transacted_at` | ISO datetime |
| `tran_type` | `transaction_type` | 코드/문자 정규화 |
| `print_content` / `printed_content` | `description` | 원문 표기 차이 흡수 |
| `tran_amt` | `amount_krw` | int 변환 |
| `after_balance_amt` | `after_balance_krw` | int 변환 |
| `befor_inquiry_trace_info` | `next_page.cursor` | agent 직접 노출 금지 가능 |

## CardBill

원문: `card_bill_basic.md`, `card_bill_detail.md`

```json
{
  "card_id": "internal-card-id",
  "card_name": "카드상품명",
  "charge_month": "2019-12",
  "charge_krw": 456000,
  "settlement_date": "2019-12-26",
  "credit_check_type": "credit",
  "details": [
    {
      "used_on": "2019-11-30",
      "merchant_name": "가맹점명",
      "amount_krw": 30000,
      "category_hint": "medical"
    }
  ]
}
```

## InsurancePolicySummary

원문: `insurance_list.md`, `insurance_payment.md`

```json
{
  "policy_id": "internal-policy-id",
  "product_name": "오픈암보험",
  "insurance_type": "health",
  "status": "active",
  "issued_on": "2002-02-02",
  "expires_on": "2052-02-02",
  "payment": {
    "pay_cycle": "monthly",
    "pay_day": 1,
    "pay_until": "2055-12-31",
    "premium_krw": 1000000,
    "payment_method_masked": "000-1230000-***",
    "auto_pay": false
  }
}
```

| Provider field | Internal field | Note |
|---|---|---|
| `insu_num` | hidden/internal ref | agent 노출 금지 |
| `prod_name` | `product_name` | 노출 가능 |
| `insu_type` | `insurance_type` | 코드 변환 |
| `insu_status` | `status` | `02` active 등 |
| `pay_amt` | `payment.premium_krw` | int 변환 |
| `pay_account_num` | hidden | agent 노출 금지 |
| `pay_account_num_masked` | `payment.payment_method_masked` | 제한적 노출 가능 |

## LoanSummary

원문: `loan_lease_list.md`, `loan_lease_basic.md`

```json
{
  "loan_id": "internal-loan-id",
  "product_name": "오픈대출",
  "loan_type": "jeonse_collateral",
  "status": "active",
  "repayment_day": 5,
  "repayment_method": "bullet",
  "next_repayment_on": "2022-12-05",
  "recent_transactions": [
    {
      "transacted_at": "2019-09-10T11:30:00",
      "transaction_type": "execution",
      "amount_krw": -450000
    }
  ]
}
```

## LoanSwitchPrecheck

원문: `personal_credit_loan.md`, `mortgage_loan.md`, `jeonse_loan.md`

```json
{
  "loan_id": "internal-loan-id",
  "repayment_available": true,
  "denial_code": null,
  "prepayment_penalty_krw": 0,
  "interest_rate_type": "fixed",
  "variation_cycle_months": null,
  "fixed_rate_apply_months": null
}
```

대출이동 관련 API는 MVP에서 **실행하지 않고 조회/사전평가 mock**으로만 사용합니다.
대환 신청, 계좌해지, 잔고이전은 Executor only 영역입니다.

