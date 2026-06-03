# 04 · 에이전트 런타임 (공급자 무관)

이 문서는 **추론 백엔드와 무관한** 에이전트 루프와 인터페이스를 정의합니다. Codex SDK의 구체 연동은 [CODEX_ADAPTER.md](CODEX_ADAPTER.md)에 분리되어 있습니다.

> 원칙: 에이전트 루프·도구·상태는 우리가 영구히 소유한다. **어떤 LLM 공급자를 쓰는지는 어댑터 뒤의 교체 가능한 세부사항이다.**

## 고객별 통합 에이전트

JB WM의 기본 단위는 도메인별 agent가 아니라 **고객별 holistic WM agent**입니다.
건강, 의료비, 보험, 현금흐름, 자산, 투자전략, 생애계획을 분리된 agent가 나눠 보는
것이 아니라, 하나의 통합 agent가 매 turn 최신 고객 컨텍스트와 장기 메모리를 함께 봅니다.

기본 운영 모델:

```text
Customer 1명
  ├─ active holistic AgentSession 1개
  │    └─ Codex thread 1개
  ├─ CustomerMemory
  ├─ Health / Insurance / Portfolio / Loans
  └─ AgentMessage / AgentEvent
```

하나의 통합 agent는 `AssessNeed` 단계에서 여러 필요도를 함께 평가합니다. 이 평가 결과는
FSM 상태가 아니라 `NeedAssessment` 구조화 출력입니다.

## LLM이 하는 일 vs 코드가 하는 일

흔한 오해를 먼저 정리합니다. **계획·행동 판단은 LLM이 합니다** (에이전트의 두뇌). 다만 **권한·상태·실제 실행은 코드가** 가집니다.

| LLM (에이전트 두뇌) — 능동 | 코드 (FSM + Policy + Executor) — 권한 |
|---|---|
| 통합 상황 인식, 의도 추론 | 현재 상태의 단일 진실 |
| **계획 생성** (무슨 액션을 할지) | 허용 전이 강제 |
| **행동 판단** (어떤 도구를 부를지) | 고객 승인 여부 확인 |
| 읽기·분석 도구 호출을 주도 | **되돌릴 수 없는 실제 실행의 방아쇠** |
| 요약·설명 생성 | 재시도·타임아웃·스케줄 |

> 비유: LLM = 진단·처방을 *제안*하는 의사. 코드 = 동의서 없으면 수술을 못 들어가게 막고, 동의 후에만 집도하는 병원 시스템.

## AgentReasoner 포트 (우리 소유)

추론 백엔드는 이 인터페이스 뒤에 있습니다. 구현체(어댑터)만 갈아끼우면 공급자 교체가 됩니다.

```python
# app/agent/runtime.py  (개념 스케치)
from typing import Protocol, Any
from app.agent.schemas import NeedAssessment, Plan

class AgentReasoner(Protocol):
    """공급자 무관 추론 인터페이스. Codex/Gemini/Anthropic 등이 구현."""

    last_thread_id: str | None

    async def start_session(self, customer_id: str, ctx: dict) -> str:
        """추론 세션 시작. 반환: 재개용 세션/thread id."""
        ...

    async def resume_session(self, session_ref: str) -> str:
        """기존 세션 재개. 반환: 같은 세션/thread id."""
        ...

    async def assess_need(self, signal: dict, ctx: dict, session_ref: str | None = None) -> NeedAssessment:
        """신호로부터 통합 필요도 평가 (read-only 도구 사용 가능)."""
        ...

    async def generate_plan(
        self, assessment: NeedAssessment, ctx: dict, memory: dict, session_ref: str | None = None
    ) -> Plan:
        """필요도 평가 + 장기 메모리(개인화) → 액션 제안 계획."""
        ...
```

- 반환은 **구조화 스키마**(Pydantic). 자유 텍스트가 아니라 `NeedAssessment`, `Plan(ActionProposal[])`.
- 도구 호출은 어댑터 내부에서 일어나며, **읽기·분석·제안만** 가능 (실행 도구 없음 — [06](06_TOOL_CONTRACTS.md)).

## 에이전트 루프 (Orchestrator)

```python
# app/agent/orchestrator.py  (개념 스케치)
async def handle_signal(self, session, signal):
    self.fsm.to(session, "SignalDetected")

    ctx = self.tools.build_latest_customer_context(session.customer_id)
    assessment = await self.reasoner.assess_need(signal, ctx)
    if assessment.needs_clarification:
        return self.ask_user(session, assessment.clarifying_question)  # ClarifyUser

    memory = self.memory.long_term(session.customer_id)
    self.fsm.to(session, "GeneratePlan")
    plan = await self.reasoner.generate_plan(assessment, ctx, memory)

    routing = self.policy.evaluate(plan)          # RiskCheck
    if routing.needs_approval:
        return self.request_approval(session, plan)  # NeedApproval → UserApproval
    return self.execute(session, plan)            # AutoExecutable → ExecuteAction
```

핵심: **Orchestrator는 reasoner 출력을 받아 FSM/Policy/Executor로 라우팅**합니다. reasoner는 절대 상태를 직접 바꾸거나 실행하지 않습니다.

LLM이 상태머신에 들어가는 곳은 두 군데가 중심입니다.

1. `AssessNeed`에서 `NeedAssessment`를 생성해 명확화/성향변경/계획생성 분기의 입력을 제공합니다.
2. `GeneratePlan`에서 `Plan(ActionProposal[])`을 생성합니다.

전이는 LLM이 직접 수행하지 않습니다. Orchestrator가 reasoner 출력이 허용된 상태인지
검증하고, Policy Engine이 승인 필요 여부를 판단한 뒤, Executor만 실제 실행합니다.

## 추론 세션 ↔ 분석 세션

| 백엔드 개념 | 추론 개념 |
|---|---|
| `agent_session.id` | 고객별 active holistic agent session 식별자 |
| `agent_session.agent_thread_id` | 해당 고객 agent의 Codex thread 참조 |

기본은 고객 1명당 active holistic agent session 1개입니다. Orchestrator는 첫 신호 처리 전에
`start_session(customer_id, ctx)`를 호출하고 Codex thread id를 즉시 영속화하여, 프로세스가
재시작해도 같은 고객 agent thread를 재개할 수 있게 합니다. 이후 `AssessNeed`,
`GeneratePlan`, `RevisePlan`은 저장된 `agent_thread_id`로 `resume_session()`/`thread_resume()`을
사용합니다. 별도 시뮬레이션, 감사 분리, thread rollover 같은 경우에만 예외적으로 새
session/thread를 만듭니다.

## 구조화 출력

reasoner는 JSON 스키마에 맞는 출력을 반환해야 합니다.

```python
# app/agent/schemas.py  (개념)
class NeedAssessment(BaseModel):
    medical_cost_need: Literal["none","low","mid","high"]
    insurance_need: Literal["none","low","mid","high"]
    cashflow_need: Literal["none","low","mid","high"]
    asset_defense_need: Literal["none","low","mid","high"]
    investment_adjust_need: Literal["none","low","mid","high"]
    life_plan_need: Literal["none","low","mid","high"]
    primary_need: str
    confidence: float
    rationale: str
    clarifying_question: str | None = None

class ActionProposal(BaseModel):
    kind: Literal["book_hospital","review_insurance","cashflow_plan",
                  "rebalance_portfolio","notify","report"]
    summary: str
    has_external_effect: bool         # Policy 라우팅의 입력
    params: dict

class Plan(BaseModel):
    proposals: list[ActionProposal]
    explanation: str
```

`has_external_effect`가 곧 Policy Engine의 핵심 입력입니다 ([07](07_ACTION_EXECUTION.md)).

## 스트리밍 (선택, Phase 후반)

진행 상황을 프론트에 실시간 표시하려면 어댑터가 토큰/이벤트 스트림을 노출합니다. 포트에 `stream_*` 변형을 추가하되, MVP는 블로킹 호출 + 폴링으로 충분합니다.

## 마이그레이션 표면

| 바꾸려는 것 | 건드릴 파일 |
|---|---|
| Codex → Gemini/Anthropic | `app/agent/{provider}_adapter.py` 신규 + 주입 변경 |
| 그 외 (FSM·Policy·Executor·Memory·Tools·도메인) | **변경 없음** |

자세한 Codex 구현은 [CODEX_ADAPTER.md](CODEX_ADAPTER.md).
