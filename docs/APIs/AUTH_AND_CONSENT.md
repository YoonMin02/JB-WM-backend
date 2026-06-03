# Auth and Consent

오픈뱅킹/어카운트인포 계열 API는 OAuth 2.0 기반 인증·권한 부여를 전제로 합니다.
이 문서는 실제 인증 구현서가 아니라, JB WM 백엔드가 외부 금융 API를 다룰 때 지켜야 할
계약을 정리합니다.

## OAuth 역할

| OAuth 용어 | JB WM 관점 |
|---|---|
| Resource Owner | 고객 |
| Client | JB WM 백엔드/이용기관 애플리케이션 |
| Authorization Server | 오픈뱅킹 인증 서버 |
| Resource Server | 오픈뱅킹/어카운트인포 API 서버 |

MVP에서는 실제 OAuth flow를 구현하지 않고, 동의/토큰/핀테크이용번호가 이미 존재한다고
가정한 mock adapter를 사용합니다.

## 3-legged User Auth

고객 개인 데이터 조회는 고객 동의가 필요합니다.

```text
고객 동의
→ authorization code
→ access_token
→ 계좌등록
→ fintech_use_num 발급
→ 잔액/거래내역 등 조회
```

`access_token`, `refresh_token`, `fintech_use_num`은 provider 호출을 위한 credential 또는
외부 식별자입니다. Codex/agent에 직접 노출하지 않습니다.

## 2-legged Client Auth

일부 API는 사용자 개입 없이 client credentials로 호출할 수 있습니다. 예를 들어 계좌실명조회
같은 API가 여기에 속할 수 있습니다. JB WM MVP에서는 고객 통합 자산/건강 판단에 필요한
읽기 데이터가 중심이므로, 2-legged API는 우선순위가 낮습니다.

## Internal Storage Policy

MVP mock에서는 아래 값을 실제로 저장하지 않아도 됩니다. 실서비스 구현 시에는 암호화 저장 또는
별도 secret/token vault가 필요합니다.

| 값 | 저장 위치 | Agent 노출 |
|---|---|---|
| `access_token` | token vault / encrypted store | 금지 |
| `refresh_token` | token vault / encrypted store | 금지 |
| `fintech_use_num` | external account mapping | 금지 |
| `user_seq_no` | external user mapping | 금지 |
| `bank_tran_id` | adapter request log | 금지 |
| 원 계좌번호/증권번호/카드번호 | 가능하면 미저장, 필요 시 암호화 | 금지 |

## Backend Boundary

도메인/FSM/Policy/Executor는 OAuth 세부사항을 알지 않습니다.

```text
Domain code
  → Internal adapter contract
    → Provider adapter
      → OAuth token / fintech_use_num / raw API
```

실제 외부 API 연결 시에도 바뀌는 범위는 provider adapter 내부로 제한합니다.

