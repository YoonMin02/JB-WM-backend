"""SQLModel 엔진 / 세션."""
from __future__ import annotations

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

# psycopg(v3) 드라이버. DATABASE_URL이 postgresql:// 이면 SQLAlchemy 기본 드라이버 사용.
engine = create_engine(settings.database_url, echo=False, pool_pre_ping=True)


def init_db() -> None:
    """모든 SQLModel 테이블 생성. (MVP: Alembic 대신 create_all)"""
    # 모델 등록을 위해 import 필요
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI 의존성: 요청 단위 DB 세션."""
    with Session(engine) as session:
        yield session
