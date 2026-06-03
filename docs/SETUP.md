# SETUP · 개발 환경 구성 (WSL/Ubuntu)

시스템 도구는 전역 1회 설치, 프로젝트 의존성은 venv에 설치합니다.

## 1. 시스템 도구 (1회)

```bash
# Node.js (Codex CLI용) — nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
source ~/.nvm/nvm.sh
nvm install --lts

# Codex CLI (OAuth 로그인 담당)
npm install -g @openai/codex@latest
codex --version

# uv (Python 패키지 매니저)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.local/bin/env

# PostgreSQL
sudo apt-get install -y postgresql postgresql-contrib
sudo service postgresql start
sudo -u postgres psql -c "CREATE USER jbwm WITH PASSWORD 'jbwm';"
sudo -u postgres psql -c "CREATE DATABASE jbwm_dev OWNER jbwm;"

# Codex OAuth (1회)
codex login
```

`~/.bashrc`에 nvm·uv 로더가 추가됩니다 (새 터미널 자동 로드). PostgreSQL은 WSL에서 자동 시작이 안 되므로 재시작마다 `sudo service postgresql start`.

## 2. 백엔드 의존성

```bash
bash scripts/install.sh
source .venv/bin/activate
python -c "from openai_codex import AsyncCodex; print('OK')"
```

> **openai-codex-cli-bin (glibc Linux 우회):** Codex SDK 의존성 `openai-codex-cli-bin`은 musl 정적 바이너리로만 배포되어, Ubuntu/WSL pip/uv의 일반 resolver가 자동 선택하지 못합니다. `scripts/install.sh`가 일반 Python 의존성을 먼저 설치한 뒤, CLI 바이너리만 `--python-platform x86_64-unknown-linux-musl`로 설치하고, 마지막에 `openai-codex` SDK를 `--no-deps`로 설치합니다. (정적 빌드라 glibc에서도 실행됨)

## 3. 환경변수

```bash
cp .env.example .env
```

`DATABASE_URL` 확인. Codex는 OAuth 세션을 쓰므로 `OPENAI_API_KEY` 불필요. 자세히는 [ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md).

## 4. 실행

```bash
source .venv/bin/activate
uvicorn app.main:app --reload   # GET /health
pytest
```

일반 개발 테스트만 빠르게 돌릴 때는 아래도 동작해야 합니다.

```bash
uv run pytest -q
```

실제 SDK 연동 smoke test는 OAuth/session 대기에서 오래 멈출 수 있으므로 shell timeout을 씁니다.

```bash
timeout 120s .venv/bin/python scripts/codex_smoke_test.py
```

## 버전 확인 체크리스트

```bash
node --version     # v18+ (LTS 권장)
uv --version
codex --version    # codex-cli x.x.x
psql --version     # PostgreSQL 16+
python -c "from openai_codex import AsyncCodex; print('OK')"
```
