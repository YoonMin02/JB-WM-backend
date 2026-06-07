# Codex CLI 모델 벤치마크

이 문서는 로컬 Codex CLI에서 JB-WM agent job 후보 모델을 실제로 실행한 결과다.
측정은 작은 strict JSON 출력 작업으로 수행한다. 실제 금융 agent job은 context와 schema가 더 커서 더 오래 걸릴 수 있다.

- 실행 시각: `2026-06-07T12:07:46.281969+00:00`
- Codex 명령어: `codex`
- reasoning effort: `low`
- 원본 결과: [`benchmarks/codex_cli_models_20260607T120659Z.json`](benchmarks/codex_cli_models_20260607T120659Z.json)
- 안정적인 빠른 기본값: `AGENT_JOB_CODEX_MODEL=gpt-5.4-mini`
- 이번 측정의 최단 시간 후보: `gpt-5.3-codex-spark`

| 모델 | effort | 현재 계정에서 실행됨 | 시간 | 입력 토큰 | 출력 토큰 | 추론 토큰 |
|---|---|---:|---:|---:|---:|---:|
| gpt-5.4-mini | low | 예 | 9.496s | 18994 | 48 | 10 |
| gpt-5.5 | low | 예 | 12.39s | 20728 | 75 | 37 |
| gpt-5.3-codex-spark | low | 예 | 8.979s | 16626 | 91 | 38 |
| gpt-5-mini | low | 아니오 | 5.847s | - | - | - |
| gpt-5-nano | low | 아니오 | 3.547s | - | - | - |
| gpt-5.1-codex-mini | low | 아니오 | 3.198s | - | - | - |
| gpt-5.2-codex | low | 아니오 | 3.071s | - | - | - |

## 사용법

```bash
uv run python scripts/benchmark_codex_cli_models.py
```

특정 후보만 다시 측정:

```bash
uv run python scripts/benchmark_codex_cli_models.py --models gpt-5.4-mini,gpt-5.5 --effort low
```

## 런타임 플래그

```dotenv
AGENT_JOB_MODE=codex_cli
AGENT_JOB_CODEX_MODEL=gpt-5.4-mini
AGENT_JOB_CODEX_REASONING_EFFORT=low
```

## 해석

- `현재 계정에서 실행됨=예`는 현재 로그인/계정/CLI 조합에서 해당 model slug가 `codex exec`로 성공했다는 뜻이다.
- 토큰과 시간은 작은 스모크 작업 기준이다. 운영 판단은 실제 `context.json`/`output_schema.json`으로 한 번 더 측정해야 한다.
- `gpt-5.3-codex-spark`가 이번 스모크에서는 가장 빨랐지만 research preview/account 의존 후보이므로 기본값은 `gpt-5.4-mini`로 둔다.
- 모델 권한은 계정, 로그인 방식, Codex CLI 버전에 따라 바뀔 수 있으므로 배포 전에 다시 측정한다.

## 공식/실측 기준

- Codex manual은 `codex exec --model`로 non-interactive 실행 모델을 지정할 수 있다고 설명한다.
- Codex manual은 빠르고 낮은 비용 후보로 `gpt-5.4-mini`를, 강한 기본 후보로 `gpt-5.5`를 언급한다.
- `model_reasoning_effort`는 `minimal`, `low`, `medium`, `high`, `xhigh` 값을 지원한다.
- 이 repo의 기본값은 공식 설명만이 아니라 위 로컬 실측 성공 여부까지 함께 보고 정한다.
