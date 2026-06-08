# 웹앱 알림 설계

이 문서는 JB-WM이 나중에 실제 웹앱 알림을 붙일 때의 구조를 정한다.
현재 데모는 화면을 켜 둔 상태에서 SSE로 진행 상태를 보여준다. 실제 알림은
그와 다른 책임을 가진다. 사용자가 웹앱을 닫았거나 휴대폰 홈 화면에 추가한
PWA 상태여도, 승인 요청이나 처리 결과처럼 놓치면 안 되는 일을 알려주는
비동기 전달 채널이다.

## 가능 여부

모바일 PWA 알림은 가능하다.

- Android/Chrome 계열은 Service Worker, Push API, Notifications API 조합으로
  웹 푸시를 받을 수 있다.
- iOS/iPadOS는 16.4 이상에서 홈 화면에 추가된 웹앱이 Web Push를 받을 수 있다.
  사용자가 웹앱 안의 버튼처럼 명확한 동작을 한 뒤 알림 권한을 허용해야 한다.
- macOS Safari도 Web Push를 지원한다.

따라서 JB-WM은 "PWA 설치 + 알림 권한 + push subscription 저장 + 서버 전송"의
표준 Web Push 구조로 설계하면 된다.

참고:

- Apple Developer: `https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers`
- WebKit: `https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/`
- MDN Push API: `https://developer.mozilla.org/en-US/docs/Web/API/Push_API`

## SSE와 Push의 차이

SSE는 현재 열린 화면에 진행 상태를 보여주는 통로다.

```text
사용자가 화면을 열어 둠
-> 이벤트 트리거
-> LangGraph stage 변화
-> 브라우저 화면에 "일하는 중" 표시
-> 완료 후 제안/처리 결과 표시
```

Push는 화면이 닫혀 있어도 사용자를 다시 부르는 통로다.

```text
워크플로우 결과 발생
-> 알림 intent 생성
-> 사용자별 push subscription 조회
-> Web Push 전송
-> Service Worker가 notification 표시
-> 사용자가 누르면 해당 workflow 화면으로 이동
```

둘은 서로 대체하지 않는다. 같은 도메인 이벤트에서 둘 다 발생할 수 있지만,
SSE는 프론트 진행 표시, Push는 재참여 알림이다.

## 알림을 보낼 수 있는 순간

알림은 에이전트가 직접 보내면 안 된다. 알림은 LangGraph/Executor가 상태를
확정한 뒤 코드가 만든다.

권장 알림 지점:

1. `ApprovalInterrupt`
   - 고객 승인이 필요한 제안이 생김
   - 예: "승인이 필요한 제안이 있습니다."
2. `VerifyResult`
   - 승인한 일이 처리되고 확인까지 끝남
   - 예: "승인하신 일이 처리되었습니다."
3. `VerificationFailed`
   - 실행 결과가 기대와 다르거나 확인이 실패함
   - 예: "처리 결과 확인이 필요합니다."
4. `HumanReview`
   - 실제 외부 API가 없거나 담당자 검토가 필요함
   - 예: "담당자 검토 요청이 만들어졌습니다."

추천하지 않는 알림:

- 단순 분석 시작
- 내부 상태 전이마다 발송
- 고객이 아직 승인하지 않은 고위험 액션을 실행한 것처럼 보이는 문구
- 다른 고객이나 내부 id가 포함된 문구

## 서버 구조

실제 구현 시에는 다음 레이어를 둔다.

```text
app/notifications/
  schemas.py              # NotificationIntent, NotificationChannel
  subscriptions.py        # 사용자별 Web Push subscription 등록/해지
  service.py              # intent 생성, 중복 방지, 발송 예약
  webpush_sender.py       # VAPID 기반 Web Push 전송
  templates.py            # 사용자 언어의 짧은 알림 문구

app/workflows/nodes.py
  approval_interrupt      # 승인 필요 intent 생성
  verify_result           # 처리 완료/확인 실패 intent 생성

webapp/public/sw.js       # push 수신 및 notificationclick 처리
webapp/public/manifest.webmanifest
```

현재 브랜치는 프론트에 `manifest.webmanifest`와 `sw.js`를 추가해 PWA 껍데기를
준비했다. 아직 알림 권한 요청, 구독 저장 API, VAPID 키, 실제 전송 서버는
붙이지 않는다.

## 데이터 모델 초안

```text
PushSubscription
  id
  principal_id
  customer_id
  endpoint_hash
  endpoint_encrypted
  p256dh_encrypted
  auth_encrypted
  user_agent
  active
  created_at
  revoked_at

NotificationIntent
  id
  tenant_id
  customer_id
  graph_thread_id
  session_id
  proposal_id
  execution_id
  kind
  title
  body
  url
  status            # queued / sent / failed / skipped
  idempotency_key
  created_at
  sent_at
```

`endpoint`와 암호키는 capability URL 성격이 있으므로 평문으로 로그에 남기지
않는다. DB에 저장할 때도 암호화하거나 Supabase Vault 같은 서버 전용 비밀 저장소를
쓴다.

## 보안 규칙

- 알림 구독 등록은 인증된 사용자만 할 수 있다.
- 구독은 `principal_id + customer_id`에 묶는다.
- 고객 A의 workflow에서 고객 B의 subscription으로 알림을 보낼 수 없다.
- 알림 payload에는 내부 id, 계좌번호, provider token, raw API body를 넣지 않는다.
- 알림 URL은 서버가 소유한 `graph_thread_id`를 기준으로 만들고, 화면 진입 시
  다시 owner check를 한다.
- 알림 권한 요청은 사용자의 명확한 클릭 이후에만 한다.
- 실패한 전송은 재시도하되, 같은 `idempotency_key`는 중복 발송하지 않는다.

## Supabase/Netlify 방향

프론트는 Netlify에 배포할 수 있다. PWA 파일은 `webapp/public`에 두면 Vite 빌드
시 그대로 배포된다.

백엔드/DB를 Supabase로 옮길 때는 다음 구조가 적합하다.

- Supabase Postgres: subscription, notification intent, audit log 저장
- RLS: `customer_id`와 `principal_id` 기준으로 구독 조회 제한
- Edge Function 또는 private FastAPI worker: Web Push 전송
- Netlify 브라우저 코드: publishable key와 구독 등록 요청만 사용

Supabase service-role key, VAPID private key, provider token은 브라우저로
노출하지 않는다.

## 구현 순서

1. 프론트에 알림 설정 버튼 추가
2. Service Worker 준비 여부 확인
3. 사용자 클릭 후 `Notification.requestPermission()` 호출
4. `pushManager.subscribe()`로 subscription 생성
5. 서버에 subscription 등록
6. `ApprovalInterrupt`와 `VerifyResult`에서 `NotificationIntent` 생성
7. worker가 intent를 읽어 Web Push 전송
8. notification click으로 `/` 또는 해당 workflow 화면 이동
9. `/dev`에서 intent, subscription, send result를 확인

이 순서대로 가면 지금의 LangGraph 흐름을 깨지 않고, 나중에 실제 휴대폰 PWA
알림을 붙일 수 있다.
