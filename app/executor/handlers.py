"""Executor — 승인/자동 액션의 실제 실행. LLM을 거치지 않는다.

실행 권한(자격증명·외부 API)은 여기에만 존재한다. MVP는 전부 mock.
(docs/07_ACTION_EXECUTION)
"""
from __future__ import annotations

from decimal import Decimal

from sqlmodel import Session
from sqlmodel import select

from fastapi import HTTPException

from app.core.config import settings
from app.core.logging import logger
from app.models.agent import ActionExecution, ActionProposal, AgentSession
from app.models.finance import Holding, PortfolioAccount
from app.models.insurance import CoverageItem, InsurancePolicy
from app.planning.schemas import ActionProposalSchema
from app.policy.engine import evaluate


def _exec_record(proposal_id: str, executor: str, result: dict, status: str = "success") -> ActionExecution:
    return ActionExecution(proposal_id=proposal_id, executor=executor, status=status, result=result)


def _customer_id_for_proposal(db: Session, proposal: ActionProposal) -> str:
    session = db.get(AgentSession, proposal.session_id)
    return session.customer_id if session else ""


def _external_not_implemented(proposal: ActionProposal) -> ActionExecution:
    return _exec_record(
        proposal.id,
        "ExternalRequestExecutor",
        {
            "mode": settings.action_execution_mode,
            "message": "실제 외부 실행 요청은 아직 구현되지 않았습니다. ACTION_EXECUTION_MODE=mock_apply만 사용하세요.",
        },
        status="failed",
    )


def _apply_mock_insurance_review(db: Session, proposal: ActionProposal) -> dict:
    customer_id = _customer_id_for_proposal(db, proposal)
    policy = db.exec(
        select(InsurancePolicy)
        .where(InsurancePolicy.customer_id == customer_id, InsurancePolicy.active == True)  # noqa: E712
        .order_by(InsurancePolicy.product_name)
    ).first()
    if policy is None:
        policy = InsurancePolicy(customer_id=customer_id, product_name="JB 보장점검 결과", policy_type="건강")
        db.add(policy)
        db.commit()
        db.refresh(policy)

    existing = db.exec(
        select(CoverageItem).where(
            CoverageItem.policy_id == policy.id,
            CoverageItem.coverage_type == "심혈관특약",
            CoverageItem.active == True,  # noqa: E712
        )
    ).first()
    if existing is None:
        db.add(CoverageItem(policy_id=policy.id, coverage_type="심혈관특약", limit_amount=Decimal(20_000_000), active=True))
        db.commit()

    return {
        "document": "보험 보장 점검 결과 (mock)",
        "coverage": "심혈관특약",
        "status": "mock DB 반영 완료",
        "claim_id": f"MOCK-INS-{proposal.id[:8]}",
        "applied": True,
    }


def _apply_mock_rebalance(db: Session, proposal: ActionProposal) -> dict:
    account = db.exec(
        select(PortfolioAccount).where(PortfolioAccount.customer_id == _customer_id_for_proposal(db, proposal))
    ).first()
    if account is None:
        return {"proposal": "리밸런싱 대상 계좌 없음", "applied": False}

    holdings = db.exec(select(Holding).where(Holding.account_id == account.id)).all()
    total = sum((h.amount for h in holdings), Decimal(0))
    if not holdings or total <= 0:
        return {"proposal": "리밸런싱 대상 보유자산 없음", "applied": False}

    target_high = float(proposal.params.get("target_high_risk_weight", 0.45))
    target_low = max(0.0, 1.0 - target_high)
    high_holdings = [h for h in holdings if h.risk_grade == "high"]
    low_holdings = [h for h in holdings if h.risk_grade != "high"]

    if high_holdings:
        high_amount = total * Decimal(str(target_high))
        per_high = high_amount / len(high_holdings)
        for h in high_holdings:
            h.amount = per_high
            h.weight = target_high / len(high_holdings)
            db.add(h)
    if low_holdings:
        low_amount = total * Decimal(str(target_low))
        per_low = low_amount / len(low_holdings)
        for h in low_holdings:
            h.amount = per_low
            h.weight = target_low / len(low_holdings)
            db.add(h)
    db.commit()

    return {
        "proposal": "방어형 리밸런싱 적용 (mock)",
        "applied": True,
        "target_high_risk_weight": target_high,
        "target_low_risk_weight": target_low,
    }

def _handle(db: Session, proposal: ActionProposal) -> ActionExecution:
    """제안 종류별 핸들러. MVP: mock 결과 생성."""
    if settings.action_execution_mode == "external_request":
        return _external_not_implemented(proposal)

    kind = proposal.kind
    if kind == "review_insurance":
        return _exec_record(proposal.id, "InsuranceReviewMockHandler", _apply_mock_insurance_review(db, proposal))
    if kind == "report":
        return _exec_record(proposal.id, "ReportHandler", {"report": proposal.summary})
    if kind == "cashflow_plan":
        return _exec_record(proposal.id, "CashflowPlanHandler", {"plan": "3개월 비상자금 플랜 (mock)"})
    if kind == "rebalance_portfolio":
        return _exec_record(proposal.id, "RebalanceHandler", _apply_mock_rebalance(db, proposal))
    if kind == "book_hospital":
        return _exec_record(
            proposal.id, "HospitalBookingHandler", {"booking": "예약 완료 (mock)", "when": "내주"}
        )
    if kind == "notify":
        return _exec_record(proposal.id, "NotifyHandler", {"notified": True})
    # 미지원 종류
    return _exec_record(proposal.id, "Unknown", {"message": f"미지원 액션: {kind}"}, status="failed")


def execute(db: Session, proposal: ActionProposal) -> ActionExecution:
    """승인/자동 제안을 실행하고 결과를 기록.

    호출 전 상태머신이 '실행 가능' 상태임을 보장해야 한다.
    """
    logger.info("executor 실행: proposal=%s kind=%s", proposal.id, proposal.kind)
    execution = _handle(db, proposal)
    proposal.status = "executed" if execution.status == "success" else "failed"
    db.add(execution)
    db.add(proposal)
    db.commit()
    db.refresh(execution)
    return execution


def execute_scoped(
    db: Session,
    *,
    proposal_id: str,
    customer_id: str,
    require_approval: bool,
) -> ActionExecution:
    """Execute a proposal after re-checking customer ownership and policy.

    This is the entrypoint for the LangGraph redesign. The caller may have a
    graph state, but execution authority is re-derived from the database.
    """

    proposal = db.get(ActionProposal, proposal_id)
    if proposal is None:
        raise HTTPException(404, "제안을 찾을 수 없습니다.")
    session = db.get(AgentSession, proposal.session_id)
    if session is None or session.customer_id != customer_id:
        raise HTTPException(403, "제안의 고객 scope가 일치하지 않습니다.")
    if proposal.status == "executed":
        existing = db.exec(select(ActionExecution).where(ActionExecution.proposal_id == proposal.id)).first()
        if existing is not None:
            return existing
        raise HTTPException(409, "이미 실행된 제안이나 실행 기록이 없습니다.")
    if proposal.status not in {"proposed", "approved"}:
        raise HTTPException(409, f"실행 가능한 제안 상태가 아닙니다: {proposal.status}")

    routing = evaluate(
        ActionProposalSchema(
            kind=proposal.kind,
            summary=proposal.summary,
            has_external_effect=proposal.has_external_effect,
            params=proposal.params,
            rationale=proposal.rationale,
        )
    )
    if routing.needs_approval and require_approval and proposal.status != "approved":
        raise HTTPException(409, "고객 승인 전에는 실행할 수 없습니다.")
    if routing.needs_approval and not require_approval:
        raise HTTPException(409, "승인 필요 제안은 자동 실행할 수 없습니다.")

    return execute(db, proposal)
