"""Orchestrator — 에이전트 루프를 FSM/Policy/Executor로 라우팅.

reasoner(LLM)는 판단·계획만 한다. 상태 전이·실행은 여기(코드)가 통제한다.
AssessNeed: 고객 신호를 단일 intent로 좁히지 않고 통합 필요도로 평가한다.
(docs/02_SYSTEM_ARCHITECTURE, 03_STATE_MACHINE, 04_AGENT_RUNTIME)
"""
from __future__ import annotations

from sqlmodel import Session

from app.agent.runtime import AgentReasoner, get_reasoner
from app.agent.schemas import NeedAssessment, Plan
from app.executor.handlers import execute as executor_execute
from app.models.agent import ActionProposal, AgentSession, Signal
from app.models.base import utcnow
from app.models.memory import CustomerMemory
from app.policy.engine import evaluate
from app.state_machine.machine import log_event, transition
from app.state_machine.states import State
from app.tools.data_tools import build_context


class Orchestrator:
    def __init__(self, reasoner: AgentReasoner | None = None) -> None:
        self.reasoner = reasoner or get_reasoner()

    async def handle_signal(self, db: Session, session: AgentSession, source: str, payload: dict) -> AgentSession:
        """신호 수신 → 필요도 평가 → 계획 → 리스크검토 → (자동실행 | 승인대기)."""
        db.add(Signal(session_id=session.id, source=source, payload=payload))
        db.commit()

        transition(db, session, State.SIGNAL_DETECTED, detail={"source": source})
        transition(db, session, State.ASSESS_NEED)

        ctx = build_context(db, session.customer_id)
        log_event(db, session.id, "tool_call", {"tool": "build_context"})

        assessment = await self.reasoner.assess_need({"source": source, "payload": payload}, ctx)
        log_event(db, session.id, "need_assessment", assessment.model_dump())

        if assessment.needs_clarification:
            transition(db, session, State.CLARIFY_USER, detail={"question": assessment.clarifying_question})
            session.recent_context = {
                "clarifying_question": assessment.clarifying_question,
                "assessment": assessment.model_dump(),
            }
            db.add(session)
            db.commit()
            db.refresh(session)
            return session

        session.active_intents = {"primary_need": assessment.primary_need, "needs": self._need_levels(assessment)}
        session.recent_context = {"assessment": assessment.model_dump()}
        db.add(session)
        db.commit()

        if assessment.preference_update_only:
            transition(db, session, State.PREFERENCE_UPDATE, detail={"primary_need": assessment.primary_need})
            return self._finish(db, session)

        if assessment.no_action or not assessment.has_actionable_need:
            transition(db, session, State.NO_ACTION, detail={"primary_need": assessment.primary_need})
            return self._finish(db, session)

        # 계획 생성 (장기 메모리 반영 = 개인화)
        transition(db, session, State.GENERATE_PLAN)
        plan = await self.reasoner.generate_plan(assessment, ctx, ctx.get("memory", {}))
        plan.assessment = assessment
        log_event(db, session.id, "plan", plan.model_dump())
        proposals = self._persist_plan(db, session, plan)

        return await self._risk_route(db, session, proposals)

    def _persist_plan(self, db: Session, session: AgentSession, plan: Plan) -> list[ActionProposal]:
        proposals: list[ActionProposal] = []
        for p in plan.proposals:
            row = ActionProposal(
                session_id=session.id,
                kind=p.kind,
                summary=p.summary,
                has_external_effect=p.has_external_effect,
                params=p.params,
                rationale=p.rationale,
            )
            db.add(row)
            proposals.append(row)
        db.commit()
        for row in proposals:
            db.refresh(row)
        return proposals

    async def _risk_route(self, db: Session, session: AgentSession, proposals: list[ActionProposal]) -> AgentSession:
        transition(db, session, State.RISK_CHECK)

        auto = [p for p in proposals if not evaluate_needs_approval(p)]
        needs = [p for p in proposals if evaluate_needs_approval(p)]

        # 부작용 없는 제안은 즉시 실행 (분석 결과 — AutoExecutable 클래스)
        for p in auto:
            executor_execute(db, p)
            log_event(db, session.id, "execution", {"proposal_id": p.id, "auto": True})

        if needs:
            # 첫 승인 대상 제안을 대기 상태로 (슬라이스 1: 단일 승인 흐름)
            primary = needs[0]
            session.pending_proposal_id = primary.id
            db.add(session)
            db.commit()
            transition(db, session, State.NEED_APPROVAL, detail={"proposal_id": primary.id})
            transition(db, session, State.USER_APPROVAL)
            return session

        # 승인 필요 없음 → 자동 완료 루프
        transition(db, session, State.AUTO_EXECUTABLE)
        transition(db, session, State.EXECUTE_ACTION)
        transition(db, session, State.VERIFY_RESULT)
        return self._finish(db, session)

    async def apply_decision(self, db: Session, session: AgentSession, decision: str, note: str = "") -> AgentSession:
        """USER_APPROVAL 상태에서 고객 결정 처리. 승인 시 Executor가 실행 (LLM 미경유)."""
        if session.state != State.USER_APPROVAL:
            raise ValueError(f"승인 가능한 상태가 아닙니다: {session.state}")

        proposal = db.get(ActionProposal, session.pending_proposal_id)
        if proposal is None:
            raise ValueError("대기 중인 제안이 없습니다.")

        if decision == "approve":
            transition(db, session, State.EXECUTE_ACTION, detail={"proposal_id": proposal.id})
            execution = executor_execute(db, proposal)  # ★ 실행은 여기, LLM 안 거침
            log_event(db, session.id, "execution", {"proposal_id": proposal.id, "status": execution.status})
            target = State.VERIFY_RESULT if execution.status == "success" else State.FAILED
            transition(db, session, target)
            session.pending_proposal_id = None
            return self._finish(db, session)

        if decision == "reject":
            proposal.status = "rejected"
            db.add(proposal)
            transition(db, session, State.NO_ACTION, detail={"proposal_id": proposal.id})
            session.pending_proposal_id = None
            return self._finish(db, session)

        if decision == "revise":
            proposal.status = "deferred"
            db.add(proposal)
            transition(db, session, State.REVISE_PLAN, detail={"note": note})
            # 재계획: 의도 유지하고 plan 재생성
            ctx = build_context(db, session.customer_id)
            assessment = self._assessment_from_session(session)
            transition(db, session, State.GENERATE_PLAN)
            plan = await self.reasoner.generate_plan(assessment, ctx, ctx.get("memory", {}))
            log_event(db, session.id, "plan", {"revised": True, **plan.model_dump()})
            proposals = self._persist_plan(db, session, plan)
            return await self._risk_route(db, session, proposals)

        raise ValueError(f"알 수 없는 결정: {decision}")

    def _finish(self, db: Session, session: AgentSession) -> AgentSession:
        """UpdateMemory → Monitoring 으로 루프 종료."""
        transition(db, session, State.UPDATE_MEMORY)
        self._touch_memory(db, session)
        transition(db, session, State.MONITORING)
        session.active_intents = {}
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def _touch_memory(self, db: Session, session: AgentSession) -> None:
        """슬라이스 1: 최소 메모리 갱신 (존재 보장 + 타임스탬프)."""
        mem = db.get(CustomerMemory, session.customer_id)
        if mem is None:
            mem = CustomerMemory(customer_id=session.customer_id)
        mem.updated_at = utcnow()
        db.add(mem)
        db.commit()
        log_event(db, session.id, "memory", {"updated": True})

    def _need_levels(self, assessment: NeedAssessment) -> dict[str, str]:
        return {
            "medical_cost_need": assessment.medical_cost_need,
            "insurance_need": assessment.insurance_need,
            "cashflow_need": assessment.cashflow_need,
            "asset_defense_need": assessment.asset_defense_need,
            "investment_adjust_need": assessment.investment_adjust_need,
            "life_plan_need": assessment.life_plan_need,
        }

    def _assessment_from_session(self, session: AgentSession) -> NeedAssessment:
        raw = session.recent_context.get("assessment") if session.recent_context else None
        if isinstance(raw, dict):
            return NeedAssessment.model_validate(raw)
        needs = session.active_intents.get("needs", {}) if session.active_intents else {}
        return NeedAssessment(
            primary_need=session.active_intents.get("primary_need", "none") if session.active_intents else "none",
            **{k: v for k, v in needs.items() if k.endswith("_need")},
        )


def evaluate_needs_approval(proposal: ActionProposal) -> bool:
    """DB 제안 → Policy 라우팅 (스키마 어댑팅)."""
    from app.agent.schemas import ActionProposalSchema

    schema = ActionProposalSchema(
        kind=proposal.kind,
        summary=proposal.summary,
        has_external_effect=proposal.has_external_effect,
        params=proposal.params,
    )
    return evaluate(schema).needs_approval
