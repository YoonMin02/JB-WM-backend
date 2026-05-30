"""통계/기준 데이터 (분류 ②) — 참고 데이터, per-customer 아님.

파라미터 쿼리 도구 get_population_stat로 노출 (06_TOOL_CONTRACTS, STATS_SOURCES).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.models.base import new_uuid


class PopulationStat(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    age_band: str = Field(index=True)  # "65-69"
    metric: str = Field(index=True)  # avg_assets, mortality_rate, cardio_risk ...
    value: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    source: str = ""  # KOSIS / KIDI / KNHANES ...
    as_of: str = ""  # 기준시점
