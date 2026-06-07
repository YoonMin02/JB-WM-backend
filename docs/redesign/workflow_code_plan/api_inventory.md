# workflow API 목록과 실행 가능성 판단

이 문서는 `DataRefresh`, `SignalDetect`, `ExecuteAction`, `VerifyResult`를 구현할 때
어떤 API 문서를 기준으로 삼을지 정리한다.

확인일: 2026-06-07

구분은 세 가지다.

1. `docs/APIs`에 이미 있는 로컬 API body 문서
2. 공개 금융결제원/KFTC Open API 자료를 보고 실행 가능성을 판단한 후보
3. 공개 실행 API가 확인되지 않아 mock 또는 담당자 task로 둬야 하는 영역

`docs/APIs`가 현재 구현의 1차 기준이다. 공개 링크는 "실제 실행 경로가 가능한가"를
판단하기 위한 참고 자료로만 쓴다.

## 로컬 API 문서 기준

| 도메인 | 로컬 문서 | workflow 사용처 | 현재 판단 |
|---|---|---|---|
| 계좌 잔액 | `account_balance.md` | `DataRefresh`, 유동성/현금 여유 signal | 읽기 |
| 계좌 거래 | `account_transaction_list.md` | 지출, 현금흐름, 의료비/생활비 signal | 읽기 |
| AccountInfo 통합 조회 | `account_info_integrated_list.md` | 흩어진 계좌 목록 확인 | 읽기 |
| AccountInfo 해지/잔고이전 | `account_info_close_transfer.md` | 승인 후 실행 후보 | MVP는 mock, 계약 후 executor |
| 카드 목록/기본/청구 상세 | `card_list.md`, `card_issue.md`, `card_bill_basic.md`, `card_bill_detail.md` | 카드 결제 예정액, 지출 급증 signal | 읽기 |
| 보험 목록/납입 | `insurance_list.md`, `insurance_payment.md` | 보험료 부담, 보장 점검 signal | 읽기 |
| 대출/리스 목록/기본 | `loan_lease_list.md`, `loan_lease_basic.md` | 상환 압박 signal | 읽기 |
| 대출 이동 사전조회 | `personal_credit_loan.md`, `mortgage_loan.md`, `jeonse_loan.md` | 대환 가능성 근거 | 사전조회/담당자 task |
| 투자/JB자산운용 | 로컬 문서 없음 | 포트폴리오 손실, 고위험 비중 signal | mock 또는 private contract 필요 |

## 공개 API 조사 결론

### 금융결제원 Open Banking

참고:

- `https://openapi.kftc.or.kr/service/openBanking`
- `https://developers.kftc.or.kr/dev/openapi/open-banking/deposit`
- `https://developers.kftc.or.kr/dev/openapi/open-banking/balance`

결론:

- 계좌 잔액/거래 등 읽기 API는 `DataRefresh`의 실제 후보가 될 수 있다.
- 이체류 API도 공개 서비스 설명에 존재하지만, agent가 직접 호출하면 안 된다.
- 실제 이체 실행은 반드시 `PolicyCheck -> ApprovalInterrupt -> ExecuteAction` 뒤에 둔다.
- MVP에서는 계약, 동의, 키, 한도, 거래 검증 흐름이 없으므로 mock 또는 disabled로 둔다.

### 금융결제원 AccountInfo

참고:

- `https://openapi.kftc.or.kr/service/accountInfo`
- `https://developers.kftc.or.kr/dev/openapi/account-info`

결론:

- 계좌 통합 조회는 데이터 수집 후보가 된다.
- 로컬 `account_info_close_transfer.md`에는 해지/잔고이전 후보 흐름이 있다.
- 후보 순서는 `eligibility -> recipient -> status -> transfer -> result`다.
- 이 영역은 repo 안에서 가장 구체적인 "승인 후 실행" 후보지만, 실제 계약 전에는 mock으로 둔다.

### 금융결제원 대출 이동

참고:

- `https://openapi.kftc.or.kr/service/loan`

결론:

- 공개 서비스 설명은 기존 대출 조회와 더 나은 상품 이동 지원에 가깝다.
- 로컬 문서는 대출 이동 사전조회/추천 근거 형태다.
- 현재 기획에서 "대환을 실제 실행했다"고 표현하면 안 된다.
- 가능한 처리는 사전조회 결과 기록, 상담/담당자 task 생성, mock request다.

### MyData relay

참고:

- `https://openapi.kftc.or.kr/service/mydata`

결론:

- 향후 더 풍부한 은행/카드/보험/투자 데이터를 읽는 후보가 될 수 있다.
- 이 MVP의 자동 실행 경로는 아니다.

### JB자산운용

조사한 공개 경로:

- `https://www.jbfg.com/ko/about/network.do`
- `JB자산운용 API`
- `JB자산운용 오픈API`
- `JB Asset Management API`

결론:

- 공개 검색으로는 JB자산운용의 매매/리밸런싱/포트폴리오 실행용 developer API를 찾지 못했다.
- 이것은 private API가 없다는 증명이 아니라, 이 repo가 공개 자료만으로 실제 실행을 계획할 수 없다는 뜻이다.
- 따라서 `rebalance_portfolio`는 private contract가 생기기 전까지 다음 중 하나로 처리한다.
  - 로컬 데모 포트폴리오 mock 반영
  - 담당자/PB 검토 task 생성
  - 리포트 생성만 수행
  - 나중에 signed contract 기반 `jbam` adapter + verifier 추가

## action별 실행 판단

| Action kind | 실제 API 후보 | MVP 처리 방식 | 확인 방식 |
|---|---|---|---|
| `report` | 내부 DB/file | 실제 내부 처리 | report row/hash 재조회 |
| `notify` | 내부 알림/PB task API | 내부 처리 또는 mock | notification/task status 재조회 |
| `cashflow_plan` | 외부 API 불필요 | 내부 plan record 생성 | saved plan 재조회 |
| `review_insurance` | 보험 읽기 API 근거 | mock review/report | review artifact 재조회 |
| `rebalance_portfolio` | 공개 JB 실행 API 없음 | mock 또는 advisor task | holdings 재조회, 비중 재계산 |
| `close_dormant_account` | AccountInfo 해지/잔고이전 후보 | 계약 전 mock | result API 또는 계좌목록 재조회 |
| `transfer_cash` | Open Banking 이체 후보 | 계약 전 mock/disabled | 이체 결과 + 잔액/거래 재조회 |
| `loan_switch_request` | 대출 이동 사전조회 후보 | mock/advisor task | precheck result + task status |

## 실행 API가 없을 때의 규칙

실제 외부 실행 API가 없거나 계약되지 않았다면 executor는 provider 호출을 흉내 내면
안 된다. 대신 다음 중 하나를 기록한다.

- `mock_applied`: 데모 DB에만 반영했고 화면에 mock임을 표시
- `advisor_task_created`: 담당자나 PB가 이어서 검토해야 함
- `report_created`: 실행이 아니라 추천/리포트만 생성
- `external_unavailable`: 현재 환경에서는 실행할 수 없음

프론트도 같은 구분을 사용자 언어로 보여줘야 한다. 예를 들어 "처리 완료"만 쓰면
실제 금융회사 주문이 끝난 것처럼 오해할 수 있다.

## 구현 시 의미

`ActionProposal.kind`는 agent가 말할 수 있다는 이유만으로 늘리지 않는다. 각 action은
반드시 아래 중 하나를 가져야 한다.

- 내부 handler와 verifier
- 계약된 provider handler와 verifier
- mock handler와 mock임을 밝히는 UI copy
- 실행 불가를 기록하는 `external_unavailable` 처리

이 규칙을 지키면 "계획만 만든 일"을 "실행 완료"로 보여주는 문제를 막을 수 있다.
