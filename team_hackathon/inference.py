"""
Inference Script for Pipeline Debugging Environment.

This file is intended for hackathon evaluation and follows the required
structured stdout format.
"""

import asyncio
import os
import textwrap
from pathlib import Path
from typing import List, Optional

IMPORT_ERROR: Optional[Exception] = None

try:
    from openai import OpenAI
except Exception as exc:
    OpenAI = None  # type: ignore[assignment]
    IMPORT_ERROR = exc

try:
    from client import TeamHackathonEnv
    from models import TeamHackathonAction
except Exception as exc:
    TeamHackathonEnv = None  # type: ignore[assignment]
    TeamHackathonAction = None  # type: ignore[assignment]
    IMPORT_ERROR = IMPORT_ERROR or exc

LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")
MODEL_NAME = os.getenv("MODEL_NAME") or "Qwen/Qwen2.5-72B-Instruct"
TASK_NAME = os.getenv("PIPELINE_TASK")
BENCHMARK = os.getenv("PIPELINE_BENCHMARK", "pipeline_debugger")
ENV_URL = os.getenv("ENV_URL", "http://localhost:8000")
MAX_STEPS = 12
TEMPERATURE = 0.0
MAX_TOKENS = 100
SUCCESS_SCORE_THRESHOLD = 0.5
TASK_ORDER = ["easy_api_delay", "medium_sync_failure", "hard_cascade_failure"]
VALID_ACTIONS = [
    "check_logs",
    "check_api",
    "check_metrics",
    "retry_pipeline",
    "apply_batching",
    "fix_sync",
]

SYSTEM_PROMPT = textwrap.dedent(
    """
    You are a supply chain debugging expert investigating a pipeline failure.

    Rules:
    - Reply with exactly one valid action name.
    - Diagnose before fixing.
    - Use the evidence in the observation.

    Valid actions:
    check_logs
    check_api
    check_metrics
    retry_pipeline
    apply_batching
    fix_sync
    """
).strip()


def load_dotenv_file() -> None:
    env_path = Path(__file__).with_name(".env")
    if not env_path.exists():
        return

    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not key:
            continue

        if "#" in value and not value.startswith(("'", '"')):
            value = value.split("#", 1)[0].strip()

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        os.environ.setdefault(key, value)


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={str(done).lower()} error={error or 'null'}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={','.join(f'{r:.2f}' for r in rewards)}",
        flush=True,
    )


def build_user_prompt(obs, history: List[str]) -> str:
    history_block = "\n".join(history[-4:]) if history else "None"
    return textwrap.dedent(
        f"""
        Task: {obs.task_id} (Difficulty: {obs.task_difficulty})
        Issue: {obs.issue_description}

        Current State:
        - Inventory lag: {obs.inventory_lag_score:.2f}
        - Inventory errors: {obs.inventory_error_count:.2f}
        - API response time: {obs.api_response_time:.2f}
        - API errors: {obs.api_error_rate:.2f}
        - Latency: {obs.latency_score:.2f}
        - Network congestion: {obs.network_congestion:.2f}

        Hint:
        {obs.hints}

        Business impact:
        {obs.business_impact_summary or 'None'}

        Inventory evidence:
        {obs.inventory_log_excerpt or 'None'}

        API evidence:
        {obs.api_log_excerpt or 'None'}

        Metrics evidence:
        {obs.metrics_summary or 'None'}

        Previous steps:
        {history_block}

        Return exactly one valid action.
        """
    ).strip()


def extract_actions(history: List[str]) -> List[str]:
    taken: List[str] = []
    for item in history:
        for action in VALID_ACTIONS:
            if action in item:
                taken.append(action)
    return taken


def fallback_action(obs, history: List[str]) -> str:
    taken = extract_actions(history)
    if obs.task_id == "easy_api_delay":
        order = ["check_api", "check_metrics", "retry_pipeline", "check_logs", "apply_batching", "fix_sync"]
    elif obs.task_id == "medium_sync_failure":
        order = ["check_logs", "check_api", "fix_sync", "retry_pipeline", "check_metrics", "apply_batching"]
    else:
        order = ["check_logs", "check_api", "check_metrics", "retry_pipeline", "apply_batching", "fix_sync"]

    for action in order:
        if action not in taken:
            return action
    return "retry_pipeline"


def get_model_action(client: OpenAI, obs, history: List[str]) -> str:
    completion = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(obs, history)},
        ],
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        stream=False,
    )
    text = (completion.choices[0].message.content or "").strip().lower()

    for action in VALID_ACTIONS:
        if action in text:
            return action
    return fallback_action(obs, history)


async def run_task(client: OpenAI, env: TeamHackathonEnv, task_name: str) -> None:
    history: List[str] = []
    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False
    last_error: Optional[str] = None

    log_start(task_name, BENCHMARK, MODEL_NAME)

    try:
        result = await env.reset(task_id=task_name)
        obs = result.observation

        for step in range(1, MAX_STEPS + 1):
            if result.done:
                break

            try:
                action_type = get_model_action(client, obs, history)
            except Exception as exc:
                last_error = str(exc).replace("\n", " ").strip() or exc.__class__.__name__
                action_type = fallback_action(obs, history)

            try:
                result = await env.step(TeamHackathonAction(action_type=action_type))
            except Exception as exc:
                last_error = str(exc).replace("\n", " ").strip() or exc.__class__.__name__
                log_step(step, action_type, 0.0, True, last_error)
                break

            obs = result.observation

            reward = result.reward or 0.0
            rewards.append(reward)
            steps_taken = step

            log_step(step, action_type, reward, result.done, last_error)
            history.append(f"Step {step}: {action_type} -> {obs.action_result}")
            last_error = None

            if result.done:
                score = obs.current_score
                success = obs.diagnosis_complete and obs.fix_applied
                break

        if not result.done and rewards:
            score = min(max(sum(rewards) / len(rewards), 0.0), 1.0)
        success = score >= SUCCESS_SCORE_THRESHOLD
    except Exception:
        success = False
    finally:
        log_end(success, steps_taken, score, rewards)


async def main() -> None:
    load_dotenv_file()

    if IMPORT_ERROR is not None:
        raise RuntimeError(str(IMPORT_ERROR))

    env: Optional[TeamHackathonEnv] = None
    api_base_url = require_env("API_BASE_URL")
    api_key = require_env("API_KEY")
    client = OpenAI(base_url=api_base_url, api_key=api_key)

    try:
        if LOCAL_IMAGE_NAME:
            env = await TeamHackathonEnv.from_docker_image(LOCAL_IMAGE_NAME)
        else:
            env = TeamHackathonEnv(
                base_url=ENV_URL,
                connect_timeout_s=10.0,
                message_timeout_s=20.0,
            )

        task_names = [TASK_NAME] if TASK_NAME else TASK_ORDER

        for task_name in task_names:
            await run_task(client, env, task_name)
    finally:
        if env is not None:
            try:
                await env.close()
            except Exception:
                pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(f"[ERROR] {exc}", flush=True)
        log_end(success=False, steps=0, score=0.0, rewards=[])
