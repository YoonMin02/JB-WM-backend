# 12 · Implementation Checklist

## Current Runtime Refactor

- [x] `AgentReasoner`를 provider-neutral one-shot interface로 단순화한다.
- [x] 고객별 연속성은 provider session이 아니라 DB `AgentSession`/records가 가진다.
- [x] `ContextBuilder`가 고객 데이터, 최근 대화, 판단 기록, proposal history, policy docs를 묶는다.
- [x] `PydanticAIReasoner`를 추가해 구조화 출력으로 `NeedAssessment`, `Plan`을 받는다.
- [x] 기존 provider-specific runtime 파일과 전용 tool server 코드를 제거한다.
- [x] `.env.example`과 설치 문서를 새 reasoner 설정으로 맞춘다.

## Still Needed For Production Quality

- [ ] `uv.lock`를 새 dependency와 동기화한다.
- [ ] long conversation compact summary table/field를 설계한다.
- [ ] 장기 메모리 승격 기준을 코드와 정책 문서로 분리한다.
- [ ] 질병별 playbook을 `policy_docs/`에 추가한다.
- [ ] 보험/현금흐름/투자전략 판단 기준 문서를 작성한다.
- [ ] `ContextBuilder`가 신호 종류에 따라 관련 policy docs를 우선 선택하도록 개선한다.
- [ ] 실제 외부 API adapter와 mock adapter의 인터페이스를 고정한다.
- [ ] `ACTION_EXECUTION_MODE=external_request` 구현 시 승인/감사/rollback 정책을 추가한다.

## Frontend / Demo

- [x] mock 고객 10명 이상 seed
- [x] API body shape 기반 상세 데이터 노출
- [x] 승인 후 mock DB 반영 흐름
- [ ] 한 명의 deep scenario를 질병 playbook까지 연결해 완성한다.
- [ ] 판단 전문/대화 전문 화면에서 context pack 일부를 확인할 수 있게 한다.

## Safety

- [x] 실행 도구는 LLM 표면에 노출하지 않는다.
- [x] consent 없는 건강 데이터는 제외한다.
- [x] provider raw identifiers는 context에서 제거한다.
- [x] LLM 실패와 rate limit을 API 에러로 정규화한다.
- [ ] 의료 권고 금지 표현 검증을 별도 테스트로 강화한다.
