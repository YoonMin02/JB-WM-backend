"""SQLModel 엔진 / 세션."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

# psycopg(v3) 드라이버. DATABASE_URL이 postgresql:// 이면 SQLAlchemy 기본 드라이버 사용.
engine = create_engine(settings.database_url, echo=False, pool_pre_ping=True)


def init_db() -> None:
    """모든 SQLModel 테이블 생성. (MVP: Alembic 대신 create_all)"""
    # 모델 등록을 위해 import 필요
    import app.models  # noqa: F401

    _reconcile_mvp_schema()
    SQLModel.metadata.create_all(engine)


def _reconcile_mvp_schema() -> None:
    """MVP 개발 DB의 작은 스키마 변경을 보정한다.

    Alembic 도입 전까지 로컬 PostgreSQL에 남은 이전 컬럼명을 안전하게 맞춘다.
    운영 migration 대체물이 아니라, 개발 DB 재초기화 없이 최근 모델 rename을 따라가기 위한 장치다.
    """
    inspector = inspect(engine)
    if not inspector.has_table("agentsession"):
        return

    columns = {col["name"] for col in inspector.get_columns("agentsession")}
    with engine.begin() as conn:
        if "active_needs" not in columns and "active_intents" in columns:
            conn.execute(text("ALTER TABLE agentsession RENAME COLUMN active_intents TO active_needs"))
            columns.remove("active_intents")
            columns.add("active_needs")
        if "active_needs" not in columns:
            conn.execute(text("ALTER TABLE agentsession ADD COLUMN active_needs JSON"))


def get_session() -> Iterator[Session]:
    """FastAPI 의존성: 요청 단위 DB 세션."""
    with Session(engine) as session:
        yield session
