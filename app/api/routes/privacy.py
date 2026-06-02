"""Privacy / consent management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.deps import db_session
from app.privacy.service import revoke_consent

router = APIRouter(prefix="/customers/{customer_id}/privacy", tags=["privacy"])


@router.post("/consents/{consent_id}/revoke")
def revoke_customer_consent(
    customer_id: str,
    consent_id: str,
    db: Session = Depends(db_session),
) -> dict:
    try:
        return revoke_consent(db, customer_id=customer_id, consent_id=consent_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
