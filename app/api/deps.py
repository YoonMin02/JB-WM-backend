"""FastAPI 의존성."""
from __future__ import annotations

from collections.abc import Iterator

from sqlmodel import Session

from app.core.database import get_session


def db_session() -> Iterator[Session]:
    yield from get_session()
