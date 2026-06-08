# 13 · LLM Decision Context And Policy Design

이 문서는 PydanticAI 구조에서 LLM 판단 품질을 좌우하는 설계 지점을 정리합니다. 핵심은 “LLM에게 모든 것을 맡기는 것”이 아니라, backend가 어떤 컨텍스트와 규칙을 제공할지 정하고 LLM은 그 안에서 구조화 판단을 하는 것입니다.

## 1. 대화 연속성

현재 구조에서 JB-WM의 세션은 DB의 `AgentSession`입니다. LLM provider 내부 대화방이 세션의 주인이 아닙니다.

매 요청마다 `ContextBuilder`가 아래 항목을 골라 LLM에 다시 제공합니다.

- 최근 고객 발화와 agent 응답
- 이전 `NeedAssessment`
- 이전 `Plan`
- 승인/거절/실행된 `ActionProposal`
- 상태 전이와 주요 이벤트
- 장기 메모리: 위험 성향, 지불의향, 병원 선호, 투자 성향, 제약

### 추가로 정해야 할 것

| 결정 지점 | 코드 위치 | 성격 |
|---|---|---|
| 최근 대화 몇 개를 넣을지 | `app/agent/context_builder.py` | 코드 설정 |
| 오래된 대화를 어떻게 요약할지 | 신규 memory summarizer 필요 | 코드 + LLM 요약 prompt |
| 어떤 정보가 장기 메모리로 승격되는지 | `app/agent/orchestrator.py`, memory service | 코드 정책 |
| 고객이 거절한 제안을 언제 다시 꺼낼 수 있는지 | `policy_docs/` 또는 Policy Engine | 정책 + 코드 |

권장: 단순 transcript 전체를 계속 넣지 말고, `recent_conversation` + `decision_history` + `long_term_memory` + `compact_summary` 네 층으로 나눕니다.

## 2. Compact / 요약 정책

대화가 길어지면 다음 정보를 분리해 저장해야 합니다.

| 종류 | 예시 | 저장 위치 |
|---|---|---|
| 원문 감사 로그 | 고객 발화, agent 응답 전문 | `AgentMessage` |
| 판단 기록 | 왜 보험 필요도를 high로 봤는지 | `NeedAssessmentRecord` |
| 실행 계획 | 어떤 제안을 만들었는지 | `PlanRecord`, `ActionProposal` |
| 장기 선호 | “고위험 투자는 피하고 싶다” | `CustomerMemory` |
| compact summary | 최근 30턴 요약 | 신규 필드/테이블 권장 |

원문은 감사와 재현용이고, LLM 입력은 요약과 핵심 기록 중심이어야 합니다.

## 3. 코드로 강제할 것 vs 문서로 줄 것

### 코드로 강제해야 하는 것

- FSM 상태 전이
- 승인 없는 실행 금지
- 의료 권고 금지에 대한 라우팅/표현 검증
- action kind enum
- 고객/세션 scope
- consent 없는 건강 데이터 제외
- provider raw id 제거
- 호출 rate limit
- context size limit
- executor mode: mock apply vs real execution

### policy 문서로 제공할 것

- 보험 보장 공백 판단 기준
- 질병별 재무 대응 playbook
- 투자전략 조정의 우선순위
- 회사 상품 권유 제한
- 승인 필요 액션 기준
- 고객에게 설명할 때의 문체/금지 표현
- 통계 출처 우선순위

### LLM에게 맡길 것

- 여러 데이터 사이의 trade-off 해석
- 고객 상황에 맞는 우선순위 설명
- 통합 필요도 평가
- 액션 제안의 rationale 작성
- 고객에게 물어야 할 clarifying question 작성

## 4. 보험/자산관리 전문 지식 반영

전문 지식은 코드에 하드코딩하기보다 `policy_docs/`에 작은 문서로 나누어 둡니다.

권장 파일 예시:

```text
policy_docs/
├── medical_boundary.md
├── insurance_gap_rules.md
├── cashflow_risk_rules.md
├── investment_adjustment_rules.md
├── life_plan_rules.md
├── disease_dementia_playbook.md
├── disease_liver_cancer_playbook.md
└── disease_lung_cancer_playbook.md
```

각 문서는 “판단 기준”, “금지할 말”, “필수 확인 데이터”, “가능한 제안”, “승인 필요 액션”을 짧게 포함하는 것이 좋습니다.

## 5. 질병 시나리오 판단 방식

질문: 치매, 간암, 폐암 같은 특정 케이스에서 종합 판단을 할지, 특정 파일을 강하게 참고하게 할지?

권장 답: 둘 다 합니다.

1. 항상 종합 판단을 합니다.
   - 건강 이벤트만 보지 않고 보험, 현금흐름, 대출, 카드청구, 투자위험, 생애계획을 함께 봅니다.

2. 특정 질병이 감지되면 해당 playbook을 강하게 참고합니다.
   - 예: `diagnosis=dementia`이면 `disease_dementia_playbook.md`가 context에 들어가야 합니다.
   - 단, playbook은 의료 처방이 아니라 재무 대비/보험/가족 의사결정/장기 지출 시나리오 기준이어야 합니다.

즉 “통합 판단”을 기본으로 하고, “질병별 playbook”은 판단을 좁히는 것이 아니라 누락되기 쉬운 체크리스트를 보강하는 역할입니다.

## 6. GeneratePlan의 우선순위

회의에서 정한 방향은 `GeneratePlan` prompt와 정책 문서에 반영해야 합니다.

권장 순서:

1. 생애설계 영향 여부 확인
2. 의료비 필요도 확인
3. 보험 보장/청구/보험료 부담 확인
4. 현금흐름 위험 확인
5. 자산방어 필요 확인
6. 위 결과를 종합해 투자전략 조정 여부 판단

이 순서는 FSM 상태를 새로 늘리는 문제가 아니라, `AssessNeed`와 `GeneratePlan` 내부 판단 기준입니다.

## 7. 지금 코드에서 수정해야 할 주요 위치

| 목표 | 파일 |
|---|---|
| LLM 입력에 어떤 고객 데이터를 넣을지 | `app/agent/context_builder.py` |
| LLM의 역할/금지사항/출력 요구 | `app/agent/pydantic_ai_reasoner.py` |
| 필요도/계획 스키마 | `app/agent/schemas.py` |
| 상태 전이 | `app/state_machine/` |
| 승인/자동실행 기준 | `app/policy/` |
| 실제 반영 로직 | `app/executor/` |
| 장기 메모리 승격/갱신 | `app/agent/orchestrator.py`, `app/models/memory.py` |
| 전문 지식/내규 | `policy_docs/*.md` |
| API body shape 기반 mock/adapter | `docs/APIs/`, `app/seed.py`, `app/tools/data_tools.py` |

## 8. MVP 시연 기준

나머지 시나리오가 비어 있어도, 한 고객의 시나리오는 깊게 만들어야 합니다.

예: 치매 위험/진단 이벤트

- 건강 기록: 진단/검사/치료/악화 기록
- 보험: 치매/간병/입원/실손 보장 세부 항목
- 현금흐름: 카드청구, 고정비, 의료비 지출 증가
- 자산: 유동성, 위험자산 비중, 손실 여부
- 대출: 상환 압박
- 장기 메모리: 의료 지불의향, 가족 동반 선호, 위험 회피
- 정책 문서: 치매 playbook
- 결과: 의료 권고 없이 보험 점검, 현금흐름 방어, 자산방어, 투자전략 조정, 생애설계 변경을 통합 제안

이 방식이 해커톤 MVP에서 “그냥 텍스트 생성”이 아니라 “고객 데이터와 정책에 근거한 agent”로 보이게 만듭니다.
