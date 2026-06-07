# workflow 코드 구현 계획

이 폴더는 화면에 보이는 상태 문구를 실제 코드, API 계약, mock provider payload,
executor, verifier로 어떻게 구현할지 설명한다.

특히 다음 네 단계가 이전 기획에서 너무 추상적이었다.

| 화면 문구 | LangGraph node | 책임 주체 | 상세 문서 |
|---|---|---|---|
| 1. 데이터 받음 | `DataRefresh` | 코드 + adapter | [`data_refresh_signal_detection.md`](data_refresh_signal_detection.md) |
| 2. 이벤트 파악 | `SignalDetect`, `SignalGate` | 코드 + detector registry | [`data_refresh_signal_detection.md`](data_refresh_signal_detection.md) |
| 9. 승인 후 실행 | `ExecuteAction` | policy + executor | [`execution_verification.md`](execution_verification.md) |
| 10. 처리 확인 | `VerifyResult` | verifier | [`execution_verification.md`](execution_verification.md) |

함께 읽을 문서:

- [`api_inventory.md`](api_inventory.md): 어떤 API가 데이터 수집/실행 후보가 되는지 정리
- [`../workflow.md`](../workflow.md): 전체 LangGraph 순서
- [`../../APIs/README.md`](../../APIs/README.md): 로컬에 정리된 제공 API body 문서

## 설계 관점

이 workflow는 "에이전트가 말했으니 화면에서 일이 끝난 것처럼 보여준다"가 아니다.
각 단계는 실제 코드 책임을 가진다.

```text
provider/mock API payload
  -> scoped adapter
  -> normalized internal DTO
  -> DataSnapshot
  -> deterministic SignalEnvelope
  -> sandboxed agent assessment/plan
  -> policy approval gate
  -> scoped executor
  -> verifier가 결과 재확인
```

MVP에서는 provider 호출이 mock일 수 있다. 하지만 mock도 provider boundary처럼
보여야 한다.

- provider 모양의 request/response body가 있어야 한다.
- adapter가 금액, 날짜, 코드 값을 내부 DTO로 정규화해야 한다.
- 민감한 provider id는 서버 내부에만 남아야 한다.
- agent는 redacted context만 받아야 한다.
- executor는 저장되고 승인된 proposal만 실행해야 한다.
- verifier는 handler 응답을 믿지 말고 post-condition을 다시 확인해야 한다.

## 현재 코드 상태

현재 브랜치에는 LangGraph 흐름의 뼈대가 있다.

- `app/workflows/nodes.py`
- `app/adapters/mock/context.py`
- `app/signals/detectors.py`
- `app/executor/handlers.py`

하지만 아직 구현은 얇다.

- `DataRefresh`는 mock DB 테이블에서 하나의 redacted snapshot을 만든다.
- `SignalDetect`는 rule registry가 아니라 작은 detector 함수다.
- `ExecuteAction`은 mock/internal handler를 직접 호출한다.
- `VerifyResult`는 별도 verifier로 분리되어 있지 않다.

따라서 다음 코드 개편에서는 이 폴더의 계획을 기준으로 adapter, signal detector,
executor, verifier를 분리한다.

## 구현할 때의 우선순위

1. `docs/APIs`에 있는 계좌/카드/보험/대출 body를 mock payload로 먼저 맞춘다.
2. 투자/JB자산운용 쪽은 공개 실행 API가 확인되지 않았으므로 mock 또는 담당자 task로 둔다.
3. agent가 이벤트 존재를 invent하지 않도록 signal detector를 코드화한다.
4. 승인 후 실행은 `proposal_id` 기반으로만 처리한다.
5. 처리 확인은 execution handler와 분리된 verifier로 만든다.
6. `/dev`에서 input, output, decision, execution, verification을 모두 볼 수 있게 한다.
