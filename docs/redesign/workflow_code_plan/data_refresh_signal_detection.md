# 데이터 받음과 이벤트 파악 코드 계획

이 문서는 workflow의 1번과 2번 상태를 실제 코드로 어떻게 구현할지 설명한다.

1. `데이터 받음`: 계좌, 카드, 보험, 대출, 투자 데이터를 고객 scope 안에서 모은다.
2. `이벤트 파악`: 받은 데이터에서 무슨 일이 생겼는지 코드가 먼저 분류한다.

핵심은 에이전트가 "데이터를 찾고 이벤트를 invent"하지 않게 하는 것이다. 데이터 조회와
이벤트 존재 판단은 코드가 하고, agent는 그 다음에 제한된 context를 해석한다.

## 1. 데이터 받음

사용자 화면의 의미:

```text
고객님의 계좌, 카드, 보험, 대출, 투자 데이터를 다시 확인했습니다.
```

사용자에게는 다음처럼 말한다.

- 계좌 잔액과 최근 거래를 확인했어요.
- 이번 달 카드 결제 예정액을 확인했어요.
- 보험료와 보장 상태를 확인했어요.
- 대출 상환일과 월 상환 부담을 확인했어요.
- 투자 비중은 현재 데모 데이터 기준으로 확인했어요.

개발자 화면(`/dev`)에는 더 자세히 보여준다.

- provider/mock request body
- provider/mock response body
- normalized internal DTO
- redacted agent context
- `DataSnapshot.context_hash`

## 현재 코드

현재 구현:

- `app/workflows/nodes.py::data_refresh`
- `app/adapters/mock/context.py::build_agent_context_snapshot`
- `app.tools.data_tools.build_context`

현재는 mock DB 테이블에서 바로 redacted context를 만든다. 다음 단계에서는 provider/mock
adapter fan-out과 정규화 단계를 분리한다.

## 목표 모듈

```text
app/adapters/
  base.py
  registry.py
  mock/
    provider_payloads.py
    normalizers.py
  openbanking/
    client.py
    normalizers.py
  accountinfo/
    client.py
    normalizers.py
  loanmove/
    client.py
    normalizers.py
  portfolio/
    mock.py

app/data_refresh/
  service.py
  snapshot_builder.py
  redaction.py
  schemas.py
```

## 데이터 흐름

```text
principal
  -> CustomerScope 생성
  -> DataRefreshService.refresh(scope, reason)
  -> AdapterRegistry.fetch_all(scope, consent_scope)
  -> provider-shaped payload 저장
  -> normalized internal DTO 생성
  -> DataSnapshot 저장
  -> redacted context payload 생성
  -> agent job 입력으로 전달
```

중요한 규칙:

- `customer_id`는 UI body나 agent output에서 가져오지 않는다.
- `customer_id`는 인증된 principal과 server-owned thread/session에서 파생한다.
- raw provider id는 서버 저장소에만 남긴다.
- agent에게는 단일 고객의 redacted context만 전달한다.

## adapter 계약

각 adapter는 다음 envelope를 반환한다.

```json
{
  "provider": "openbanking",
  "capability": "account_balance",
  "mode": "mock",
  "fetched_at": "2026-06-07T09:00:00Z",
  "request_ref": "req_...",
  "raw_payload_ref": "raw_...",
  "normalized": {
    "accounts": [
      {
        "account_id": "acct_internal_1",
        "bank_name": "전북은행",
        "product_name": "입출금통장",
        "balance_krw": 1680000,
        "available_krw": 1540000
      }
    ]
  },
  "errors": []
}
```

`raw_payload_ref`는 서버 내부 저장소를 가리킨다. agent context에는 들어가지 않는다.

## provider 모양 mock body

mock도 실제 API body와 비슷해야 한다. 그래야 `/dev`에서 "무슨 데이터를 받았고
어떻게 정규화했는지" 설명할 수 있다.

계좌 잔액 예시:

```json
{
  "api_tran_id": "MOCK-TRX-001",
  "rsp_code": "A0000",
  "bank_name": "전북은행",
  "product_name": "입출금통장",
  "balance_amt": "1680000",
  "available_amt": "1540000",
  "fintech_use_num": "REDACTED_IN_AGENT_CONTEXT"
}
```

카드 청구 예시:

```json
{
  "card_name": "생활비 카드",
  "charge_month": "2026-06",
  "charge_amt": "1320000",
  "settlement_date": "2026-06-25",
  "bill_detail_list": [
    {
      "used_on": "2026-06-01",
      "merchant_name": "병원",
      "amount": "420000",
      "category_hint": "medical"
    }
  ]
}
```

투자 mock 예시:

```json
{
  "provider": "jbam_mock",
  "portfolio_name": "은퇴 준비 포트폴리오",
  "total_value_krw": 94000000,
  "high_risk_weight": 0.72,
  "holdings": [
    {
      "asset_label": "해외 주식형 펀드",
      "risk_grade": "high",
      "weight": 0.52
    },
    {
      "asset_label": "채권형 펀드",
      "risk_grade": "low",
      "weight": 0.28
    }
  ]
}
```

투자/JB자산운용은 공개 실행 API가 확인되지 않았으므로, 데이터 수집과 실행을 분리해
생각한다. 데이터 수집은 mock으로 가능하지만, 실제 리밸런싱 실행은 private contract가
생길 때까지 mock 또는 담당자 task로 둔다.

## 저장 계획

| 테이블 | 목적 |
|---|---|
| `provider_fetch_run` | 고객/session별 데이터 갱신 시도 1회 |
| `provider_payload` | 암호화된 raw body 또는 로컬 mock raw body |
| `normalized_financial_fact` | 선택적 read model/fact 저장 |
| 기존 domain tables | accounts, card bills, insurance policies, loans, portfolio holdings |
| `data_snapshot` | agent job에 들어간 redacted single-customer context |

MVP에서는 SQLite/Postgres JSON column에 raw mock payload를 둘 수 있다. 운영에서는 raw
payload 저장을 최소화하고, 저장한다면 암호화하거나 audit 요구가 있는 필드만 남긴다.

## DataRefresh 출력

`DataRefresh`는 UI가 바로 설명할 수 있는 요약을 반환해야 한다.

```json
{
  "stage": "DataRefresh",
  "data_snapshot_id": "snap_...",
  "context_hash": "sha256...",
  "received": [
    {
      "label": "계좌",
      "provider": "openbanking_mock",
      "status": "ok",
      "items": 3,
      "summary": "출금 가능한 현금 154만원"
    },
    {
      "label": "투자",
      "provider": "jbam_mock",
      "status": "ok",
      "items": 1,
      "summary": "고위험 투자 비중 72%"
    }
  ]
}
```

고객 화면은 이 값을 "받은 데이터" 설명으로 번역하고, `/dev`는 원문 payload와
정규화 결과를 함께 보여준다.

## 2. 이벤트 파악

사용자 화면의 의미:

```text
방금 받은 데이터에서 어떤 일이 생겼는지 확인했습니다.
```

예시:

- 다음 카드값과 대출 상환이 현금 여유를 압박하고 있어요.
- 고위험 투자 비중이 정한 기준보다 높아요.
- 보험료 부담은 큰데 보장 공백이 있을 수 있어요.

## 현재 코드

현재 구현:

- `app/signals/detectors.py::detect_signal`

지금은 작은 함수 하나가 이벤트를 분류한다. 다음 단계에서는 signal rule registry로
분리한다.

## 목표 모듈

```text
app/signals/
  schemas.py
  registry.py
  rules/
    cashflow.py
    card.py
    insurance.py
    loan.py
    portfolio.py
    routine.py
  dedupe.py
  severity.py
```

## detector 계약

입력:

```json
{
  "source": "api_refresh",
  "payload": {
    "trigger": "manual_demo_refresh"
  },
  "snapshot": {
    "accounts": "redacted normalized data",
    "card_bills": "...",
    "insurance": "...",
    "loans": "...",
    "portfolio": "..."
  }
}
```

출력:

```json
{
  "source": "detector",
  "kind": "portfolio_risk_overweight",
  "severity": "high",
  "idempotency_key": "portfolio_risk_overweight:customer_scope_hash:2026-06",
  "evidence": [
    {
      "label": "고위험 투자 비중",
      "value": "72%",
      "threshold": "60%"
    }
  ],
  "rationale": "고위험 투자 비중이 기준보다 높아 방어형 조정 제안이 필요합니다."
}
```

agent는 이 signal을 해석할 수 있지만, signal이 존재하는지 여부를 결정하지 않는다.

## rule 예시

| signal 종류 | 결정 조건 | 심각도 |
|---|---|---|
| `upcoming_card_payment_pressure` | 카드 결제 예정액 + 대출 상환액 > 가용 현금의 50% | mid/high |
| `liquidity_shortfall` | 가용 현금 < 30일 이내 예정 지출 | high |
| `spending_spike` | 이번 달 지출이 기준선보다 설정 비율 이상 증가 | mid |
| `medical_spending_spike` | 의료 카테고리 지출이 기준을 초과 | mid/high |
| `insurance_gap` | 필요한 보장 힌트가 있는데 matching coverage 없음 | mid |
| `premium_burden` | 월 보험료가 소득/현금흐름 기준보다 큼 | mid |
| `loan_repayment_pressure` | 상환일이 임박했고 현금 여유가 작음 | mid/high |
| `portfolio_risk_overweight` | 고위험 비중이 고객/정책 기준을 초과 | high |
| `stale_data` | 필수 adapter 실패 또는 데이터 오래됨 | low/mid |
| `routine_check` | 강한 이벤트 없음 | low |

## SignalGate 책임

`SignalGate`는 agent job을 띄울 가치가 있는지 판단한다.

- 동일 이벤트 중복 제거
- 쿨다운 window 적용
- 심각도 threshold 적용
- stale data fallback 처리
- 같은 signal이면 기존 workflow 재사용

권장 제약:

```text
unique(customer_id, kind, idempotency_key)
```

예를 들어 같은 카드 청구 이벤트를 두 번 클릭하면 새 agent job을 두 번 만들지 말고,
기존 workflow를 보여줘야 한다.

## 보안 경계

다른 고객 조회 시도를 한국어 이름이나 문장 파싱으로 막지 않는다. detector는
"내 보험 확인해줘"를 보험 signal로 분류할 수 있지만, 권한 판단은 하지 않는다.

권한 판단은 나중에 server-owned `customer_id`, `graph_thread_id`, `proposal_id`,
provider id를 scoped code가 resolve할 때 발생한다. 그래서 "박민수 DB 조회" 같은
문장을 앞단에서 이름으로 막지 않고, 실제 조회 대상 id가 현재 고객 scope 밖이면
그때 차단한다.

## 구현 전 최소 테스트

- `DataRefresh`는 scoped customer만 읽는다.
- redacted context에는 `customer_id`, raw 계좌번호, token, `fintech_use_num`,
  policy raw id, loan raw id가 없다.
- 각 local API mock body가 기대한 internal DTO로 정규화된다.
- demo customer fixture별로 detector가 기대 signal을 낸다.
- detector output에는 `/dev`에서 볼 수 있는 evidence가 있다.
- duplicate signal은 새 agent job을 만들지 않고 기존 workflow를 재사용한다.
- 다른 사람 이름이 들어간 사용자 문장은 text parsing으로 막지 않는다.
