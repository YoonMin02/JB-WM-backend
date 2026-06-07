# 에이전트 job 실행 구조

이 문서는 JB-WM에서 에이전트를 어떻게 실행할지 정한다. 기준은
로컬 참고 구현인 `temp/Codex_with_Gmail`의 흐름이다. Gmail 예제는 신뢰된 메일
명령을 받으면 Codex CLI를 별도 프로세스로 띄우고 결과 파일만 회수한다. JB-WM은
같은 패턴을 금융 이벤트에 적용한다. 단, `temp/`는 런타임 의존성이 아니라 설계
참고 자료다.

## 기본 흐름

```text
SignalGate
-> AgentJob row 생성
-> /tmp/jbwm-agent-jobs/{job_id}/context.json 작성
-> 같은 정제 context payload를 stdin으로 전달
-> local_stub 또는 codex exec 실행
-> output.json 회수
-> schema validation
-> 금지 id/customer scope 누출 검사
-> NeedAssessment / Plan / ActionProposal 저장
```

에이전트 job은 항상 단일 고객 snapshot만 받는다. 현재 Codex CLI runner는 같은
payload를 `stdin`과 `context.json`에 둔다. `stdin`은 agent가 실제로 읽는 입력이고,
`context.json`은 `/dev`와 감사/debug에서 확인하는 파일이다. DB URL, provider token,
Supabase service key, executor tool은 받지 않는다.

## 실행 모드

| 모드 | 용도 |
|---|---|
| `local_stub` | 빠른 로컬 테스트와 화면 데모 |
| `codex_cli` | 실제 Codex CLI child process로 agent boundary 검증 |

기본값은 `local_stub`이다. `codex_cli`는 의도적으로 느릴 수 있다. 실제 모델이
컨텍스트를 읽고, 계획을 만들고, 엄격한 JSON schema에 맞춰 최종 답변을 생성하기
때문이다.

## Codex CLI 실행 커맨드

현재 구현은 다음 구조다.

```text
codex exec
  --sandbox read-only
  --skip-git-repo-check
  --ephemeral
  --color never
  --model ${AGENT_JOB_CODEX_MODEL}
  -c model_reasoning_effort="${AGENT_JOB_CODEX_REASONING_EFFORT}"
  --output-schema /tmp/jbwm-agent-jobs/{job_id}/output_schema.json
  --output-last-message /tmp/jbwm-agent-jobs/{job_id}/output.json
  -C /tmp/jbwm-agent-jobs/{job_id}
  "<prompt>"
```

`--ephemeral`은 job마다 Codex 세션 파일을 남기지 않게 한다. JB-WM agent job은
대화 세션을 이어가는 용도가 아니라 이벤트 1건을 독립 처리하는 worker이므로
이 옵션이 맞다.

모델은 감으로 고정하지 않고 벤치 결과를 기준으로 환경 변수로 지정한다.

```dotenv
AGENT_JOB_CODEX_MODEL=gpt-5.4-mini
AGENT_JOB_CODEX_REASONING_EFFORT=low
```

2026-06-07 로컬 측정에서는 `gpt-5.4-mini`, `gpt-5.5`,
`gpt-5.3-codex-spark`가 성공했다. `gpt-5.3-codex-spark`가 작은 스모크에서는
가장 빨랐지만 research preview/account 의존성이 있으므로 기본값은 안정 fast
후보인 `gpt-5.4-mini`로 둔다. 자세한 결과는
[`codex_cli_model_benchmark.md`](codex_cli_model_benchmark.md)를 본다.

child process 환경 변수는 allowlist 방식으로 전달한다.

```text
허용: PATH, LANG, LC_ALL, TMPDIR
차단: DATABASE_URL, JWT_SECRET, HOME, Supabase service key, provider token
```

## 왜 CLI 모드가 느릴 수 있는가

현재 관찰 기준으로는 입력 파일 크기가 병목은 아니다. `context.json`은 보통
수십 KB 이하이고, agent job 디렉터리 전체도 작다. 시간이 걸리는 주된 이유는
다음에 가깝다.

1. `codex exec` 프로세스를 매번 새로 띄운다.
2. 실제 모델 호출이 발생한다.
3. 출력이 엄격한 JSON schema를 만족해야 한다.
4. 샌드박스와 job directory 준비가 매 실행마다 일어난다.

따라서 화면 데모와 테스트는 `AGENT_JOB_MODE=local_stub`을 쓴다. 실제 agent
boundary를 확인할 때만 `AGENT_JOB_MODE=codex_cli`를 쓴다.

각 job result에는 runtime 정보가 남는다.

```json
{
  "runtime": {
    "mode": "codex_cli",
    "codex_model": "gpt-5.4-mini",
    "codex_reasoning_effort": "low",
    "duration_seconds": 72.4,
    "input_bytes": 11800,
    "output_bytes": 3600
  }
}
```

개발자 화면(`/dev`)에서는 이 값을 보고 실제 CLI가 얼마나 걸렸는지 확인한다.
만약 input_bytes가 비정상적으로 커지면 context pack을 줄이고, duration만 크면
모델 작업 시간으로 본다.

## 출력 계약

에이전트 최종 출력은 JSON만 허용한다.

```json
{
  "assessment": {
    "cashflow_need": "high",
    "insurance_need": "mid",
    "asset_defense_need": "high",
    "investment_adjust_need": "mid",
    "life_plan_need": "low",
    "primary_need": "cashflow",
    "confidence": 0.82,
    "rationale": "..."
  },
  "plan": {
    "explanation": "...",
    "assessment": { "...": "..." },
    "proposals": [
      {
        "kind": "report",
        "summary": "...",
        "has_external_effect": false,
        "params": {},
        "rationale": "..."
      }
    ]
  },
  "message": "고객에게 보여줄 짧은 설명"
}
```

출력에 `customer_id`, `graph_thread_id`, `DATABASE_URL` 같은 내부 id/namespace가
나오거나 실제 server-owned id가 포함되면 저장 전에 폐기한다.

## 운영 원칙

- 에이전트는 판단과 제안만 한다.
- 외부 금융 API 호출은 adapter/executor만 한다.
- 실행은 `proposal_id`를 기준으로 DB에서 다시 scope를 확인한 뒤 진행한다.
- 승인 필요 제안은 고객 승인 전 실행할 수 없다.
- job directory는 고객별 장기 저장소가 아니라 감사와 디버깅을 위한 임시 산출물이다.
- agent가 "context.json을 읽을 수 없다"는 식의 비근거 응답을 내면 output validation에서 실패 처리한다.
