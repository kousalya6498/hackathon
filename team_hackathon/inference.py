"""
Inference Script for Pipeline Debugging Environment
===================================
MANDATORY
- Before submitting, ensure the following variables are defined in your environment configuration:
    API_BASE_URL   The API endpoint for the LLM.
    MODEL_NAME     The model identifier to use for inference.
    HF_TOKEN       Your Hugging Face / API key.
    LOCAL_IMAGE_NAME The name of the local image to use for the environment if you are using from_docker_image()
                     method

- Defaults are set only for API_BASE_URL and MODEL_NAME 
    (and should reflect your active inference setup):
    API_BASE_URL = os.getenv("API_BASE_URL", "<your-active-endpoint>")
    MODEL_NAME = os.getenv("MODEL_NAME", "<your-active-model>")
    
- The inference script must be named `inference.py` and placed in the root directory of the project
- Participants must use OpenAI Client for all LLM calls using above variables

STDOUT FORMAT
- The script must emit exactly three line types to stdout, in this order:

    [START] task=<task_name> env=<benchmark> model=<model_name>
    [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>

  Rules:
    - One [START] line at episode begin.
    - One [STEP] line per step, immediately after env.step() returns.
    - One [END] line after env.close(), always emitted (even on exception).
    - reward and rewards are formatted to 2 decimal places.
    - done and success are lowercase booleans: true or false.
    - error is the raw last_action_error string, or null if none.
    - All fields on a single line with no newlines within a line.
    - Each tasks should return score in [0, 1]

  Example:
    [START] task=easy_api_delay env=pipeline_debugger model=Qwen2.5-72B-Instruct
    [STEP] step=1 action=check_api reward=0.00 done=false error=null
    [STEP] step=2 action=check_metrics reward=0.00 done=false error=null
    [STEP] step=3 action=retry_pipeline reward=1.00 done=true error=null
    [END] success=true steps=3 score=0.95 rewards=0.00,0.00,1.00
"""

import asyncio
import os
import textwrap
from typing import List, Optional

from openai import OpenAI

from client import TeamHackathonEnv
from models import TeamHackathonAction

LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")
API_KEY = os.getenv("HF_TOKEN")

API_BASE_URL = os.getenv("API_BASE_URL") or "https://router.huggingface.co/v1"
MODEL_NAME = os.getenv("MODEL_NAME") or "Qwen/Qwen2.5-72B-Instruct"
TASK_NAME = os.getenv("PIPELINE_TASK")
BENCHMARK = os.getenv("PIPELINE_BENCHMARK", "pipeline_debugger")
MAX_STEPS = 12  # Maximum for hard task
TEMPERATURE = 0.0
MAX_TOKENS = 100
SUCCESS_SCORE_THRESHOLD = 0.5  # normalized score in [0, 1]
TASK_ORDER = ["easy_api_delay", "medium_sync_failure", "hard_cascade_failure"]

SYSTEM_PROMPT = textwrap.dedent(
    """
    You are a supply chain debugging expert. You are investigating a pipeline failure.
    
    Available diagnostic actions:
    - check_logs: Inspect inventory logs
    - check_api: Inspect API sync logs
    - check_metrics: Inspect latency metrics
    
    Available fix actions:
    - retry_pipeline: Retry failed operations
    - apply_batching: Apply batching to reduce load
    - fix_sync: Apply synchronization correction
    
    Strategy:
    1. First, diagnose the issue by checking relevant logs/metrics
    2. Then, apply appropriate fixes based on your diagnosis
    
    Reply with ONLY the action name (e.g., "check_api" or "retry_pipeline").
    No explanations, no quotes, just the action name.
    """
).strip()


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}", flush=True)


def build_user_prompt(step: int, obs, history: List[str]) -> str:
    history_block = "\n".join(history[-4:]) if history else "None"
    
    # Build context from observation
    context = f"""
Task: {obs.task_id} (Difficulty: {obs.task_difficulty})
Issue: {obs.issue_description}

Current State:
- Inventory lag: {obs.inventory_lag_score:.2f}
- Inventory errors: {obs.inventory_error_count:.2f}
- API response time: {obs.api_response_time:.2f}
- API errors: {obs.api_error_rate:.2f}
- Latency: {obs.latency_score:.2f}
- Network congestion: {obs.network_congestion:.2f}

Actions taken: {obs.actions_taken}
Last action: {obs.last_action or 'None'}
Last result: {obs.action_result or 'None'}

Hint: {obs.hints}

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

What action should you take next?
"""
    return context.strip()


def get_model_action(client: OpenAI, step: int, obs, history: List[str]) -> str:
    user_prompt = build_user_prompt(step, obs, history)
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            stream=False,
        )
        text = (completion.choices[0].message.content or "").strip()
        
        # Validate action
        valid_actions = ["check_logs", "check_api", "check_metrics", 
                        "retry_pipeline", "apply_batching", "fix_sync"]
        
        # Extract action from response
        for action in valid_actions:
            if action in text.lower():
                return action
        
        return "check_logs"
    except Exception:
        return "check_logs"


async def run_task(client: OpenAI, env: TeamHackathonEnv, task_name: str) -> None:
    history: List[str] = []
    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False

    log_start(task=task_name, env=BENCHMARK, model=MODEL_NAME)

    try:
        result = await env.reset(task_id=task_name)
        obs = result.observation

        for step in range(1, MAX_STEPS + 1):
            if result.done:
                break

            # Get action from model
            action_type = get_model_action(client, step, obs, history)

            # Take step
            result = await env.step(TeamHackathonAction(action_type=action_type))
            obs = result.observation

            reward = result.reward or 0.0
            done = result.done
            error = None

            rewards.append(reward)
            steps_taken = step

            log_step(step=step, action=action_type, reward=reward, done=done, error=error)

            history.append(f"Step {step}: {action_type} -> {obs.action_result}")

            if done:
                # Final score from observation
                score = obs.current_score
                success = obs.diagnosis_complete and obs.fix_applied
                break

        # If not done, calculate score from rewards
        if not result.done and len(rewards) > 0:
            score = sum(rewards) / len(rewards) if rewards else 0.0
            score = min(max(score, 0.0), 1.0)
        
        success = score >= SUCCESS_SCORE_THRESHOLD

    finally:
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)


async def main() -> None:
    try:
        if not API_KEY:
            raise RuntimeError("Missing API key. Set HF_TOKEN.")

        client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

        if LOCAL_IMAGE_NAME:
            env = await TeamHackathonEnv.from_docker_image(LOCAL_IMAGE_NAME)
        else:
            env_url = os.getenv("ENV_URL", "http://localhost:8000")
            env = TeamHackathonEnv(
                base_url=env_url,
                connect_timeout_s=10.0,
                message_timeout_s=20.0,
            )

        task_names = [TASK_NAME] if TASK_NAME else TASK_ORDER

        for task_name in task_names:
            await run_task(client, env, task_name)
    finally:
        try:
            await env.close()  # type: ignore[name-defined]
        except Exception:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        # Keep stdout compliant with the hackathon parser even if startup fails.
        log_end(success=False, steps=0, score=0.0, rewards=[])
