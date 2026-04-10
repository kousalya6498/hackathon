# Testing Guide

This guide reflects the current repository layout and scripts in `team_hackathon/`.

## What to verify

Before deployment or submission, we want to confirm:

- The server starts and exposes OpenEnv endpoints
- The baseline agent can complete all tasks
- `inference.py` can talk to both the model endpoint and the environment
- Scores stay inside the expected open interval `(0, 1)`

## Local setup

From the repo root:

```bash
cd hackathon/team_hackathon
uv sync
```

If you are not using `uv`, install the runtime dependencies from `requirements.txt`.

## Start the environment server

Recommended:

```bash
uv run server
```

Other equivalent commands:

```bash
uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload
python -m server.app
```

Expected healthy endpoint:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"healthy"}
```

## Run the built-in smoke test

The repo already includes a connection check script:

```bash
python3 test_connection.py
```

What it covers:

- `GET /health`
- `POST /reset`
- One stateful episode over WebSocket via `TeamHackathonEnv`

There is also a smaller debug helper:

```bash
python3 debug_step.py
```

## Manual endpoint checks

Reset:

```bash
curl -X POST http://localhost:8000/reset \
  -H "Content-Type: application/json" \
  -d '{}'
```

The environment supports `POST /step`, but for multi-step episode testing you should prefer the packaged client and WebSocket flow used by `TeamHackathonEnv`.

## Baseline verification

Run one deterministic pass over all tasks:

```bash
python3 baseline.py --episodes 3 --url http://localhost:8000
```

Save the results:

```bash
python3 baseline.py --episodes 3 --url http://localhost:8000 --output results.json
```

The checked-in `results.json` currently shows:

| Difficulty | Mean score |
| --- | --- |
| easy | 0.8725 |
| medium | 0.7317 |
| hard | 0.6889 |
| overall | 0.7644 |

Success rate: `1.0`

If your local run differs slightly after code changes, that is a sign to inspect scoring logic, task data, or action order assumptions.

## LLM inference verification

`inference.py` requires:

- `API_BASE_URL`
- `API_KEY`

Optional:

- `MODEL_NAME`
- `ENV_URL`
- `PIPELINE_TASK`
- `LOCAL_IMAGE_NAME`

Example against a remote-compatible OpenAI-style endpoint:

```bash
export API_BASE_URL="https://router.huggingface.co/v1"
export API_KEY="your_key_here"
export MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"
export ENV_URL="http://localhost:8000"

python3 inference.py
```

Run only one task:

```bash
export PIPELINE_TASK="medium_sync_failure"
python3 inference.py
```

Expected log format:

```text
[START] task=easy_api_delay env=pipeline_debugger model=Qwen/Qwen2.5-72B-Instruct
[STEP] step=1 action=check_api reward=0.10 done=false error=null
[STEP] step=2 action=check_metrics reward=0.08 done=false error=null
[STEP] step=3 action=retry_pipeline reward=0.87 done=true error=null
[END] success=true steps=3 score=0.872 rewards=0.10,0.08,0.87
```

## Task-specific checks

Easy task:

```bash
export PIPELINE_TASK="easy_api_delay"
python3 inference.py
```

Medium task:

```bash
export PIPELINE_TASK="medium_sync_failure"
python3 inference.py
```

Hard task:

```bash
export PIPELINE_TASK="hard_cascade_failure"
python3 inference.py
```

## Verification checklist

- [ ] `uv sync` completes successfully
- [ ] Server starts without import errors
- [ ] `/health` returns healthy
- [ ] `/reset` returns a valid observation payload
- [ ] `python3 test_connection.py` passes
- [ ] `python3 baseline.py --episodes 3 --url http://localhost:8000` completes
- [ ] Baseline scores remain in `(0, 1)`
- [ ] `python3 inference.py` emits `[START]`, `[STEP]`, and `[END]` lines
- [ ] All three tasks can be selected via `PIPELINE_TASK`

## Troubleshooting

### `ModuleNotFoundError: pydantic_core._pydantic_core`

This happened during verification in this workspace on April 10, 2026 when running `uv run server`.

Try:

```bash
uv sync
```

If the environment is still broken, remove and recreate the virtual environment, then sync again.

### Server does not respond on port 8000

Check whether something else is already bound:

```bash
lsof -i :8000
```

Then either stop that process or choose another port:

```bash
uvicorn server.app:app --port 8001
```

### Health check fails

Make sure the server process is still running, then retry:

```bash
curl http://localhost:8000/health
```

### Inference fails before the first step

`inference.py` performs an initial model call through the configured API endpoint. Double-check:

- `API_BASE_URL`
- `API_KEY`
- `MODEL_NAME`

### Wrong credential variable name

The current script expects `API_KEY`, not `HF_TOKEN`.

## Files involved in testing

- `server/app.py`
- `server/team_hackathon_environment.py`
- `client.py`
- `baseline.py`
- `inference.py`
- `debug_step.py`
- `test_connection.py`
- `metrics.py`
- `results.json`

## Suggested release flow

1. Run `uv sync`.
2. Start the server.
3. Run `python3 test_connection.py`.
4. Run `python3 baseline.py --episodes 3 --url http://localhost:8000 --output results.json`.
5. Run `python3 inference.py` against your chosen model endpoint.
6. Deploy with `openenv push --repo-id your-username/pipeline-debugger`.
