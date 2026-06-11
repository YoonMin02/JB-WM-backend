"""Population/statistical baseline data."""
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
