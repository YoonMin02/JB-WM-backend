"""FastAPI 진입점."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import customers, health, privacy, proposals, sessions, workflows
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

# 프론트(개발 서버)에서 호출 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(customers.router)
app.include_router(sessions.router)
app.include_router(proposals.router)
app.include_router(privacy.router)
app.include_router(workflows.router)


@app.get("/")
def root() -> dict:
    return {
        "service": settings.app_name,
        "workflow": "langgraph",
        "agent_job_mode": settings.agent_job_mode,
        "legacy_reasoner": settings.reasoner,
    }
