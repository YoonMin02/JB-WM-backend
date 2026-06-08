# Runbook

## Check Backend

```bash
uv run uvicorn app.main:app --reload
curl http://127.0.0.1:8000/health
```

Expected:

- server starts without dependency errors
- `/health` returns 200
- root endpoint shows current `reasoner`

## Reasoner Modes

| Mode | Env | Behavior |
|---|---|---|
| stub | `REASONER=stub` | deterministic local reasoning |
| real LLM | `REASONER=pydantic_ai` | PydanticAI structured output over Codex SDK one-shot calls |

Real LLM mode uses the server's `codex login` OAuth session.

## Logs To Watch

- `session X: A -> B`: FSM transition
- `llm 호출 #N`: real LLM call counter
- `execution`: approved action execution event
- route logs: frontend/API traffic

## Common Failures

| Symptom | Likely cause | Fix |
|---|---|---|
| 503 reasoner unavailable | provider key/model/dependency issue | check `.env`, dependency install, model string |
| 429 reasoner rate limited | `LLM_MAX_CALLS_*` exceeded | raise limit or wait |
| proposal not reflected | `ACTION_EXECUTION_MODE` or executor handler missing | use `mock_apply` or implement handler |
| stale demo data | DB already seeded | reset dev DB and restart |

## Inspect What The LLM Saw

The LLM input is not hidden in a provider session. It is built in:

- `app/agent/context_builder.py`
- `app/agent/pydantic_ai_reasoner.py`

Persistent records are available through:

- `AgentMessage`
- `NeedAssessmentRecord`
- `PlanRecord`
- `ActionProposal`
- `AgentEvent`

Frontend “full details” screens should read these backend records instead of depending on provider-side chat history.
