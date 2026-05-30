"""모델 공통 헬퍼."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone


def new_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
