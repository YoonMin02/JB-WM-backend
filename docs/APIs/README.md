# External API Specs

이 폴더는 실제 외부 API를 바로 연결하기 위한 구현 코드가 아니라, **mock 데이터와
adapter contract를 만들기 위한 request/response 형식 참고 문서**입니다.

MVP에서는 외부망 호출을 하지 않습니다. 각 원문 API 명세의 body 항목을 기준으로
내부 DTO를 만들고, seed/mock adapter가 같은 형태의 값을 반환하도록 맞춥니다.

## 원칙

- 원문 API 스펙은 provider별 계약을 이해하기 위한 참고 자료로 보존합니다.
- 백엔드 도메인 로직은 provider 원문 필드에 직접 의존하지 않고, 내부 정규화 모델에 의존합니다.
- Codex/agent에는 원문 응답을 그대로 주지 않습니다. 백엔드 read tool이 정규화하고 민감 필드를 제거한 결과만 제공합니다.
- 실행 API는 agent tool에 노출하지 않습니다. 실행은 고객 승인 후 Executor만 수행합니다.
- OAuth token, fintech_use_num, user_seq_no, 계좌번호, 증권번호, 카드 식별자, 개인실명번호는 agent에 직접 노출하지 않습니다.

## 파일 목록

| 파일 | Provider 영역 | 용도 | MVP 사용 |
|---|---|---|---|
| `AUTH_AND_CONSENT.md` | 공통 | OAuth/동의/토큰 경계 | mock 전제 |
| `account_balance.md` | 오픈뱅킹 | 계좌 잔액/출금가능금액 조회 | 현금흐름, 유동성 |
| `account_transaction_list.md` | 오픈뱅킹 | 계좌 거래내역 조회 | 소비/의료비/고정비 탐지 |
| `account_info_integrated_list.md` | 어카운트인포 | 계좌통합조회 | 흩어진 유동성 파악 |
| `account_info_close_transfer.md` | 어카운트인포 | 계좌해지·잔고이전 | Executor only, MVP 미연결 |
| `card_list.md` | 오픈뱅킹 | 카드 목록 조회 | 카드 청구 연결 키 |
| `card_issue.md` | 오픈뱅킹 | 카드 기본정보 조회 | 카드 상태/상품 |
| `card_bill_basic.md` | 오픈뱅킹 | 카드 청구 기본정보 | 다음 달 현금흐름 |
| `card_bill_detail.md` | 오픈뱅킹 | 카드 청구 상세정보 | 지출 항목 분석 |
| `insurance_list.md` | 오픈뱅킹 | 보험 목록 조회 | 보장 점검 |
| `insurance_payment.md` | 오픈뱅킹 | 보험 납입정보 조회 | 보험료 현금흐름 |
| `loan_lease_list.md` | 오픈뱅킹 | 대출·리스 목록 조회 | 부채 현황 |
| `loan_lease_basic.md` | 오픈뱅킹 | 대출·리스 기본/거래정보 | 상환일·상환방식 |
| `personal_credit_loan.md` | 대출이동 | 개인신용대출 상환정보 사전조회 | 대환 가능성 참고 |
| `mortgage_loan.md` | 대출이동 | 주택담보대출 상환정보 사전조회 | 대환 가능성 참고 |
| `jeonse_loan.md` | 대출이동 | 전세대출 상환정보 사전조회 | 대환 가능성 참고 |

## 함께 볼 문서

- [`INTERNAL_ADAPTER_CONTRACTS.md`](INTERNAL_ADAPTER_CONTRACTS.md) — provider 원문을 내부 DTO로 정규화하는 계약
- [`AGENT_TOOL_MAPPING.md`](AGENT_TOOL_MAPPING.md) — agent에게 노출되는 read tool과 숨겨야 할 필드
- [`../06_TOOL_CONTRACTS.md`](../06_TOOL_CONTRACTS.md) — JB WM agent tool 정책
- [`../10_SECURITY_PRIVACY.md`](../10_SECURITY_PRIVACY.md) — capability / 개인정보 경계

## 구현 순서

1. 이 폴더의 원문 명세에서 request/response 필드 shape를 확인합니다.
2. `INTERNAL_ADAPTER_CONTRACTS.md`의 내부 DTO에 맞춰 mock adapter 응답을 만듭니다.
3. `AGENT_TOOL_MAPPING.md`의 노출 정책에 따라 agent read tool 결과를 구성합니다.
4. 실제 외부 API 연결은 adapter 내부에서만 추가합니다. 도메인/FSM/Policy/Executor는 provider 원문 필드를 직접 보지 않습니다.
