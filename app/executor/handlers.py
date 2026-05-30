"""Executor — 승인/자동 액션의 실제 실행. LLM을 거치지 않는다.

실행 권한(자격증명·외부 API)은 여기에만 존재한다. MVP는 전부 mock.
(docs/07_ACTION_EXECUTION)
"""
from __future__ import annotations

from sqlmodel import Session

from app.core.logging import logger
from app.models.agent import ActionExecution, ActionProposal


def _exec_record(proposal_id: str, executor: str, result: dict, status: str = "success") -> ActionExecution:
    return ActionExecution(proposal_id=proposal_id, executor=executor, status=status, result=result)


def _handle(proposal: ActionProposal) -> ActionExecution:
    """제안 종류별 핸들러. MVP: mock 결과 생성."""
    kind = proposal.kind
    if kind == "review_insurance":
        # mock 청구 서류 생성
        result = {
            "document": "보험금 청구 신청서 (초안)",
            "coverage": proposal.params.get("coverage", "실손"),
            "status": "접수 완료 (mock)",
            "claim_id": f"CLAIM-{proposal.id[:8]}",
        }
        return _exec_record(proposal.id, "InsuranceClaimHandler", result)
    if kind == "report":
        return _exec_record(proposal.id, "ReportHandler", {"report": proposal.summary})
    if kind == "cashflow_plan":
        return _exec_record(proposal.id, "CashflowPlanHandler", {"plan": "3개월 비상자금 플랜 (mock)"})
    if kind == "rebalance_portfolio":
        return _exec_record(proposal.id, "RebalanceHandler", {"proposal": "저위험 리밸런싱 제안서 (mock)"})
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
    execution = _handle(proposal)
    proposal.status = "executed" if execution.status == "success" else "failed"
    db.add(execution)
    db.add(proposal)
    db.commit()
    db.refresh(execution)
    return execution
