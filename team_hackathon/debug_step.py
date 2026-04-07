"""Quick debug script for a single reset + step over the OpenEnv WebSocket client."""

import asyncio
import json
import sys
from pathlib import Path

PACKAGE_PARENT = Path(__file__).resolve().parent.parent
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))

from team_hackathon.client import TeamHackathonEnv
from team_hackathon.models import TeamHackathonAction


BASE_URL = "http://localhost:8000"


async def main() -> None:
    env = TeamHackathonEnv(
        base_url=BASE_URL,
        connect_timeout_s=10.0,
        message_timeout_s=15.0,
    )

    try:
        print("1. Resetting environment...")
        reset_result = await env.reset()
        print(f"Reset task: {reset_result.observation.task_id}")
        print(f"Difficulty: {reset_result.observation.task_difficulty}\n")

        print("2. Taking a step...")
        step_result = await env.step(TeamHackathonAction(action_type="check_logs"))

        payload = {
            "observation": step_result.observation.model_dump(),
            "reward": step_result.reward,
            "done": step_result.done,
        }

        print("=" * 60)
        print("STEP RESPONSE:")
        print("=" * 60)
        print(json.dumps(payload, indent=2))
        print("=" * 60)
        print(f"\nResponse keys: {list(payload.keys())}")
        print(f"Has 'observation' key: {'observation' in payload}")
    finally:
        await env.close()


if __name__ == "__main__":
    asyncio.run(main())

# Made with Bob
