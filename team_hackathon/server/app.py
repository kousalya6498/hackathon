# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
FastAPI application for the Team Hackathon Environment.

This module creates an HTTP server that exposes the TeamHackathonEnvironment
over HTTP and WebSocket endpoints, compatible with EnvClient.

Endpoints:
    - POST /reset: Reset the environment
    - POST /step: Execute an action
    - GET /state: Get current environment state
    - GET /schema: Get action/observation schemas
    - WS /ws: WebSocket endpoint for persistent sessions

Usage:
    # Development (with auto-reload):
    uvicorn server.app:app --reload --host 0.0.0.0 --port 8000

    # Production:
    uvicorn server.app:app --host 0.0.0.0 --port 8000 --workers 4

    # Or run directly:
    python -m server.app
"""

try:
    from openenv.core.env_server.http_server import create_app
except Exception as e:  # pragma: no cover
    raise ImportError(
        "openenv is required for the web interface. Install dependencies with '\n    uv sync\n'"
    ) from e

try:
    from team_hackathon.models import TeamHackathonAction, TeamHackathonObservation
    from .team_hackathon_environment import TeamHackathonEnvironment
except ModuleNotFoundError:
    from models import TeamHackathonAction, TeamHackathonObservation
    from server.team_hackathon_environment import TeamHackathonEnvironment

from fastapi.responses import HTMLResponse, JSONResponse


# Create the app with web interface and README integration
app = create_app(
    TeamHackathonEnvironment,
    TeamHackathonAction,
    TeamHackathonObservation,
    env_name="team_hackathon",
    max_concurrent_envs=8,
)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home() -> str:
    """Simple landing page for the deployed Hugging Face Space."""
    return """
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Pipeline Debugger</title>
        <style>
          :root {
            color-scheme: light;
            --bg: #f4f7fb;
            --card: #ffffff;
            --text: #16324f;
            --muted: #5d7285;
            --accent: #14866d;
            --accent-2: #0f5da8;
            --border: #d7e1ea;
          }
          body {
            margin: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: linear-gradient(135deg, #eef5ff, #f7fbf8);
            color: var(--text);
          }
          .wrap {
            max-width: 860px;
            margin: 48px auto;
            padding: 0 20px;
          }
          .card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 28px;
            box-shadow: 0 12px 40px rgba(19, 44, 74, 0.08);
          }
          h1 {
            margin: 0 0 12px;
            font-size: 2rem;
          }
          p {
            color: var(--muted);
            line-height: 1.6;
          }
          .links {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            margin-top: 20px;
          }
          a {
            text-decoration: none;
            padding: 10px 14px;
            border-radius: 10px;
            border: 1px solid var(--border);
            color: var(--accent-2);
            background: #f8fbff;
            font-weight: 600;
          }
          .badge {
            display: inline-block;
            margin-bottom: 12px;
            padding: 6px 10px;
            border-radius: 999px;
            background: #e7f7f3;
            color: var(--accent);
            font-size: 0.9rem;
            font-weight: 700;
          }
            code {
            background: #f3f6f8;
            padding: 2px 6px;
            border-radius: 6px;
          }
          pre {
            margin-top: 18px;
            padding: 16px;
            overflow-x: auto;
            border-radius: 14px;
            border: 1px solid var(--border);
            background: #0f1b2a;
            color: #e8f0f8;
            line-height: 1.5;
          }
          .detail-list {
            color: var(--muted);
            line-height: 1.6;
            margin-top: 18px;
          }
          .detail-list strong {
            color: var(--text);
          }
          .subtle {
            margin-top: 18px;
            font-size: 0.96rem;
          }
        </style>
      </head>
      <body>
        <div class="wrap">
          <div class="card">
            <div class="badge">OpenEnv Space Running</div>
            <h1>Pipeline Debugging Environment</h1>
            <p>
              This environment simulates real supply-chain incident response for inventory and
              warehouse synchronization systems. An agent investigates operational evidence across
              API behavior, inventory pipeline drift, and infrastructure metrics, then chooses the
              right remediation before fulfillment accuracy and downstream operations degrade.
            </p>
            <p>
              The benchmark includes three escalating scenarios: a recoverable API slowdown,
              a warehouse sync mismatch, and a cascading multi-signal failure that requires
              coordinated diagnosis. Rewards reflect partial progress, redundant actions are
              penalized, and final scores are normalized to <code>[0, 1]</code>.
            </p>
            <div class="links">
              <a href="/docs">API Docs</a>
              <a href="/health">Health Check</a>
              <a href="/example-output">Example Output</a>
            </div>
            <div class="detail-list">
              <strong>Primary use case:</strong> evaluate whether an agent can diagnose and fix
              production-like supply-chain failures using evidence instead of guesswork.
            </div>
            <pre>API_KEY=your_key \
API_BASE_URL=https://router.huggingface.co/v1 \
MODEL_NAME=Qwen/Qwen2.5-72B-Instruct \
PIPELINE_TASK=hard_cascade_failure \
ENV_URL=http://localhost:8000 \
venv/bin/python -u inference.py</pre>
            <div class="subtle">
              Explore the interactive schema in <code>/docs</code>, verify deployment health,
              open a sample structured run transcript from the example output endpoint, or copy the
              command above to test the environment locally against a running server.
            </div>
          </div>
        </div>
      </body>
    </html>
    """


@app.get("/example-output", response_class=JSONResponse, include_in_schema=False)
async def example_output() -> JSONResponse:
    """Read-only example of the inference log format used in evaluation."""
    return JSONResponse(
        {
            "description": "Sample structured stdout from inference.py",
            "local_test_command": [
                "API_KEY=your_key \\",
                "API_BASE_URL=https://router.huggingface.co/v1 \\",
                "MODEL_NAME=Qwen/Qwen2.5-72B-Instruct \\",
                "PIPELINE_TASK=hard_cascade_failure \\",
                "ENV_URL=http://localhost:8000 \\",
                "venv/bin/python -u inference.py",
            ],
            "lines": [
                "[START] task=easy_api_delay env=pipeline_debugger model=Qwen/Qwen2.5-72B-Instruct",
                "[STEP] step=1 action=check_api reward=0.10 done=false error=null",
                "[STEP] step=2 action=check_metrics reward=0.08 done=false error=null",
                "[STEP] step=3 action=retry_pipeline reward=0.87 done=true error=null",
                "[END] success=true steps=3 score=0.872 rewards=0.10,0.08,0.87",
            ],
            "note": "This endpoint is illustrative only. Real evaluation output is produced when inference.py is executed by the validator.",
        }
    )


def main(host: str = "0.0.0.0", port: int = 8000):
    """
    Entry point for direct execution via uv run or python -m.

    This function enables running the server without Docker:
        uv run --project . server
        uv run --project . server --port 8001
        python -m team_hackathon.server.app

    Args:
        host: Host address to bind to (default: "0.0.0.0")
        port: Port number to listen on (default: 8000)

    For production deployments, consider using uvicorn directly with
    multiple workers:
        uvicorn team_hackathon.server.app:app --workers 4
    """
    import uvicorn

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.port == 8000:
        main()
    else:
        main(port=args.port)
