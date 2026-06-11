"""Authentication routes for seeded demo accounts."""
from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.deps import current_principal, db_session
from app.core.auth import Principal, create_jwt, verify_password
from app.models.auth import UserAccount
from app.models.base import utcnow

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: str
    password: str


def _user_dict(user: UserAccount) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "customer_id": user.customer_id,
        "active": user.active,
    }


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(db_session)) -> dict:
    user = db.exec(select(UserAccount).where(UserAccount.email == body.email.lower())).first()
    if user is None or not user.active or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "이메일 또는 비밀번호가 올바르지 않습니다.")

    user.last_login_at = utcnow()
    user.updated_at = utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_jwt(subject=user.id, role=user.role, customer_id=user.customer_id)
    return {"access_token": token, "token_type": "bearer", "user": _user_dict(user)}


@router.get("/me")
def me(
    db: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> dict:
    if principal.subject == "local-dev":
        return {
            "id": "local-dev",
            "email": "local-dev@jbwm.local",
            "role": "operator",
            "customer_id": None,
            "active": True,
        }
    user = db.get(UserAccount, principal.subject)
    if user is None or not user.active:
        raise HTTPException(401, "유효하지 않은 계정입니다.")
    return _user_dict(user)
