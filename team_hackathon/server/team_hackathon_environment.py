# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Pipeline Debugging Environment Implementation.

An OpenEnv environment for training agents to diagnose and fix supply chain
pipeline failures through systematic investigation.
"""

import json
from pathlib import Path
from uuid import uuid4
import random
from typing import Any, Dict, Set, Optional

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

try:
    from team_hackathon.models import TeamHackathonAction, TeamHackathonObservation
    from team_hackathon.metrics import PipelineMetricsCalculator
except ImportError:
    from models import TeamHackathonAction, TeamHackathonObservation
    from metrics import PipelineMetricsCalculator


DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "sample_logs.json"


def _load_incident_corpus() -> Dict[str, Dict[str, Any]]:
    with DATA_PATH.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    return payload["incidents"]


INCIDENT_CORPUS = _load_incident_corpus()


# Task definitions with difficulty progression
TASKS = {
    "easy_api_delay": {
        "difficulty": "easy",
        "name": "Simple API Delay",
        "description": "API response time is high",
        "indicators": {
            "api_response_time": 0.8,
            "latency_score": 0.7,
        },
        "correct_diagnostic": ["check_api", "check_metrics"],
        "correct_fixes": ["retry_pipeline"],
        "max_steps": 8,
    },
    "medium_sync_failure": {
        "difficulty": "medium",
        "name": "Warehouse Sync Failure",
        "description": "Stock mismatch between warehouse and central system",
        "indicators": {
            "inventory_lag_score": 0.8,
            "inventory_error_count": 0.7,
            "api_response_time": 0.9,
            "api_error_rate": 0.6,
        },
        "correct_diagnostic": ["check_logs", "check_api"],
        "correct_fixes": ["fix_sync", "retry_pipeline"],
        "max_steps": 10,
    },
    "hard_cascade_failure": {
        "difficulty": "hard",
        "name": "Cascading Timeout Failure",
        "description": "Multiple systems experiencing cascading failures",
        "indicators": {
            "inventory_lag_score": 0.9,
            "api_response_time": 0.95,
            "api_error_rate": 0.85,
            "latency_score": 0.9,
            "network_congestion": 0.95,
        },
        "correct_diagnostic": ["check_logs", "check_api", "check_metrics"],
        "correct_fixes": ["retry_pipeline", "apply_batching", "fix_sync"],
        "max_steps": 12,
    },
}


class TeamHackathonEnvironment(Environment):
    """
    Pipeline Debugging Environment for agent training.
    
    Agents must diagnose pipeline failures by inspecting logs, API status,
    and metrics, then apply appropriate fixes. Tasks vary in difficulty.
    
    Scoring (0.0-1.0):
    - Correct diagnostic actions: +points
    - Correct fixes: +points
    - Efficiency bonus: fewer steps = higher score
    - Wrong actions: -points
    """

    SUPPORTS_CONCURRENT_SESSIONS: bool = True
    MIN_VISIBLE_SCORE: float = 1e-3

    def __init__(self, task_id: Optional[str] = None):
        """
        Initialize the pipeline debugging environment.
        
        Args:
            task_id: Specific task to load (random if None)
        """
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._task_id = task_id
        self._current_task = None
        self._current_incident: Optional[Dict[str, Any]] = None
        self._diagnostic_actions_taken: Set[str] = set()
        self._fix_actions_taken: Set[str] = set()
        self._wrong_actions = 0
        self._score = 0.0
        self._metrics_calculator = PipelineMetricsCalculator()

    def reset(self, task_id: Optional[str] = None) -> TeamHackathonObservation:
        """
        Reset the environment with a new task.
        
        Args:
            task_id: Specific task to load (random if None)
            
        Returns:
            Initial observation
        """
        self._state = State(episode_id=str(uuid4()), step_count=0)
        
        # Select task
        if task_id and task_id in TASKS:
            self._task_id = task_id
        elif self._task_id and self._task_id in TASKS:
            pass  # Keep existing task_id
        else:
            self._task_id = random.choice(list(TASKS.keys()))
        
        self._current_task = TASKS[self._task_id]
        self._current_incident = INCIDENT_CORPUS[self._task_id]
        self._diagnostic_actions_taken = set()
        self._fix_actions_taken = set()
        self._wrong_actions = 0
        self._score = 0.0
        
        # Generate initial observation
        indicators = self._current_task["indicators"]
        
        return TeamHackathonObservation(
            task_id=self._task_id,
            task_difficulty=self._current_task["difficulty"],
            pipeline_name="Inventory Sync Pipeline",
            issue_description=self._current_task["description"],
            inventory_lag_score=indicators.get("inventory_lag_score", 0.2),
            inventory_error_count=indicators.get("inventory_error_count", 0.1),
            api_response_time=indicators.get("api_response_time", 0.2),
            api_error_rate=indicators.get("api_error_rate", 0.1),
            latency_score=indicators.get("latency_score", 0.2),
            network_congestion=indicators.get("network_congestion", 0.1),
            last_action=None,
            action_result=None,
            actions_taken=0,
            step_count=0,
            max_steps=self._current_task["max_steps"],
            diagnosis_complete=False,
            fix_applied=False,
            current_score=self.MIN_VISIBLE_SCORE,
            hints=f"Investigate the {self._current_task['name']}",
            inventory_log_excerpt=self._format_inventory_excerpt(),
            api_log_excerpt=self._format_api_excerpt(),
            metrics_summary=self._format_metrics_summary(),
            business_impact_summary=self._format_business_impact(),
            done=False,
            reward=0.0,
        )

    def step(self, action: TeamHackathonAction) -> TeamHackathonObservation:  # type: ignore[override]
        """
        Execute an action in the environment.
        
        Args:
            action: Action to execute
            
        Returns:
            Observation with results
        """
        self._state.step_count += 1
        
        action_type = action.action_type
        
        # Ensure task is initialized
        if self._current_task is None or self._current_incident is None:
            raise RuntimeError("Environment not initialized. Call reset() first.")
        
        # Get correct actions for current task
        correct_diagnostic = set(self._current_task["correct_diagnostic"])
        correct_fixes = set(self._current_task["correct_fixes"])
        
        # Calculate reward using metrics module
        reward, action_result = self._metrics_calculator.calculate_action_reward(
            action_type,
            correct_diagnostic,
            correct_fixes,
            self._diagnostic_actions_taken,
            self._fix_actions_taken,
        )
        action_result = self._describe_action_result(action_type, action_result)
        
        # Update action tracking
        if action_type in ["check_logs", "check_api", "check_metrics"]:
            if action_type in correct_diagnostic and action_type not in self._diagnostic_actions_taken:
                self._diagnostic_actions_taken.add(action_type)
            elif action_type not in correct_diagnostic:
                self._wrong_actions += 1
        elif action_type in ["retry_pipeline", "apply_batching", "fix_sync"]:
            if action_type in correct_fixes and action_type not in self._fix_actions_taken:
                self._fix_actions_taken.add(action_type)
            elif action_type not in correct_fixes:
                self._wrong_actions += 1
        
        # Update score
        self._score += reward
        
        # Check if task is complete using metrics module
        diagnosis_complete = self._metrics_calculator.is_task_complete(
            correct_diagnostic,
            correct_fixes,
            self._diagnostic_actions_taken,
            self._fix_actions_taken,
        )
        fix_applied = len(self._fix_actions_taken & correct_fixes) > 0
        
        # Episode done if: all correct actions taken OR max steps reached
        done = diagnosis_complete or self._state.step_count >= self._current_task["max_steps"]
        
        # Always expose a strictly in-range normalized score for validator compatibility.
        _, _, running_score = self._metrics_calculator.calculate_final_score(
            self._score,
            self._state.step_count,
            correct_diagnostic,
            correct_fixes,
            self._diagnostic_actions_taken,
            self._fix_actions_taken,
        )
        final_score = running_score if done else max(self.MIN_VISIBLE_SCORE, running_score)
        
        # Generate observation
        indicators = self._current_task["indicators"]
        
        return TeamHackathonObservation(
            task_id=self._task_id,
            task_difficulty=self._current_task["difficulty"],
            pipeline_name="Inventory Sync Pipeline",
            issue_description=self._current_task["description"],
            inventory_lag_score=indicators.get("inventory_lag_score", 0.2),
            inventory_error_count=indicators.get("inventory_error_count", 0.1),
            api_response_time=indicators.get("api_response_time", 0.2),
            api_error_rate=indicators.get("api_error_rate", 0.1),
            latency_score=indicators.get("latency_score", 0.2),
            network_congestion=indicators.get("network_congestion", 0.1),
            last_action=action_type,
            action_result=action_result,
            actions_taken=self._state.step_count,
            step_count=self._state.step_count,
            max_steps=self._current_task["max_steps"],
            diagnosis_complete=diagnosis_complete,
            fix_applied=fix_applied,
            current_score=final_score,
            hints=self._get_hint(),
            inventory_log_excerpt=self._format_inventory_excerpt(),
            api_log_excerpt=self._format_api_excerpt(),
            metrics_summary=self._format_metrics_summary(),
            business_impact_summary=self._format_business_impact(),
            done=done,
            reward=final_score if done else reward,
            metadata={
                "diagnostic_actions": list(self._diagnostic_actions_taken),
                "fix_actions": list(self._fix_actions_taken),
                "wrong_actions": self._wrong_actions,
                "root_cause": self._current_incident["expected_diagnosis"]["root_cause"],
            },
        )

    def _get_hint(self) -> str:
        """Generate contextual hint based on current state."""
        if len(self._diagnostic_actions_taken) == 0:
            return "Start with the evidence stream that best explains the current operational impact."
        if not self._fix_actions_taken:
            return "You have enough clues to isolate the fault domain. Choose a remediation that addresses the observed failure mode."
        return "Continue investigating or apply the remaining remediation needed to stabilize the pipeline."

    def _format_inventory_excerpt(self) -> str:
        assert self._current_incident is not None
        entries = self._current_incident["inventory_logs"]["entries"][:6]
        return "\n".join(entries)

    def _format_api_excerpt(self) -> str:
        assert self._current_incident is not None
        entries = self._current_incident["api_sync_logs"]["entries"][:6]
        return "\n".join(entries)

    def _format_metrics_summary(self) -> str:
        assert self._current_incident is not None
        metrics = self._current_incident["metrics"]
        series = "; ".join(metrics["time_series"][:4])
        return (
            f"avg_latency_ms={metrics['avg_latency_ms']}, "
            f"max_latency_ms={metrics['max_latency_ms']}, "
            f"network_congestion={metrics['network_congestion']}, "
            f"cpu={metrics['cpu_usage_percent']}%, memory={metrics['memory_usage_percent']}%, "
            f"active_connections={metrics['active_connections']}. "
            f"Timeline: {series}"
        )

    def _format_business_impact(self) -> str:
        assert self._current_incident is not None
        impact = self._current_incident["business_impact"]
        return (
            f"Delayed orders={impact['delayed_orders']}, warehouses affected={impact['warehouses_affected']}, "
            f"partner escalations={impact['partner_escalations']}, sla_breach_risk={impact['sla_breach_risk']}."
        )

    def _describe_action_result(self, action_type: str, fallback: str) -> str:
        assert self._current_incident is not None
        diagnosis = self._current_incident["expected_diagnosis"]
        if action_type == "check_logs":
            return (
                f"{fallback}. Inventory evidence: {self._current_incident['inventory_logs']['entries'][0]}"
            )
        if action_type == "check_api":
            return (
                f"{fallback}. API evidence: {self._current_incident['api_sync_logs']['entries'][0]}"
            )
        if action_type == "check_metrics":
            return (
                f"{fallback}. Metrics evidence: {self._current_incident['metrics']['time_series'][-1]}"
            )
        if action_type in diagnosis["recommended_fix"]:
            return f"{fallback}. This aligns with the incident pattern: {diagnosis['root_cause']}"
        return fallback

    @property
    def state(self) -> State:
        """Get current environment state."""
        return self._state
