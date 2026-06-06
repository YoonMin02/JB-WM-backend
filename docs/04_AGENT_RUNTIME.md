# 04 · Agent Runtime

JB-WM의 에이전트 런타임은 LLM 공급자 세션에 의존하지 않습니다. 고객별 `AgentSession`은 DB에 존재하고, LLM 호출은 매번 backend가 만든 context pack을 입력으로 받는 구조화 one-shot 판단입니다.

## 원칙

- Backend가 세션, 상태, 메모리, 승인, 실행의 주인입니다.
- LLM은 `NeedAssessment`와 `Plan`만 반환합니다.
- LLM에는 DB 핸들, 파일시스템, 외부 실행 도구를 주지 않습니다.
- 이전 대화와 판단 기록은 `ContextBuilder`가 선택해 매 요청에 다시 주입합니다.

## 고객별 통합 에이전트

```text
Customer
  ├─ active AgentSession 1개
  ├─ CustomerMemory
  ├─ Health / Insurance / Portfolio / Loans / Accounts / Transactions / CardBills
  └─ AgentMessage / AgentEvent / NeedAssessmentRecord / PlanRecord / ActionProposal
```

도메인별 agent를 여러 개 두는 방식이 아닙니다. 하나의 고객 agent가 건강, 의료비, 보험, 현금흐름, 자산방어, 투자전략, 생애설계를 함께 봅니다.

## AgentReasoner Port

```python
class AgentReasoner(Protocol):
    async def assess_need(self, signal: dict, ctx: dict) -> NeedAssessment:
        ...

    async def generate_plan(self, assessment: NeedAssessment, ctx: dict, memory: dict) -> Plan:
        ...
```

현재 구현체:

| 구현체 | 용도 |
|---|---|
| `StubReasoner` | 로컬 데모와 테스트. 결정론적 규칙 |
| `PydanticAIReasoner` | 실제 LLM 구조화 출력 |

`REASONER=stub|pydantic_ai`로 선택합니다.

## ContextBuilder

`app/agent/context_builder.py`가 LLM 입력을 구성합니다.

포함 항목:

- 최신 고객 profile, health, insurance, portfolio, account, transaction, card bill, loan, memory
- 현재 `AgentSession` 상태와 pending proposal
- 최근 대화 `AgentMessage`
- 이전 need assessment와 plan 기록
- proposal 승인/거절/실행 history
- 상태/event timeline
- `policy_docs/`의 `.md`, `.txt` 정책 문서 일부

즉 LLM이 직접 뭔가를 찾아 읽는 구조가 아니라, backend가 무엇을 보여줄지 결정하고 LLM은 그 범위 안에서 판단합니다.

## LLM이 들어가는 지점

```text
Monitoring
  -> SignalDetected
  -> AssessNeed      LLM: 통합 필요도 평가
  -> GeneratePlan    LLM: 실행 제안 계획 생성
  -> RiskCheck       코드: 승인 필요 여부 판단
  -> ExecuteAction   코드: 승인된 액션만 실행
```

LLM은 상태 전이를 직접 실행하지 않습니다. Orchestrator가 LLM 출력을 검증하고 FSM 전이를 적용합니다.

## 구조화 출력

`NeedAssessment`는 모든 필요도를 함께 평가합니다.

```text
medical_cost_need
insurance_need
cashflow_need
asset_defense_need
investment_adjust_need
life_plan_need
primary_need
confidence
rationale
clarifying_question
```

`Plan`은 `ActionProposal[]`을 포함합니다. 외부 효과가 있는 액션은 `has_external_effect=true`여야 하며, Policy Engine이 고객 승인으로 라우팅합니다.

## 세션 연속성

이전 대화 연속성은 LLM 공급자 내부 대화방이 아니라 DB 기록으로 유지합니다.

```text
1. 고객 입력/시스템 신호 저장
2. ContextBuilder가 최근 대화와 판단 기록을 선택
3. LLM one-shot 호출
4. 결과를 DB에 저장
5. 다음 호출 때 다시 context에 주입
```

긴 대화가 쌓이면 별도 요약/compact 정책이 필요합니다. 이 설계 지점은 [13_LLM_DECISION_CONTEXT.md](13_LLM_DECISION_CONTEXT.md)에 정리합니다.

## Provider Migration

PydanticAI는 현재 LLM 호출 라이브러리입니다. 나중에 OpenAI Responses API, Anthropic, Gemini, LangGraph 등으로 바꾸더라도 유지해야 하는 경계는 같습니다.

바뀌는 것:

- `app/agent/pydantic_ai_reasoner.py`
- 환경변수의 model/provider 설정

유지되는 것:

- FSM
- ContextBuilder
- schemas
- Policy Engine
- Executor
- DB memory/audit tables
