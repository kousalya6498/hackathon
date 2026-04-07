"""
Baseline Script for Pipeline Debugging Environment.

Demonstrates how to interact with the environment and provides
baseline performance metrics for comparison.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import List, Dict

PACKAGE_PARENT = Path(__file__).resolve().parent.parent
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))

from team_hackathon.client import TeamHackathonEnv
from team_hackathon.models import TeamHackathonAction

TASK_ORDER = ["easy_api_delay", "medium_sync_failure", "hard_cascade_failure"]


class BaselineAgent:
    """
    Simple baseline agent that uses a rule-based strategy.
    
    Strategy:
    1. Check all diagnostic sources (logs, API, metrics)
    2. Apply all available fixes
    3. No learning or optimization
    """
    
    def __init__(self):
        self.diagnostic_actions = ["check_logs", "check_api", "check_metrics"]
        self.fix_actions = ["retry_pipeline", "apply_batching", "fix_sync"]
    
    def select_action(self, observation) -> str:
        """
        Select next action based on simple rules.
        
        Args:
            observation: Current observation from environment
            
        Returns:
            Action type string
        """
        # First, do all diagnostics
        if observation.actions_taken < len(self.diagnostic_actions):
            return self.diagnostic_actions[observation.actions_taken]
        
        # Then apply fixes
        fix_index = observation.actions_taken - len(self.diagnostic_actions)
        if fix_index < len(self.fix_actions):
            return self.fix_actions[fix_index]
        
        # Fallback: retry
        return "retry_pipeline"


async def run_episode(env: TeamHackathonEnv, agent: BaselineAgent, task_id: str = None) -> Dict:
    """
    Run a single episode with the baseline agent.
    
    Args:
        env: Environment instance
        agent: Agent instance
        task_id: Specific task to run (None for random)
        
    Returns:
        Episode results dictionary
    """
    # Reset environment
    reset_kwargs = {"task_id": task_id} if task_id else {}
    result = await env.reset(**reset_kwargs)
    observation = result.observation
    done = result.done
    
    episode_data = {
        "task_id": observation.task_id,
        "difficulty": observation.task_difficulty,
        "steps": [],
        "final_score": 0.0,
        "success": False,
    }
    
    # Run episode
    while not done:
        # Select action
        action_type = agent.select_action(observation)
        action = TeamHackathonAction(action_type=action_type)
        
        # Take step
        result = await env.step(action)
        observation = result.observation
        done = result.done
        
        # Record step
        episode_data["steps"].append({
            "step": observation.step_count,
            "action": action_type,
            "result": observation.action_result,
            "reward": result.reward,
        })
        
        # Check if done
        if done:
            episode_data["final_score"] = observation.current_score
            episode_data["success"] = observation.diagnosis_complete and observation.fix_applied
            break
    
    return episode_data


async def evaluate_baseline(num_episodes: int = 10, base_url: str = None) -> Dict:
    """
    Evaluate baseline agent performance.
    
    Args:
        num_episodes: Number of episodes to run
        base_url: Environment URL (None for Docker)
        
    Returns:
        Evaluation results
    """
    print("=" * 60)
    print("Baseline Agent Evaluation")
    print("=" * 60)
    
    # Initialize environment
    if base_url:
        env = TeamHackathonEnv(
            base_url=base_url,
            connect_timeout_s=10.0,
            message_timeout_s=15.0,
        )
    else:
        # Use Docker image
        env = await TeamHackathonEnv.from_docker_image("team_hackathon-env:latest")
    
    agent = BaselineAgent()
    
    try:
        results = {
            "episodes": [],
            "by_difficulty": {
                "easy": [],
                "medium": [],
                "hard": [],
            },
        }
        
        # Run episodes
        for i in range(num_episodes):
            print(f"\nEpisode {i+1}/{num_episodes}")
            task_id = TASK_ORDER[i % len(TASK_ORDER)]
            episode_data = await run_episode(env, agent, task_id=task_id)
            
            results["episodes"].append(episode_data)
            results["by_difficulty"][episode_data["difficulty"]].append(episode_data["final_score"])
            
            print(f"  Task: {episode_data['task_id']}")
            print(f"  Difficulty: {episode_data['difficulty']}")
            print(f"  Steps: {len(episode_data['steps'])}")
            print(f"  Score: {episode_data['final_score']:.3f}")
            print(f"  Success: {episode_data['success']}")
        
        # Calculate statistics
        all_scores = [ep["final_score"] for ep in results["episodes"]]
        success_rate = sum(1 for ep in results["episodes"] if ep["success"]) / len(results["episodes"])
        
        stats = {
            "total_episodes": num_episodes,
            "mean_score": sum(all_scores) / len(all_scores) if all_scores else 0.0,
            "success_rate": success_rate,
            "by_difficulty": {},
        }
        
        for difficulty in ["easy", "medium", "hard"]:
            scores = results["by_difficulty"][difficulty]
            if scores:
                stats["by_difficulty"][difficulty] = {
                    "count": len(scores),
                    "mean_score": sum(scores) / len(scores),
                }
        
        # Print summary
        print("\n" + "=" * 60)
        print("Evaluation Summary")
        print("=" * 60)
        print(f"Total Episodes: {stats['total_episodes']}")
        print(f"Mean Score: {stats['mean_score']:.3f}")
        print(f"Success Rate: {stats['success_rate']:.1%}")
        print("\nBy Difficulty:")
        for difficulty, data in stats["by_difficulty"].items():
            if data:
                print(f"  {difficulty.capitalize()}: {data['mean_score']:.3f} ({data['count']} episodes)")
        print("=" * 60)
        
        return stats
    
    finally:
        await env.close()


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Baseline agent for pipeline debugging")
    parser.add_argument("--episodes", type=int, default=10, help="Number of episodes")
    parser.add_argument("--url", type=str, default=None, help="Environment URL")
    parser.add_argument("--output", type=str, default=None, help="Output JSON file")
    
    args = parser.parse_args()
    
    # Run evaluation
    stats = await evaluate_baseline(num_episodes=args.episodes, base_url=args.url)
    
    # Save results if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(stats, f, indent=2)
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())

# Made with Bob
