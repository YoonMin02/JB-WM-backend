"""Small deterministic detectors over sanitized customer context.

The detector layer turns financial API/mock data into explicit signal kinds
before a sandboxed agent is allowed to reason about the situation.
"""
from __future__ import annotations

from app.signals.schemas import SignalEnvelope


def detect_signal(source: str, payload: dict, context: dict) -> SignalEnvelope:
    """Return a scoped signal for the workflow.

    Manual test triggers can pass `payload.kind`. When no explicit kind is
    provided, the detector derives a conservative signal from account/card/loan
    context. This keeps event provenance in code instead of in the LLM.
    """

    explicit_kind = str(payload.get("kind") or "").strip()
    text = str(payload.get("text") or "")
    if source == "user_utterance" and not explicit_kind:
        if any(marker in text for marker in ("보험", "보장", "특약")):
            explicit_kind = "insurance_gap"
        elif any(marker in text for marker in ("투자", "손실", "리밸런싱", "포트폴리오")):
            explicit_kind = "portfolio_loss"
        elif any(marker in text for marker in ("카드", "상환", "현금", "생활비")):
            explicit_kind = "upcoming_card_payment_pressure"
    if explicit_kind:
        severity = payload.get("severity") if payload.get("severity") in {"low", "mid", "high"} else "mid"
        return SignalEnvelope(
            source="user_utterance" if source == "user_utterance" else "event",
            kind=explicit_kind,
            severity=severity,
            payload=payload,
            rationale="수동 또는 외부 이벤트 입력으로 전달된 신호입니다.",
        )

    accounts = context.get("accounts", {}).get("liquidity_summary", {})
    card_bills = context.get("card_bills", {})
    loans = context.get("loans", {}).get("loans", [])
    portfolio = context.get("portfolio", {})

    if float(portfolio.get("high_risk_weight") or 0) >= 0.65:
        return SignalEnvelope(
            source="detector",
            kind="portfolio_loss",
            severity="high",
            payload={"high_risk_weight": portfolio.get("high_risk_weight")},
            rationale="고위험 투자 비중이 기준을 초과했습니다.",
        )

    available_cash = int(accounts.get("available_cash_krw") or 0)
    upcoming_card = int(card_bills.get("upcoming_card_payment_krw") or 0)
    monthly_repayment = sum(int(loan.get("monthly_payment") or 0) for loan in loans)
    if available_cash and upcoming_card + monthly_repayment > available_cash * 0.5:
        return SignalEnvelope(
            source="detector",
            kind="upcoming_card_payment_pressure",
            severity="mid",
            payload={
                "available_cash_krw": available_cash,
                "upcoming_card_payment_krw": upcoming_card,
                "monthly_repayment_krw": monthly_repayment,
            },
            rationale="카드 청구와 대출 상환이 가용 현금흐름을 압박합니다.",
        )

    return SignalEnvelope(
        source="detector",
        kind="routine_check",
        severity="low",
        payload=payload,
        rationale="강한 자동 신호가 없어 정기 점검으로 분류했습니다.",
    )
