"""
Inference Script for Pipeline Debugging Environment.

This file is intended for hackathon evaluation and follows the required
structured stdout format.
"""

import asyncio
import os
import sys
import textwrap
from typing import List, Optional

from openai import OpenAI

from client import TeamHackathonEnv
from models import TeamHackathonAction

LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")
API_BASE_URL = os.getenv("API_BASE_URL") or "https://router.huggingface.co/v1"
MODEL_NAME = os.getenv("MODEL_NAME") or "Qwen/Qwen2.5-72B-Instruct"
API_KEY = os.getenv("API_KEY") or os.getenv("HF_TOKEN")
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


def require_validator_env() -> None:
    if "API_BASE_URL" not in os.environ:
        raise RuntimeError("Missing API_BASE_URL.")
    if "API_KEY" not in os.environ and "HF_TOKEN" not in os.environ:
        raise RuntimeError("Missing API_KEY.")


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

    log_start(task_name, BENCHMARK, MODEL_NAME)

    try:
        result = await env.reset(task_id=task_name)
        obs = result.observation

        for step in range(1, MAX_STEPS + 1):
            if result.done:
                break

            action_type = get_model_action(client, obs, history)
            result = await env.step(TeamHackathonAction(action_type=action_type))
            obs = result.observation

            reward = result.reward or 0.0
            rewards.append(reward)
            steps_taken = step

            log_step(step, action_type, reward, result.done, None)
            history.append(f"Step {step}: {action_type} -> {obs.action_result}")

            if result.done:
                score = obs.current_score
                success = obs.diagnosis_complete and obs.fix_applied
                break

        if not result.done and rewards:
            score = min(max(sum(rewards) / len(rewards), 0.0), 1.0)
        success = score >= SUCCESS_SCORE_THRESHOLD
    finally:
        log_end(success, steps_taken, score, rewards)


async def main() -> None:
    require_validator_env()
    if not API_KEY:
        raise RuntimeError("Missing API key. Set API_KEY.")

    # Important: use the injected validator proxy values directly.
    client = OpenAI(base_url=os.environ["API_BASE_URL"], api_key=os.environ.get("API_KEY", API_KEY))

    if LOCAL_IMAGE_NAME:
        env = await TeamHackathonEnv.from_docker_image(LOCAL_IMAGE_NAME)
    else:
        env = TeamHackathonEnv(
            base_url=ENV_URL,
            connect_timeout_s=10.0,
            message_timeout_s=20.0,
        )

    task_names = [TASK_NAME] if TASK_NAME else TASK_ORDER

    try:
        for task_name in task_names:
            await run_task(client, env, task_name)
    finally:
        try:
            await env.close()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        log_end(success=False, steps=0, score=0.0, rewards=[])
        sys.exit(1)
