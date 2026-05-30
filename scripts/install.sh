#!/usr/bin/env bash
# JB WM 백엔드 환경 구성 (Ubuntu / WSL2, glibc Linux).
#
# 근본 원인: openai-codex의 런타임 의존 `openai-codex-cli-bin`은 musl-static
# 바이너리로만 배포되어, glibc Ubuntu에서 pip/uv가 자동 선택하지 못한다.
# (정적 빌드라 glibc에서도 실행됨 — 검증 완료)
#
# 해결: musl 전용인 cli-bin '하나만' musl 플랫폼으로 설치하고, 나머지 패키지
# (pydantic-core 등 네이티브 확장 포함)는 전부 정상 glibc 휠로 설치한다.
# → 재설치 같은 사후 보정이 필요 없다.

set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BACKEND_DIR"

echo "--- 1/4  가상환경 생성 ---"
uv venv --clear

echo "--- 2/4  일반 의존성 설치 (glibc 네이티브 휠) ---"
uv pip install \
    "fastapi>=0.115" \
    "uvicorn[standard]>=0.32" \
    "sqlmodel>=0.0.22" \
    "alembic>=1.14" \
    "pydantic>=2.12" \
    "pydantic-settings>=2.7" \
    "python-dotenv>=1.0" \
    "httpx>=0.28" \
    "psycopg2-binary>=2.9" \
    "pytest>=8" \
    "pytest-asyncio>=0.24" \
    "ruff>=0.8"

echo "--- 3/4  Codex CLI 바이너리만 musl 휠로 설치 ---"
uv pip install "openai-codex-cli-bin" \
    --python-platform x86_64-unknown-linux-musl \
    --only-binary :all: \
    --no-deps

echo "--- 4/4  openai-codex SDK 설치 (의존성은 위에서 충족 → --no-deps) ---"
uv pip install "openai-codex>=0.1.0b2" --no-deps

echo ""
echo "완료. 활성화:  source .venv/bin/activate"
echo "검증:        python -c \"from openai_codex import AsyncCodex; import fastapi, sqlmodel; print('OK')\""
