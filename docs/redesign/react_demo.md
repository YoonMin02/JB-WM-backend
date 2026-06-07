# React 데모 앱

`webapp/`은 운영용 최종 고객 화면이 아니라, 이번 재설계의 흐름을 로컬에서 확인하는
테스트 하네스다. 목표는 예쁘게 마케팅 페이지를 만드는 것이 아니라, 고객이 실제로
무슨 데이터를 받았고 에이전트가 무엇을 판단했으며 어떤 일은 승인 후 처리되는지
확인할 수 있게 하는 것이다.

## 사용자가 확인해야 하는 흐름

1. 고객을 선택한다.
2. 금융 이벤트를 수동으로 트리거한다.
3. 화면에 "일하는 중" 상태가 보인다.
4. 완료 후 에이전트 설명과 제안이 나온다.
5. 외부효과가 있는 제안은 승인/거절/수정할 수 있다.
6. 승인 후에는 처리 결과와 "어떻게 확인했는지"가 사용자 언어로 보인다.
7. 다른 고객 정보 조회 시도는 보안 안내로 표시되고, 이후 정상 요청은 계속 동작한다.

## 개발자 화면

`http://127.0.0.1:5173/dev`는 고객용 화면이 아니다. 여기서는 상태 흐름을 확인한다.

- LangGraph 현재 stage
- thread/session/customer scope
- `DataSnapshot`과 context hash
- agent input payload
- agent output JSON
- Codex CLI mode/model/reasoning effort/duration/input bytes/output bytes
- proposal 목록
- approval decision
- execution 결과
- verifier/debug snapshot

고객이 누르는 승인/거절 버튼은 `/dev`가 아니라 기본 화면에 있어야 한다. `/dev`는
상태 변화를 관찰하는 화면이다.

## 사용하는 API

```text
GET  /customers
POST /customers/{customer_id}/workflow-sessions
GET  /workflow-sessions/{thread_id}
GET  /workflow-sessions/{thread_id}/debug
POST /workflow-sessions/{thread_id}/events
POST /workflow-sessions/{thread_id}/events/stream
POST /workflow-sessions/{thread_id}/messages
POST /workflow-sessions/{thread_id}/messages/stream
POST /workflow-sessions/{thread_id}/decisions
POST /workflow-sessions/{thread_id}/decisions/stream
```

현재 프로젝트 목적은 실시간 스트리밍 자체가 아니다. 그래서 기본 사용자 경험은
"작업 중 표시 -> 완료 후 제안/결과 표시"를 중심으로 둔다. SSE endpoint는 개발
확인이나 나중의 진행 표시 개선을 위해 남겨둔다.

## 실행

백엔드 stub 모드:

```bash
DATABASE_URL=sqlite:///./storage/jbwm_demo.db \
AGENT_JOB_MODE=local_stub \
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

백엔드 실제 Codex CLI 모드:

```bash
DATABASE_URL=sqlite:///./storage/jbwm_demo.db \
AGENT_JOB_MODE=codex_cli \
AGENT_JOB_CODEX_MODEL=gpt-5.4-mini \
AGENT_JOB_CODEX_REASONING_EFFORT=low \
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

프론트:

```bash
cd webapp
npm install
npm run dev
```

기본 화면은 `http://127.0.0.1:5173`, 개발자 화면은
`http://127.0.0.1:5173/dev`다.

## 구현 위치

```text
webapp/src/main.jsx
  React 화면, API 호출, 고객용/개발자용 view 전환

webapp/src/styles.css
  화면 스타일

webapp/src/pwa.js
  service worker 등록

webapp/public/manifest.webmanifest
webapp/public/sw.js
  PWA와 향후 Web Push 알림을 위한 기본 파일
```

프론트 문구는 개발자 용어가 아니라 사용자 언어를 우선한다. 예를 들어
`PolicyCheck`, `ActionExecution`, `DataSnapshot` 같은 말은 고객 화면에 직접
보이지 않아야 한다.
