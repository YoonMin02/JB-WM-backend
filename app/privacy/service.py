"""Consent withdrawal and retention purge services."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlmodel import Session, select

from app.core.config import settings
from app.models.agent import AgentMessage
from app.models.health import HealthRecord, MedicalDocument
from app.models.privacy import ConsentRecord
from app.models.base import utcnow


def revoke_consent(db: Session, *, customer_id: str, consent_id: str) -> dict:
    consent = db.get(ConsentRecord, consent_id)
    if consent is None or consent.customer_id != customer_id:
        raise ValueError("동의 기록을 찾을 수 없습니다.")

    health_records = db.exec(
        select(HealthRecord).where(
            HealthRecord.customer_id == customer_id,
            HealthRecord.consent_id == consent_id,
        )
    ).all()
    medical_docs = db.exec(
        select(MedicalDocument).where(
            MedicalDocument.customer_id == customer_id,
            MedicalDocument.consent_id == consent_id,
        )
    ).all()

    for row in [*health_records, *medical_docs]:
        db.delete(row)
    consent.status = "revoked"
    consent.revoked_at = utcnow()
    db.add(consent)
    db.commit()

    return {
        "consent_id": consent_id,
        "status": consent.status,
        "deleted": {
            "health_records": len(health_records),
            "medical_documents": len(medical_docs),
        },
    }


def purge_expired_sensitive_messages(
    db: Session,
    *,
    now: datetime | None = None,
    retention_days: int | None = None,
) -> dict:
    """Delete old transcript messages according to the sensitive retention setting."""
    days = retention_days if retention_days is not None else settings.privacy_sensitive_retention_days
    cutoff = (now or utcnow()) - timedelta(days=days)
    rows = db.exec(select(AgentMessage).where(AgentMessage.created_at < cutoff)).all()
    for row in rows:
        db.delete(row)
    db.commit()
    return {"deleted": {"agent_messages": len(rows)}, "cutoff": cutoff.isoformat()}
