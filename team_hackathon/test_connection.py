"""Simple diagnostic script to test the running environment server."""

import asyncio
import sys
from pathlib import Path

import requests

PACKAGE_PARENT = Path(__file__).resolve().parent.parent
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))

from team_hackathon.client import TeamHackathonEnv
from team_hackathon.models import TeamHackathonAction


BASE_URL = "http://localhost:8000"


def test_http_endpoints() -> bool:
    """Test the basic HTTP endpoints that do not require session persistence."""
    print("=" * 60)
    print("Testing HTTP Endpoints")
    print("=" * 60)

    print("\n1. Testing /health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   ERROR: {e}")
        return False

    print("\n2. Testing /reset endpoint...")
    try:
        response = requests.post(f"{BASE_URL}/reset", json={}, timeout=10)
        print(f"   Status: {response.status_code}")
        data = response.json()
        print(f"   Response keys: {list(data.keys())}")
        if "observation" in data:
            obs = data["observation"]
            print(f"   Task ID: {obs.get('task_id')}")
            print(f"   Difficulty: {obs.get('task_difficulty')}")
            print(f"   Done: {data.get('done')}")
    except Exception as e:
        print(f"   ERROR: {e}")
        return False

    print("\n3. Skipping HTTP /step for episode testing...")
    print("   OpenEnv step-by-step episodes are stateful and should use /ws via TeamHackathonEnv.")

    print("\n" + "=" * 60)
    print("HTTP sanity checks passed")
    print("=" * 60)
    return True


async def test_simple_episode() -> bool:
    """Test a complete episode using the persistent OpenEnv client."""
    env = TeamHackathonEnv(
        base_url=BASE_URL,
        connect_timeout_s=10.0,
        message_timeout_s=15.0,
    )

    print("\n" + "=" * 60)
    print("Testing Complete Episode")
    print("=" * 60)

    try:
        print("\nResetting environment...")
        result = await env.reset()
        obs = result.observation
        print(f"Task: {obs.task_id} ({obs.task_difficulty})")

        actions = ["check_logs", "check_api", "check_metrics", "retry_pipeline"]

        for i, action_name in enumerate(actions, 1):
            print(f"\nStep {i}: {action_name}")
            result = await env.step(TeamHackathonAction(action_type=action_name))
            obs = result.observation

            print(f"  Result: {obs.action_result}")
            print(f"  Reward: {result.reward}")
            print(f"  Score: {obs.current_score:.3f}")
            print(f"  Done: {result.done}")

            if result.done:
                print(f"\nEpisode complete. Final score: {obs.current_score:.3f}")
                break

        print("\n" + "=" * 60)
        return True
    except Exception as e:
        print(f"\nERROR during episode test: {e}")
        return False
    finally:
        await env.close()


if __name__ == "__main__":
    print("\nPipeline Debugger Connection Test\n")

    if test_http_endpoints():
        asyncio.run(test_simple_episode())
    else:
        print("\nHTTP checks failed. Start the server with:")
        print("  python -m uvicorn server.app:app --host 0.0.0.0 --port 8000")

# Made with Bob
