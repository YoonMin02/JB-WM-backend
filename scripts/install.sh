#!/usr/bin/env bash
# JB WM 백엔드 환경 구성 (Ubuntu / WSL2, glibc Linux).
#
# openai-codex-cli-bin은 musl-static 바이너리로만 배포되어 glibc Ubuntu에서
# pip/uv가 자동 선택하지 못한다. 전체 패키지를 musl 플랫폼 플래그로 설치한 뒤,
# 네이티브 C 확장이 있는 pydantic-core만 manylinux 휠로 재설치한다.
# (cli-bin은 정적 빌드라 glibc에서도 실행됨 — 검증 완료)

set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BACKEND_DIR"

echo "--- 1/3  가상환경 생성 ---"
uv venv --clear

echo "--- 2/3  패키지 설치 (cli-bin용 musl 플랫폼) ---"
uv pip install \
    "openai-codex>=0.1.0b2" \
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
    "ruff>=0.8" \
    --python-platform x86_64-unknown-linux-musl \
    --only-binary :all:

echo "--- 3/3  pydantic / pydantic-core를 manylinux 휠로 재설치 ---"
# pydantic-core는 런타임(glibc)과 맞는 .so가 필요. 위에서 깔린 musl 버전은 로드 불가.
# --upgrade가 아니라 쌍으로 --reinstall 해서 pydantic 핀과 호환되는 버전을 받는다.
uv pip install --reinstall pydantic pydantic-core

echo ""
echo "완료. 활성화:  source .venv/bin/activate"
echo "검증:        python -c \"from openai_codex import AsyncCodex; print('OK')\""
