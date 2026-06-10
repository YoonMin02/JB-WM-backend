"""Minimal JWT and role-based access helpers."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException

from app.core.config import settings

Role = Literal["customer", "advisor", "operator"]
PASSWORD_ITERATIONS = 120_000


@dataclass(frozen=True)
class Principal:
    subject: str
    role: Role
    customer_id: str | None = None


def create_jwt(
    *,
    subject: str,
    role: Role,
    customer_id: str | None = None,
    expires_in_seconds: int = 3600,
) -> str:
    now = int(time.time())
    payload = {
        "sub": subject,
        "role": role,
        "customer_id": customer_id,
        "iat": now,
        "exp": now + expires_in_seconds,
    }
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = f"{_b64(header)}.{_b64(payload)}"
    signature = hmac.new(
        settings.jwt_secret.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_b64_bytes(signature)}"


def hash_password(password: str) -> str:
    salt = secrets.token_urlsafe(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_ITERATIONS,
    )
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${_b64_bytes(digest)}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_raw, salt, expected = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations_raw),
        )
        return hmac.compare_digest(_b64_bytes(digest), expected)
    except Exception:
        return False


def verify_jwt(token: str) -> Principal:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        signing_input = f"{header_b64}.{payload_b64}"
        expected = hmac.new(
            settings.jwt_secret.encode("utf-8"),
            signing_input.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(_b64_bytes(expected), signature_b64):
            raise ValueError("invalid signature")
        payload = json.loads(_b64_decode(payload_b64))
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("token expired")
        role = payload.get("role")
        if role not in {"customer", "advisor", "operator"}:
            raise ValueError("invalid role")
        return Principal(
            subject=str(payload["sub"]),
            role=role,
            customer_id=payload.get("customer_id"),
        )
    except Exception as exc:
        raise HTTPException(401, "유효하지 않은 인증 토큰입니다.") from exc


def require_customer_access(principal: Principal, customer_id: str) -> None:
    if principal.role in {"advisor", "operator"}:
        return
    if principal.role == "customer" and principal.customer_id == customer_id:
        return
    raise HTTPException(403, "해당 고객 데이터에 접근할 권한이 없습니다.")


def require_operator(principal: Principal) -> None:
    if principal.role == "operator":
        return
    raise HTTPException(403, "operator 권한이 필요합니다.")


def _b64(data: dict) -> str:
    return _b64_bytes(json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _b64_bytes(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64_decode(data: str) -> str:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding).decode("utf-8")
