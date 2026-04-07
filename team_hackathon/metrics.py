"""
Metrics and Scoring Module for Pipeline Debugging Environment.

This module provides transparent, reusable scoring functions for evaluating
agent performance in the pipeline debugging task.

Scoring Methodology:
- Base Score (70%): Correctness of diagnostic and fix actions
- Efficiency Score (30%): Step optimization (fewer steps = higher score)
- Final Score: Normalized to 0.0-1.0 range

Author: Pipeline Debugging Team
"""

from typing import Set, Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class EpisodeMetrics:
    """Container for episode performance metrics."""
    
    task_id: str
    difficulty: str
    total_steps: int
    correct_diagnostics: int
    correct_fixes: int
    wrong_actions: int
    raw_score: float
    base_score: float
    efficiency_score: float
    final_score: float
    success: bool
    
    def to_dict(self) -> Dict:
        """Convert metrics to dictionary."""
        return {
            "task_id": self.task_id,
            "difficulty": self.difficulty,
            "total_steps": self.total_steps,
            "correct_diagnostics": self.correct_diagnostics,
            "correct_fixes": self.correct_fixes,
            "wrong_actions": self.wrong_actions,
            "raw_score": round(self.raw_score, 3),
            "base_score": round(self.base_score, 3),
            "efficiency_score": round(self.efficiency_score, 3),
            "final_score": round(self.final_score, 3),
            "success": self.success,
        }


class PipelineMetricsCalculator:
    """
    Calculator for pipeline debugging task metrics.
    
    Provides transparent scoring based on:
    1. Correctness of actions taken
    2. Efficiency (step count optimization)
    3. Task completion status
    """
    
    # Reward values
    CORRECT_DIAGNOSTIC_REWARD = 10.0
    CORRECT_FIX_REWARD = 20.0
    WRONG_ACTION_PENALTY = -5.0
    REDUNDANT_ACTION_PENALTY = -2.0
    IRRELEVANT_DIAGNOSTIC_PENALTY = -3.0
    
    # Scoring weights
    BASE_SCORE_WEIGHT = 0.7
    EFFICIENCY_WEIGHT = 0.3
    
    def __init__(self):
        """Initialize the metrics calculator."""
        pass
    
    def calculate_action_reward(
        self,
        action_type: str,
        correct_diagnostics: Set[str],
        correct_fixes: Set[str],
        diagnostics_taken: Set[str],
        fixes_taken: Set[str],
    ) -> Tuple[float, str]:
        """
        Calculate reward for a single action.
        
        Args:
            action_type: The action being taken
            correct_diagnostics: Set of correct diagnostic actions for this task
            correct_fixes: Set of correct fix actions for this task
            diagnostics_taken: Set of diagnostic actions already taken
            fixes_taken: Set of fix actions already taken
            
        Returns:
            Tuple of (reward, result_message)
        """
        diagnostic_actions = ["check_logs", "check_api", "check_metrics"]
        fix_actions = ["retry_pipeline", "apply_batching", "fix_sync"]
        
        # Handle diagnostic actions
        if action_type in diagnostic_actions:
            if action_type in diagnostics_taken:
                return self.REDUNDANT_ACTION_PENALTY, f"Already checked {action_type}"
            elif action_type in correct_diagnostics:
                return self.CORRECT_DIAGNOSTIC_REWARD, f"Checked {action_type} - found issues"
            else:
                return self.IRRELEVANT_DIAGNOSTIC_PENALTY, f"Checked {action_type} - no relevant issues"
        
        # Handle fix actions
        elif action_type in fix_actions:
            if action_type in fixes_taken:
                return self.REDUNDANT_ACTION_PENALTY, f"Already applied {action_type}"
            elif action_type in correct_fixes:
                return self.CORRECT_FIX_REWARD, f"Applied {action_type} successfully"
            else:
                return self.WRONG_ACTION_PENALTY, f"Applied {action_type} - not effective"
        
        # Invalid action
        else:
            return self.WRONG_ACTION_PENALTY, f"Invalid action: {action_type}"
    
    def calculate_base_score(
        self,
        raw_score: float,
        correct_diagnostics: Set[str],
        correct_fixes: Set[str],
    ) -> float:
        """
        Calculate base score from raw accumulated rewards.
        
        Args:
            raw_score: Accumulated reward from all actions
            correct_diagnostics: Set of correct diagnostic actions
            correct_fixes: Set of correct fix actions
            
        Returns:
            Normalized base score (0.0-1.0)
        """
        max_possible_score = (
            len(correct_diagnostics) * self.CORRECT_DIAGNOSTIC_REWARD +
            len(correct_fixes) * self.CORRECT_FIX_REWARD
        )
        
        if max_possible_score <= 0:
            return 0.0
        
        # Normalize to 0-1 range, ensuring non-negative
        base_score = max(0, raw_score) / max_possible_score
        return min(1.0, base_score)
    
    def calculate_efficiency_score(
        self,
        steps_taken: int,
        correct_diagnostics: Set[str],
        correct_fixes: Set[str],
    ) -> float:
        """
        Calculate efficiency score based on step count.
        
        Optimal path = number of correct diagnostics + number of correct fixes
        Efficiency = optimal_steps / actual_steps
        
        Args:
            steps_taken: Number of steps taken by agent
            correct_diagnostics: Set of correct diagnostic actions
            correct_fixes: Set of correct fix actions
            
        Returns:
            Efficiency score (0.0-1.0)
        """
        optimal_steps = len(correct_diagnostics) + len(correct_fixes)
        
        if steps_taken <= 0:
            return 0.0
        
        efficiency = optimal_steps / steps_taken
        return min(1.0, efficiency)
    
    def calculate_final_score(
        self,
        raw_score: float,
        steps_taken: int,
        correct_diagnostics: Set[str],
        correct_fixes: Set[str],
        diagnostics_taken: Set[str],
        fixes_taken: Set[str],
    ) -> Tuple[float, float, float]:
        """
        Calculate final normalized score (0.0-1.0).
        
        Formula:
        final_score = (base_score * 0.7) + (efficiency_score * 0.3)
        
        Args:
            raw_score: Accumulated reward from all actions
            steps_taken: Number of steps taken
            correct_diagnostics: Set of correct diagnostic actions
            correct_fixes: Set of correct fix actions
            diagnostics_taken: Set of diagnostic actions taken
            fixes_taken: Set of fix actions taken
            
        Returns:
            Tuple of (base_score, efficiency_score, final_score)
        """
        # Calculate component scores
        base_score = self.calculate_base_score(
            raw_score, correct_diagnostics, correct_fixes
        )
        
        efficiency_score = self.calculate_efficiency_score(
            steps_taken, correct_diagnostics, correct_fixes
        )
        
        # Weighted combination
        final_score = (
            base_score * self.BASE_SCORE_WEIGHT +
            efficiency_score * self.EFFICIENCY_WEIGHT
        )
        
        # Ensure in valid range
        final_score = max(0.0, min(1.0, final_score))
        
        return base_score, efficiency_score, final_score
    
    def is_task_complete(
        self,
        correct_diagnostics: Set[str],
        correct_fixes: Set[str],
        diagnostics_taken: Set[str],
        fixes_taken: Set[str],
    ) -> bool:
        """
        Check if task is successfully completed.
        
        Task is complete when:
        - All correct diagnostics have been performed
        - At least one correct fix has been applied
        
        Args:
            correct_diagnostics: Set of correct diagnostic actions
            correct_fixes: Set of correct fix actions
            diagnostics_taken: Set of diagnostic actions taken
            fixes_taken: Set of fix actions taken
            
        Returns:
            True if task is complete, False otherwise
        """
        diagnosis_complete = correct_diagnostics.issubset(diagnostics_taken)
        fix_applied = len(fixes_taken & correct_fixes) > 0
        
        return diagnosis_complete and fix_applied
    
    def create_episode_metrics(
        self,
        task_id: str,
        difficulty: str,
        total_steps: int,
        raw_score: float,
        correct_diagnostics: Set[str],
        correct_fixes: Set[str],
        diagnostics_taken: Set[str],
        fixes_taken: Set[str],
        wrong_actions: int,
    ) -> EpisodeMetrics:
        """
        Create comprehensive episode metrics.
        
        Args:
            task_id: Task identifier
            difficulty: Task difficulty level
            total_steps: Total steps taken
            raw_score: Raw accumulated score
            correct_diagnostics: Set of correct diagnostic actions
            correct_fixes: Set of correct fix actions
            diagnostics_taken: Set of diagnostic actions taken
            fixes_taken: Set of fix actions taken
            wrong_actions: Count of wrong actions
            
        Returns:
            EpisodeMetrics object with all calculated metrics
        """
        base_score, efficiency_score, final_score = self.calculate_final_score(
            raw_score,
            total_steps,
            correct_diagnostics,
            correct_fixes,
            diagnostics_taken,
            fixes_taken,
        )
        
        success = self.is_task_complete(
            correct_diagnostics,
            correct_fixes,
            diagnostics_taken,
            fixes_taken,
        )
        
        return EpisodeMetrics(
            task_id=task_id,
            difficulty=difficulty,
            total_steps=total_steps,
            correct_diagnostics=len(diagnostics_taken & correct_diagnostics),
            correct_fixes=len(fixes_taken & correct_fixes),
            wrong_actions=wrong_actions,
            raw_score=raw_score,
            base_score=base_score,
            efficiency_score=efficiency_score,
            final_score=final_score,
            success=success,
        )


def format_metrics_report(metrics: EpisodeMetrics) -> str:
    """
    Format episode metrics as a readable report.
    
    Args:
        metrics: EpisodeMetrics object
        
    Returns:
        Formatted string report
    """
    report = f"""
Episode Metrics Report
{'=' * 60}
Task: {metrics.task_id}
Difficulty: {metrics.difficulty}
Success: {'✓' if metrics.success else '✗'}

Performance:
  Total Steps: {metrics.total_steps}
  Correct Diagnostics: {metrics.correct_diagnostics}
  Correct Fixes: {metrics.correct_fixes}
  Wrong Actions: {metrics.wrong_actions}

Scores:
  Raw Score: {metrics.raw_score:.2f}
  Base Score (70%): {metrics.base_score:.3f}
  Efficiency Score (30%): {metrics.efficiency_score:.3f}
  Final Score: {metrics.final_score:.3f}
{'=' * 60}
"""
    return report


def calculate_aggregate_metrics(episodes: List[EpisodeMetrics]) -> Dict:
    """
    Calculate aggregate metrics across multiple episodes.
    
    Args:
        episodes: List of EpisodeMetrics objects
        
    Returns:
        Dictionary with aggregate statistics
    """
    if not episodes:
        return {}
    
    total_episodes = len(episodes)
    successful_episodes = sum(1 for e in episodes if e.success)
    
    avg_score = sum(e.final_score for e in episodes) / total_episodes
    avg_steps = sum(e.total_steps for e in episodes) / total_episodes
    avg_base_score = sum(e.base_score for e in episodes) / total_episodes
    avg_efficiency = sum(e.efficiency_score for e in episodes) / total_episodes
    
    # Group by difficulty
    by_difficulty = {}
    for episode in episodes:
        if episode.difficulty not in by_difficulty:
            by_difficulty[episode.difficulty] = []
        by_difficulty[episode.difficulty].append(episode)
    
    difficulty_stats = {}
    for difficulty, eps in by_difficulty.items():
        difficulty_stats[difficulty] = {
            "count": len(eps),
            "avg_score": sum(e.final_score for e in eps) / len(eps),
            "success_rate": sum(1 for e in eps if e.success) / len(eps),
        }
    
    return {
        "total_episodes": total_episodes,
        "successful_episodes": successful_episodes,
        "success_rate": successful_episodes / total_episodes,
        "average_score": round(avg_score, 3),
        "average_steps": round(avg_steps, 2),
        "average_base_score": round(avg_base_score, 3),
        "average_efficiency": round(avg_efficiency, 3),
        "by_difficulty": difficulty_stats,
    }

# Made with Bob
