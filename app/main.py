"""FastAPI 진입점."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import customers, health, proposals, sessions
from app.core.config import settings
from app.core.database import init_db
from app.core.logging import configure_logging, logger
from app.seed import seed_if_empty


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_db()
    cid = seed_if_empty()
    if cid:
        logger.info("seed 고객: %s", cid)
    yield


app = FastAPI(title="JB WM Agent", version="0.1.0", lifespan=lifespan)

app.include_router(health.router)
app.include_router(customers.router)
app.include_router(sessions.router)
app.include_router(proposals.router)


@app.get("/")
def root() -> dict:
    return {"service": settings.app_name, "reasoner": settings.reasoner}
