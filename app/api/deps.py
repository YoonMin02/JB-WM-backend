"""FastAPI 의존성."""
from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, Header, HTTPException
from sqlmodel import Session

from app.core.auth import Principal, verify_jwt
from app.core.config import settings
from app.core.database import get_session
from app.models.auth import UserAccount


def db_session() -> Iterator[Session]:
    yield from get_session()


def current_principal(
    authorization: str | None = Header(default=None),
    db: Session = Depends(db_session),
) -> Principal:
    if not authorization:
        if settings.app_env in {"local", "dev"}:
            return Principal(subject="local-dev", role="operator")
        raise HTTPException(401, "인증이 필요합니다.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Bearer 토큰이 필요합니다.")
    token_principal = verify_jwt(token)
    account = db.get(UserAccount, token_principal.subject)
    if account is None or not account.active:
        raise HTTPException(401, "유효하지 않은 계정입니다.")
    return Principal(subject=account.id, role=account.role, customer_id=account.customer_id)
