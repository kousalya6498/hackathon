---
title: Pipeline Debugger
emoji: "🛠️"
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# Pipeline Debugging Environment

An OpenEnv environment for evaluating agents on supply-chain incident response. Each episode asks the agent to investigate operational evidence, diagnose the failure mode, and choose the right remediation action.

## What is in this repo

- 3 deterministic tasks with increasing difficulty
- A FastAPI/OpenEnv server
- A packaged Python client for reset/step interaction
- A rule-based baseline agent
- An LLM-driven `inference.py` script that emits validator-friendly logs
- Transparent scoring logic in `metrics.py`

## Tasks

| Task | Difficulty | Description | Max steps |
| --- | --- | --- | --- |
| `easy_api_delay` | easy | Elevated API latency with a recoverable pipeline delay | 8 |
| `medium_sync_failure` | medium | Warehouse and central inventory drift out of sync | 10 |
| `hard_cascade_failure` | hard | Multi-signal cascading failure across logs, API, and metrics | 12 |

## Action space

Diagnostic actions:

- `check_logs`
- `check_api`
- `check_metrics`

Fix actions:

- `retry_pipeline`
- `apply_batching`
- `fix_sync`

## Observation highlights

Each observation includes:

- Task metadata: `task_id`, `task_difficulty`, `issue_description`
- Operational indicators: inventory lag, API error rate, latency, congestion
- Evidence strings: inventory log excerpt, API log excerpt, metrics summary, business impact summary
- Episode progress: `step_count`, `max_steps`, `actions_taken`
- Outcome state: `diagnosis_complete`, `fix_applied`, `done`
- Current normalized score: strictly inside `(0, 1)`

## Scoring

Scoring combines:

- Correctness: 70%
- Efficiency: 30%

The implementation lives in `metrics.py`, and `openenv.yaml` declares the normalized scoring range as `(0,1)`.

## Project structure

```text
team_hackathon/
├── __init__.py
├── baseline.py
├── client.py
├── data/
│   └── sample_logs.json
├── debug_step.py
├── inference.py
├── metrics.py
├── models.py
├── openenv.yaml
├── pyproject.toml
├── results.json
├── server/
│   ├── __init__.py
│   ├── app.py
│   └── team_hackathon_environment.py
├── test_connection.py
├── TESTING_GUIDE.md
└── README.md
```

## Install

```bash
uv sync
```

If you prefer `pip`, the main runtime dependencies are listed in `requirements.txt`.

## Run the server

Recommended:

```bash
uv run server
```

Equivalent options:

```bash
uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload
python -m server.app
```

## Smoke test the server

HTTP sanity checks:

```bash
python3 test_connection.py
```

Single reset + step debug run:

```bash
python3 debug_step.py
```

## Use the Python client

```python
from team_hackathon import TeamHackathonEnv, TeamHackathonAction

async with TeamHackathonEnv(base_url="http://localhost:8000") as env:
    result = await env.reset(task_id="easy_api_delay")
    obs = result.observation

    while not result.done:
        action = TeamHackathonAction(action_type="check_api")
        result = await env.step(action)
        obs = result.observation
        print(obs.action_result, obs.current_score)
```

## Run the baseline

```bash
python3 baseline.py --episodes 3 --url http://localhost:8000
python3 baseline.py --episodes 3 --url http://localhost:8000 --output results.json
```

The checked-in `results.json` records one deterministic pass over all three tasks:

| Difficulty | Mean score |
| --- | --- |
| easy | 0.8725 |
| medium | 0.7317 |
| hard | 0.6889 |
| overall | 0.7644 |

Success rate in that run: 100%.

## Run LLM inference

`inference.py` requires `API_BASE_URL` and `API_KEY`.

Example:

```bash
export API_BASE_URL="https://router.huggingface.co/v1"
export API_KEY="your_key_here"
export MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"
export ENV_URL="http://localhost:8000"

python3 inference.py
```

To run a single task:

```bash
export PIPELINE_TASK="hard_cascade_failure"
python3 inference.py
```

The script emits structured lines like:

```text
[START] task=easy_api_delay env=pipeline_debugger model=Qwen/Qwen2.5-72B-Instruct
[STEP] step=1 action=check_api reward=0.10 done=false error=null
[STEP] step=2 action=check_metrics reward=0.08 done=false error=null
[STEP] step=3 action=retry_pipeline reward=0.87 done=true error=null
[END] success=true steps=3 score=0.872 rewards=0.10,0.08,0.87
```

## Deployment

For OpenEnv deployment metadata, see `openenv.yaml`.

To push to Hugging Face Spaces:

```bash
openenv push --repo-id your-username/pipeline-debugger
```

## Current note on local setup

During a fresh verification pass in this workspace on April 10, 2026, `uv run server` failed because the local virtual environment was missing `pydantic_core`. If you hit a similar error, rebuild or resync the environment first:

```bash
uv sync
```

For a more detailed verification workflow and troubleshooting notes, see `TESTING_GUIDE.md`.
