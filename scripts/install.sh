#!/usr/bin/env bash
set -euo pipefail

echo "--- 1/3 Installing backend dependencies with uv ---"
uv sync --dev

echo
echo "--- 2/3 Installing Codex CLI runtime wheel for Linux ---"
uv pip install "openai-codex-cli-bin" \
  --python-platform x86_64-unknown-linux-musl

echo
echo "--- 3/3 Installing Codex SDK without re-resolving CLI runtime ---"
uv pip install "openai-codex>=0.1.0b2" --no-deps

echo
echo "Done."
echo "Next:"
echo "  cp .env.example .env"
echo "  uv run uvicorn app.main:app --reload"
