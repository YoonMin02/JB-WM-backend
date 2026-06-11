"""Web Push subscription registration."""
from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.deps import current_principal, db_session
from app.core.auth import Principal
from app.models.auth import PushSubscription, UserAccount
from app.models.base import utcnow

router = APIRouter(prefix="/push-subscriptions", tags=["push-subscriptions"])


class PushKeysIn(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionIn(BaseModel):
    endpoint: str
    keys: PushKeysIn
    user_agent: str = ""
    metadata: dict = Field(default_factory=dict)


def _account_for_principal(db: Session, principal: Principal) -> UserAccount:
    user = db.get(UserAccount, principal.subject)
    if user is None or not user.active:
        raise HTTPException(401, "유효하지 않은 계정입니다.")
    return user


def _subscription_dict(row: PushSubscription) -> dict:
    return {
        "id": row.id,
        "customer_id": row.customer_id,
        "endpoint": row.endpoint,
        "user_agent": row.user_agent,
        "status": row.status,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
        "last_seen_at": row.last_seen_at.isoformat(),
    }


@router.post("")
def register_push_subscription(
    body: PushSubscriptionIn,
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> dict:
    if principal.subject == "local-dev":
        raise HTTPException(401, "push subscription 등록은 로그인 계정이 필요합니다.")
    user = _account_for_principal(db, principal)
    row = db.exec(
        select(PushSubscription).where(
            PushSubscription.user_account_id == user.id,
            PushSubscription.endpoint == body.endpoint,
        )
    ).first()
    if row is None:
        row = PushSubscription(
            user_account_id=user.id,
            customer_id=user.customer_id,
            endpoint=body.endpoint,
            p256dh=body.keys.p256dh,
            auth=body.keys.auth,
            user_agent=body.user_agent,
            meta=body.metadata,
        )
    else:
        row.customer_id = user.customer_id
        row.p256dh = body.keys.p256dh
        row.auth = body.keys.auth
        row.user_agent = body.user_agent
        row.meta = body.metadata
        row.status = "active"
        row.updated_at = utcnow()
        row.last_seen_at = utcnow()
    db.add(row)
    db.commit()
    db.refresh(row)
    return _subscription_dict(row)


@router.get("")
def list_push_subscriptions(
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> dict:
    if principal.subject == "local-dev":
        return {"subscriptions": []}
    user = _account_for_principal(db, principal)
    rows = db.exec(
        select(PushSubscription)
        .where(PushSubscription.user_account_id == user.id)
        .order_by(PushSubscription.created_at.desc())
    ).all()
    return {"subscriptions": [_subscription_dict(row) for row in rows]}


@router.delete("/{subscription_id}")
def revoke_push_subscription(
    subscription_id: str,
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> dict:
    if principal.subject == "local-dev":
        raise HTTPException(401, "push subscription 해제는 로그인 계정이 필요합니다.")
    user = _account_for_principal(db, principal)
    row = db.get(PushSubscription, subscription_id)
    if row is None or row.user_account_id != user.id:
        raise HTTPException(404, "push subscription을 찾을 수 없습니다.")
    row.status = "revoked"
    row.updated_at = utcnow()
    db.add(row)
    db.commit()
    return {"id": row.id, "status": row.status}
