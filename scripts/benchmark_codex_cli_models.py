"""Benchmark candidate Codex CLI models for JB-WM agent jobs.

This script intentionally runs tiny `codex exec` jobs. It checks whether a
model slug is accepted by the local Codex CLI/auth setup and records rough
wall-clock latency for a strict JSON output task.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_MODELS = (
    "gpt-5.4-mini",
    "gpt-5.5",
    "gpt-5.3-codex-spark",
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-5.1-codex-mini",
    "gpt-5.2-codex",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--codex-command", default=os.getenv("CODEX_COMMAND", "codex"))
    parser.add_argument(
        "--models",
        default=os.getenv("AGENT_JOB_CODEX_MODEL_CANDIDATES", ",".join(DEFAULT_MODELS)),
        help="Comma-separated model candidates.",
    )
    parser.add_argument(
        "--effort",
        default=os.getenv("AGENT_JOB_CODEX_REASONING_EFFORT", "low"),
        help="Codex model_reasoning_effort override. Use an empty string to omit it.",
    )
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--output-root", default="storage/codex_cli_model_benchmarks")
    parser.add_argument("--markdown", default="docs/redesign/codex_cli_model_benchmark.md")
    args = parser.parse_args()

    models = [model.strip() for model in args.models.split(",") if model.strip()]
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    schema = {
        "type": "object",
        "properties": {
            "ok": {"type": "boolean"},
            "model_candidate": {"type": "string"},
            "message": {"type": "string"},
        },
        "required": ["ok", "model_candidate", "message"],
        "additionalProperties": False,
    }

    results = []
    for model in models:
        results.append(run_candidate(args.codex_command, model, args.effort, args.timeout, run_dir, schema))

    result_payload = {
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "codex_command": args.codex_command,
        "effort": args.effort,
        "results": results,
    }
    result_path = run_dir / "results.json"
    result_path.write_text(json.dumps(result_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    markdown_path = Path(args.markdown)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_markdown(result_payload, result_path), encoding="utf-8")

    print(json.dumps(result_payload, ensure_ascii=False, indent=2))
    print(f"\nWrote {result_path}")
    print(f"Wrote {markdown_path}")
    return 0


def run_candidate(
    codex_command: str,
    model: str,
    effort: str,
    timeout: int,
    run_dir: Path,
    schema: dict[str, Any],
) -> dict[str, Any]:
    safe_name = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in model)
    model_dir = run_dir / safe_name
    model_dir.mkdir(parents=True, exist_ok=True)
    schema_path = model_dir / "schema.json"
    output_path = model_dir / "output.json"
    schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")

    prompt = (
        "Return only JSON matching schema.json. "
        f'Set ok=true, model_candidate="{model}", and message to a short Korean sentence.'
    )
    cmd = [
        codex_command,
        "exec",
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
        "--ephemeral",
        "--color",
        "never",
        "--json",
        "--model",
        model,
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(output_path),
        "-C",
        str(model_dir),
    ]
    if effort:
        cmd.extend(["-c", f'model_reasoning_effort="{effort}"'])
    cmd.append(prompt)

    started_at = time.perf_counter()
    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=timeout,
        check=False,
    )
    duration = round(time.perf_counter() - started_at, 3)
    usage = parse_usage(completed.stdout)
    output_json = read_json(output_path)
    ok = completed.returncode == 0 and isinstance(output_json, dict) and output_json.get("ok") is True

    return {
        "model": model,
        "effort": effort or None,
        "supported": ok,
        "returncode": completed.returncode,
        "duration_seconds": duration,
        "output_bytes": output_path.stat().st_size if output_path.exists() else 0,
        "usage": usage,
        "output_json": output_json,
        "stderr_tail": completed.stderr[-1200:],
        "stdout_tail": completed.stdout[-1200:],
    }


def parse_usage(stdout: str) -> dict[str, Any] | None:
    usage = None
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("type") == "turn.completed":
            usage = event.get("usage")
    return usage


def read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return path.read_text(encoding="utf-8")[-1200:]


def render_markdown(payload: dict[str, Any], result_path: Path) -> str:
    rows = []
    for row in payload["results"]:
        usage = row.get("usage") or {}
        rows.append(
            "| {model} | {effort} | {supported} | {duration}s | {input_tokens} | {output_tokens} | {reasoning_tokens} |".format(
                model=row["model"],
                effort=row.get("effort") or "-",
                supported="yes" if row["supported"] else "no",
                duration=row["duration_seconds"],
                input_tokens=usage.get("input_tokens", "-"),
                output_tokens=usage.get("output_tokens", "-"),
                reasoning_tokens=usage.get("reasoning_output_tokens", "-"),
            )
        )

    fastest = sorted(
        [row for row in payload["results"] if row["supported"]],
        key=lambda row: row["duration_seconds"],
    )
    supported_models = {row["model"] for row in payload["results"] if row["supported"]}
    recommended = "gpt-5.4-mini" if "gpt-5.4-mini" in supported_models else (fastest[0]["model"] if fastest else "none")
    fastest_model = fastest[0]["model"] if fastest else "none"
    return "\n".join(
        [
            "# Codex CLI Model Benchmark",
            "",
            "이 문서는 로컬 Codex CLI에서 JB-WM agent job 후보 모델을 실제로 실행한 결과다.",
            "측정은 작은 strict JSON 출력 작업으로 수행한다. 실제 금융 agent job은 context와 schema가 더 커서 더 오래 걸릴 수 있다.",
            "",
            f"- 실행 시각: `{payload['created_at']}`",
            f"- Codex command: `{payload['codex_command']}`",
            f"- Reasoning effort: `{payload['effort'] or 'not set'}`",
            f"- Raw result: `{result_path}`",
            f"- 안정 fast flag: `AGENT_JOB_CODEX_MODEL={recommended}`",
            f"- 이번 측정 fastest: `{fastest_model}`",
            "",
            "| Model | Effort | Supported | Duration | Input tokens | Output tokens | Reasoning tokens |",
            "|---|---|---:|---:|---:|---:|---:|",
            *rows,
            "",
            "## 사용법",
            "",
            "```bash",
            "uv run python scripts/benchmark_codex_cli_models.py",
            "```",
            "",
            "특정 후보만 다시 측정:",
            "",
            "```bash",
            "uv run python scripts/benchmark_codex_cli_models.py --models gpt-5.4-mini,gpt-5.5 --effort low",
            "```",
            "",
            "## 런타임 플래그",
            "",
            "```dotenv",
            "AGENT_JOB_MODE=codex_cli",
            f"AGENT_JOB_CODEX_MODEL={recommended}",
            f"AGENT_JOB_CODEX_REASONING_EFFORT={payload['effort'] or 'low'}",
            "```",
            "",
            "## 해석",
            "",
            "- `Supported=yes`는 현재 로그인/계정/CLI 조합에서 해당 model slug가 `codex exec`로 성공했다는 뜻이다.",
            "- 토큰과 시간은 작은 스모크 작업 기준이다. 운영 판단은 실제 `context.json`/`output_schema.json`으로 한 번 더 측정해야 한다.",
            "- 모델 권한은 계정, 로그인 방식, Codex CLI 버전에 따라 바뀔 수 있으므로 배포 전에 다시 측정한다.",
            "",
            "## 공식 기준",
            "",
            "- Codex manual은 `codex exec --model`로 non-interactive 실행 모델을 지정할 수 있다고 설명한다.",
            "- Codex manual은 빠르고 낮은 비용 후보로 `gpt-5.4-mini`를, 강한 기본 후보로 `gpt-5.5`를 언급한다.",
            "- `model_reasoning_effort`는 `minimal`, `low`, `medium`, `high`, `xhigh` 값을 지원한다.",
            "",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
