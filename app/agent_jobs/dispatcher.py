"""Agent job dispatcher using the Codex-with-Gmail process boundary pattern."""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from sqlmodel import Session

from app.agent_jobs.local_stub import build_local_stub_output
from app.core.config import settings
from app.models.base import utcnow
from app.models.agent import AgentSession
from app.models.workflow import AgentJob, DataSnapshot
from app.planning.schemas import AgentJobOutput, NeedAssessment, Plan
from app.planning.validators import reject_forbidden_output_identifiers
from app.signals.schemas import SignalEnvelope

SAFE_ENV_ALLOWLIST = {"PATH", "LANG", "LC_ALL", "TMPDIR"}


class AgentJobDispatcher:
    """Run one isolated agent job and validate its structured output.

    In `local_stub` mode this is deterministic and test-friendly. In `codex_cli`
    mode it writes a job directory and spawns Codex without DB/API credentials.
    """

    def run(
        self,
        db: Session,
        *,
        session: AgentSession,
        snapshot: DataSnapshot,
        signal: SignalEnvelope,
    ) -> dict[str, Any]:
        job = AgentJob(
            graph_thread_id=snapshot.graph_thread_id,
            customer_id=snapshot.customer_id,
            data_snapshot_id=snapshot.id,
            mode=settings.agent_job_mode,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        job_dir = Path(settings.agent_job_root) / job.id
        job_dir.mkdir(parents=True, exist_ok=True)
        input_path = job_dir / "context.json"
        output_path = job_dir / "output.json"
        input_payload = {
            "scope": {"label": "single_customer_snapshot"},
            "signal": signal.model_dump(),
            "context": snapshot.context,
        }
        input_path.write_text(
            json.dumps(input_payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

        started_at = time.perf_counter()
        try:
            if settings.agent_job_mode == "codex_cli":
                raw_output = self._run_codex_cli(input_path, output_path, job_dir)
            else:
                raw_output = build_local_stub_output(signal, snapshot.context)
                output_path.write_text(
                    json.dumps(raw_output, ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8",
                )

            reject_forbidden_output_identifiers(
                raw_output,
                forbidden_values=[session.customer_id, session.id, snapshot.graph_thread_id, snapshot.id, job.id],
            )
            assessment = NeedAssessment.model_validate(raw_output["assessment"])
            plan = Plan.model_validate(raw_output["plan"])
            plan.assessment = assessment
            message = str(raw_output.get("message") or plan.explanation or assessment.rationale)

            job.status = "completed"
            job.input_path = str(input_path)
            job.output_path = str(output_path)
            job.updated_at = utcnow()
            job.result = {
                "assessment": assessment.model_dump(),
                "plan": plan.model_dump(),
                "message": message,
                "runtime": _runtime_summary(started_at, input_path, output_path, settings.agent_job_mode),
            }
            db.add(job)
            db.commit()
            db.refresh(job)
        except Exception as exc:
            job.status = "failed"
            job.input_path = str(input_path)
            job.output_path = str(output_path)
            job.updated_at = utcnow()
            job.result = {
                "error": str(exc),
                "runtime": _runtime_summary(started_at, input_path, output_path, settings.agent_job_mode),
            }
            db.add(job)
            db.commit()
            raise

        return {"job": job, "assessment": assessment, "plan": plan, "message": message}

    def _run_codex_cli(self, input_path: Path, output_path: Path, job_dir: Path) -> dict[str, Any]:
        schema_path = job_dir / "output_schema.json"
        schema_path.write_text(
            json.dumps(_strict_agent_output_schema(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        context_text = input_path.read_text(encoding="utf-8")
        prompt = (
            "You are a sandboxed JB-WM planning worker. The complete sanitized "
            "customer context JSON is appended on stdin; context.json in this "
            "directory contains the same payload for audit/debug inspection. Use "
            "only that provided JSON. Do not access DB, external APIs, customer "
            "records outside the provided context, or execution tools. Your final "
            "response must be valid JSON only and must match output_schema.json "
            "exactly. Use these top-level keys: assessment, plan, and message. "
            "plan must be an object with proposals, explanation, and assessment. "
            "Each proposal must use one of these kinds: book_hospital, "
            "review_insurance, cashflow_plan, rebalance_portfolio, notify, report. "
            "The signal is the trigger. For financial API signals such as "
            "portfolio_loss, spending_spike, income_drop, repayment_pressure, "
            "card_payment_pressure, or loan pressure, prioritize investment, "
            "cashflow, insurance, loan, card, and account evidence. Treat health "
            "or medical context as background only unless the signal explicitly "
            "asks for medical care. For portfolio_loss, do not make book_hospital "
            "the first proposal. If you propose rebalance_portfolio, mark it as "
            "has_external_effect=true because real portfolio changes require "
            "customer approval and executor verification. "
            "Do not say you cannot read context.json; the context is already "
            "provided below through stdin. Do not wrap the response in Markdown."
        )
        cmd = [
            settings.codex_command,
            "exec",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "--ephemeral",
            "--color",
            "never",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
            "-C",
            str(job_dir),
        ]
        _append_codex_model_flags(cmd)
        cmd.append(prompt)
        env = {key: value for key, value in os.environ.items() if key in SAFE_ENV_ALLOWLIST}
        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                input=context_text,
                text=True,
                timeout=settings.agent_job_timeout_seconds,
                env=env,
            )
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or str(exc))[-4000:]
            raise RuntimeError(f"codex_cli failed: {detail}") from exc
        if output_path.stat().st_size > settings.agent_job_output_max_bytes:
            raise ValueError("agent output exceeds max size")
        output = json.loads(output_path.read_text(encoding="utf-8"))
        _reject_context_unavailable_output(output)
        return output


def _runtime_summary(
    started_at: float,
    input_path: Path,
    output_path: Path,
    mode: str,
) -> dict[str, Any]:
    return {
        "mode": mode,
        "codex_model": settings.agent_job_codex_model or "codex_cli_default",
        "codex_reasoning_effort": settings.agent_job_codex_reasoning_effort or "codex_cli_default",
        "duration_seconds": round(time.perf_counter() - started_at, 3),
        "input_bytes": input_path.stat().st_size if input_path.exists() else 0,
        "output_bytes": output_path.stat().st_size if output_path.exists() else 0,
    }


def _append_codex_model_flags(cmd: list[str]) -> None:
    if settings.agent_job_codex_model:
        cmd.extend(["--model", settings.agent_job_codex_model])
    if settings.agent_job_codex_reasoning_effort:
        cmd.extend(
            [
                "-c",
                f'model_reasoning_effort="{settings.agent_job_codex_reasoning_effort}"',
            ]
        )


def _reject_context_unavailable_output(output: dict[str, Any]) -> None:
    text = json.dumps(output, ensure_ascii=False, default=str).lower()
    blocked_phrases = (
        "cannot read context.json",
        "can't read context.json",
        "cannot access context.json",
        "can't access context.json",
        "cannot read the provided context",
        "cannot access the provided context",
        "no access to context.json",
        "context.json을 읽을 수 없습니다",
        "context.json을 읽을 수 없",
        "컨텍스트를 읽을 수 없습니다",
        "제공된 컨텍스트를 읽을 수 없",
    )
    if any(phrase in text for phrase in blocked_phrases):
        raise RuntimeError("codex_cli returned an ungrounded context-unavailable response")


def _strict_agent_output_schema() -> dict[str, Any]:
    schema = AgentJobOutput.model_json_schema()
    action_props = schema.get("$defs", {}).get("ActionProposalSchema", {}).get("properties", {})
    action_props.pop("params", None)
    _make_strict_json_schema(schema)
    return schema


def _make_strict_json_schema(node: Any) -> None:
    if isinstance(node, dict):
        node.pop("default", None)
        node.pop("title", None)
        node.pop("description", None)
        if node.get("type") == "object":
            node["additionalProperties"] = False
            properties = node.get("properties")
            if isinstance(properties, dict):
                node["required"] = list(properties.keys())
        for value in node.values():
            _make_strict_json_schema(value)
    elif isinstance(node, list):
        for item in node:
            _make_strict_json_schema(item)
