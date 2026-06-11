# 재설계 문서 읽는 순서

이 폴더는 현재 JB-WM 백엔드의 기준 문서다. 공식 구조는 금융 이벤트를 코드가
감지하고, LangGraph가 상태를 관리하고, 샌드박스된 에이전트 job이 판단 결과만
만들고, 승인/실행은 코드가 책임지는 방향이다.

핵심 관점은 다음과 같다.

```text
외부/목업 API 데이터 수집
-> 고객별 scope 확인
-> 이벤트 감지
-> LangGraph 상태 전이
-> 샌드박스 agent job 실행
-> 구조화 결과 검증
-> 정책 검사
-> 고객 승인
-> 승인된 일만 실행
-> 실행 결과 확인
-> 필요하면 웹앱 알림
```

에이전트는 "판단 worker"다. DB를 직접 조회하거나, 다른 고객 정보를 찾거나,
금융 실행을 직접 호출하지 않는다. 코드 레이어가 고객 scope, 데이터 조회,
정책 검사, 승인, 실행, 감사 로그를 맡는다.

## 먼저 읽을 문서

1. [`architecture.md`](architecture.md)
   - 전체 레이어와 모듈 경계를 설명한다.
   - 어떤 코드는 에이전트가 하고, 어떤 코드는 서버/스킬이 해야 하는지 잡는다.

2. [`workflow.md`](workflow.md)
   - LangGraph state와 node 흐름을 설명한다.
   - `DataRefresh`, `SignalDetect`, `SpawnAgent`, `PolicyCheck`,
     `ApprovalInterrupt`, `ExecuteAction`, `VerifyResult`가 어떤 순서로 이어지는지 본다.

3. [`security.md`](security.md)
   - 고객별 namespace, thread owner check, sandbox, DB scope 규칙을 설명한다.
   - LangGraph의 `thread_id`는 상태 재개 포인터일 뿐 보안 장치가 아니라는 점이 중요하다.

4. [`agent_jobs.md`](agent_jobs.md)
   - 로컬 참고 구현인 `temp/Codex_with_Gmail`의 "검증된 이벤트마다 CLI worker를 띄우고 결과만 회수한다"는 패턴을 JB-WM에 적용한 방식이다.
   - 이벤트마다 정제된 context payload를 만들고 `codex exec` 또는 `local_stub`로 agent job을 실행한다.
   - 실제 Codex CLI 모델 후보와 속도는 [`codex_cli_model_benchmark.md`](codex_cli_model_benchmark.md)를 본다.

5. [`codex_cli_model_benchmark.md`](codex_cli_model_benchmark.md)
   - `codex exec --model` 후보를 실제로 돌려본 결과다.
   - `AGENT_JOB_CODEX_MODEL`과 `AGENT_JOB_CODEX_REASONING_EFFORT` 기본값을 왜 그렇게 잡았는지 설명한다.

6. [`workflow_code_plan/`](workflow_code_plan/)
   - 실제 코드로 갈아엎을 때 필요한 상세 계획이다.
   - 특히 데이터 수집/이벤트 감지, 승인 후 실행, 처리 확인을 어떻게 구현할지 정리한다.

7. [`notifications.md`](notifications.md)
   - 나중에 휴대폰 PWA/Web Push 알림을 붙일 때의 구조다.
   - SSE와 Push의 책임 차이, subscription 저장, 알림 intent, 보안 규칙을 설명한다.

8. [`react_demo.md`](react_demo.md)
   - 현재 `webapp/` 데모 화면의 역할과 API 계약을 설명한다.
   - 이 화면은 운영 UI가 아니라 LangGraph 흐름을 검증하는 로컬 테스트 하네스다.

9. [`testing.md`](testing.md)
   - 이 재설계에서 깨지면 안 되는 회귀 테스트 목록이다.
   - 고객 scope 섞임, 승인 전 실행, agent output 검증, sandbox 경계를 테스트한다.

## 짧은 결론

```text
LangGraph = 상태 흐름과 승인 대기/resume
Scoped Data Layer = 유일한 DB/API 조회권자
Sandboxed Agent Job = 정제된 단일 고객 context만 받는 판단 worker
Policy/Executor = 유일한 실행 권한자
Notification Layer = 확정된 상태를 사용자에게 알려주는 전달 채널
React 데모 = 로컬 검증 UI
```

이 구조에서 에이전트가 잘못된 지시를 받더라도, 다른 고객 DB를 조회할 도구가 없고,
승인되지 않은 제안을 실행할 권한도 없다. 보안은 프롬프트가 아니라 namespace,
scope check, DB 정책, sandbox, executor gate가 담당한다.
