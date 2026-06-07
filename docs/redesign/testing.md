# 테스트와 QA 기준

이 재설계에서 테스트가 지켜야 하는 것은 두 가지다.

1. 고객별 scope와 sandbox 경계가 깨지지 않는 것
2. 이벤트에서 제안, 승인, 실행, 확인까지의 업무 흐름이 유지되는 것

단순히 "LLM 답이 그럴듯하다"를 테스트하는 것이 아니다. 에이전트가 실수해도 코드가
막아야 하는 보안/상태 불변식을 테스트한다.

## 백엔드 전체 테스트

```bash
uv run pytest -q
```

## LangGraph 재설계 집중 테스트

```bash
uv run pytest app/tests/test_langgraph_workflow.py -q
```

현재 이 파일이 확인하는 내용:

- 다른 고객의 `graph_thread_id` 접근 거부
- `scope_hash` 변조 거부
- agent context redaction
- Codex CLI child process env sandbox
- Codex CLI가 정제 context를 stdin으로 받는지 확인
- 금융 신호에서 agent가 trigger domain을 우선하도록 하는 prompt 계약
- agent output의 내부 id/provider id 누출 거부
- LangGraph interrupt/resume 승인 흐름
- 여러 외부효과 proposal의 순차 승인
- reject/revise/잘못된 proposal id 처리
- `execute_scoped()`의 고객 scope, 승인, idempotency guard
- FastAPI workflow route의 auth와 pending message 처리

## 프론트 빌드

```bash
cd webapp
npm run build
```

프론트는 운영 배포 전 최소한 다음 흐름을 수동으로 확인한다.

1. 고객 선택
2. 투자 손실 또는 카드/대출 압박 이벤트 트리거
3. "일하는 중" 표시
4. 완료 후 받은 데이터 설명과 agent 제안 표시
5. 승인 대기 proposal 표시
6. 승인/거절/수정 동작
7. 처리 결과 자세히 보기
8. `/dev`에서 stage, agent input/output, execution 확인

## 실제 Codex CLI 스모크

`AGENT_JOB_MODE=codex_cli`는 모델 호출이 발생하므로 전체 테스트의 기본값으로 두지
않는다. 대신 필요할 때 다음을 확인한다.

```bash
DATABASE_URL=sqlite:///./storage/jbwm_demo.db \
AGENT_JOB_MODE=codex_cli \
AGENT_JOB_CODEX_MODEL=gpt-5.4-mini \
AGENT_JOB_CODEX_REASONING_EFFORT=low \
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

그 뒤 프론트나 curl로 투자 손실 이벤트를 트리거하고 `/dev`에서 다음을 본다.

- `runtime.mode = codex_cli`
- `runtime.codex_model`
- `runtime.duration_seconds`
- `input_json.signal`
- `output_json.message`
- `context.json을 읽을 수 없다` 같은 비근거 응답이 없는지

## 아직 남은 운영급 QA

- LangGraph checkpointer를 DB 기반으로 바꾼 뒤 durable checkpoint 테스트
- Supabase/PostgreSQL RLS 통합 테스트
- 실제 provider 계약이 생겼을 때 adapter contract 테스트
- executor/verifier를 action별 모듈로 나눈 뒤 idempotency 테스트
- Playwright 기반 브라우저 smoke test
- container 수준의 Codex CLI sandbox 테스트
- Web Push subscription과 notification intent 테스트
