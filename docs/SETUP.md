# Setup

## Prerequisites

- Python 3.12+
- uv
- PostgreSQL, or a compatible local DB URL

No global LLM CLI is required.

## Install

```bash
cd JB-WM-backend
bash scripts/install.sh
cp .env.example .env
```

Default settings use `REASONER=stub`, so local demo and tests run without a Codex login session.

## Run

```bash
uv run uvicorn app.main:app --reload
```

Open:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`

## Enable Real LLM Reasoning

Edit `.env`:

```dotenv
REASONER=pydantic_ai
CODEX_MODEL=gpt-5.4-mini
CODEX_MODEL_REASONING_EFFORT=low
```

Run `codex login` once on the server, then restart the backend.

## Tests

```bash
uv run pytest -q
```

## DB Initialization

For local development, the app creates tables and seeds demo data on startup. If you need a clean DB, drop/recreate the dev database and restart the backend.
