"""구조화 로깅 설정."""
from __future__ import annotations

import logging

from app.core.config import settings


def configure_logging() -> None:
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


logger = logging.getLogger("jbwm")
