# 보안 설계

이 문서는 고객별 context가 섞이지 않고, 에이전트가 임의로 다른 고객 DB를 조회하거나
승인되지 않은 금융 작업을 실행하지 못하게 만드는 구조를 설명한다.

가장 중요한 전제는 다음이다.

```text
LangGraph는 상태 흐름 도구다.
LangGraph thread_id는 권한 검증 장치가 아니다.
보안은 namespace, scoped DB access, sandbox, policy/executor gate가 맡는다.
```

## 반드시 지켜야 할 불변식

- agent job은 DB credential을 받지 않는다.
- agent job은 provider token, Supabase service-role key, raw 계좌/카드/대출 id를 받지 않는다.
- `graph_thread_id`는 opaque id이며 정확히 한 고객/session에만 매핑된다.
- 사용자 입력은 graph `scope`를 만들거나 수정할 수 없다.
- 모든 고객 데이터 read/write는 서버가 만든 `CustomerScope`를 통해서만 한다.
- executor는 proposal, session, customer, approval 상태를 다시 확인한 뒤 실행한다.
- proposal A에 대한 승인은 proposal B 실행 권한이 아니다.
- agent에게 MCP/tool server, DB search tool, 금융 API executor tool을 노출하지 않는다.
- 다른 고객 조회 시도는 이름/문장 파싱이 아니라 server-owned id/scope 검증에서 막는다.

## namespace 구조

외부에 보이는 id와 내부 권한 판단 id를 섞지 않는다.

```text
tenant_id        = jbwm
customer_id      = 내부 고객 UUID
agent_session_id = 고객별 상담/workflow session UUID
graph_thread_id  = LangGraph checkpoint용 opaque UUID
graph_run_id     = 이벤트 처리 1회 UUID
job_id           = agent CLI process 1회 UUID
proposal_id      = 저장된 ActionProposal UUID
execution_id     = 저장된 ActionExecution UUID
```

API에서 `thread_id`나 `proposal_id`가 들어오면 바로 실행하지 않는다.

```text
graph_thread_id/proposal_id 조회
  -> 연결된 customer_id 확인
  -> principal이 customer_id에 접근 가능한지 확인
  -> session 상태 확인
  -> 필요한 경우 scope_hash 확인
  -> 다음 단계 실행
```

이렇게 해야 사용자가 URL이나 payload의 id를 바꿔도 다른 고객 정보가 보이지 않는다.

## 이름으로 막지 않는 이유

사용자가 "박민수 DB 조회"라고 입력했다고 해서 텍스트 앞단에서 막으면 안 된다.
동명이인이 있을 수 있고, "박민수"가 현재 고객 본인일 수도 있으며, 문장 의미가 너무
다양하기 때문이다.

올바른 방식은 다음이다.

1. 사용자 문장은 그냥 `user_utterance` signal로 기록한다.
2. detector/agent는 그 문장을 금융/보험/현금흐름 같은 주제로 분류할 수 있다.
3. 실제 DB 조회나 thread resume이 필요해지는 순간 server-owned id를 사용한다.
4. 그 id가 현재 principal의 고객 scope 밖이면 403/404로 막는다.

즉 프론트에는 "다른 고객 정보는 볼 수 없습니다"라는 안내가 나올 수 있지만, 그
판단은 이름 파싱이 아니라 thread/proposal/customer scope 검증 실패에서 나와야 한다.

## agent job sandbox

개발 최소 기준:

```text
job별 임시 디렉터리: /tmp/jbwm-agent-jobs/{job_id}
입력: 정제된 단일 고객 context payload
디버그 파일: context.json
출력: output.json
env allowlist: PATH, LANG, LC_ALL, TMPDIR
차단 env: DATABASE_URL, JWT_SECRET, HOME, provider token, Supabase service key
timeout: 설정값으로 제한
output size: 설정값으로 제한
```

현재 Codex CLI runner는 같은 정제 context를 두 경로로 제공한다.

- `stdin`: agent가 실제로 읽는 입력
- `context.json`: `/dev` 화면과 감사/debug에서 확인하는 동일 payload

이렇게 한 이유는 CLI sandbox나 모델 행동 때문에 파일 읽기가 실패해도, agent가
"context.json을 읽을 수 없다"는 비근거 답변을 사용자에게 보내지 않도록 하기 위해서다.
그래도 agent가 그런 응답을 만들면 output validation에서 실패 처리한다.

프로덕션 목표:

- 별도 OS user 또는 container
- 기본 no-network
- read-only filesystem
- home directory mount 금지
- CPU/memory 제한
- DB/API credential 미주입
- job directory 외 파일 접근 제한

## DB 보안

로컬 MVP에서는 코드 레벨 scope 확인을 우선 구현한다. Supabase/PostgreSQL로 옮길
때는 customer-owned table에 RLS를 켜는 것이 좋다.

```sql
ALTER TABLE account_balance ENABLE ROW LEVEL SECURITY;

CREATE POLICY account_balance_customer_scope
ON account_balance
USING (customer_id = current_setting('app.customer_id', true));
```

서버 코드는 scoped transaction을 시작할 때 `app.customer_id`를 설정한다. 그러면
실수로 `select *`가 들어가도 DB가 고객 범위를 한 번 더 막아준다.

## 반드시 테스트할 항목

- 고객 A token으로 고객 B thread를 resume/debug 할 수 없다.
- 사용자가 보낸 `thread_id`만으로 checkpoint를 읽을 수 없다.
- graph state의 `scope`가 중간에 바뀌면 실패한다.
- agent output에 `customer_id`, `graph_thread_id`, raw provider id가 있으면 저장하지 않는다.
- agent가 `context.json을 못 읽는다`고 답하면 사용자 메시지로 저장하지 않는다.
- executor는 pending/approved proposal 외에는 실행하지 않는다.
- context pack에는 `fintech_use_num`, 계좌번호, 카드 식별자, token이 없다.
- 동일 signal이 중복 side effect를 만들지 않는다.
- `codex_cli` child process env에는 DB/API secret과 `HOME`이 없다.
