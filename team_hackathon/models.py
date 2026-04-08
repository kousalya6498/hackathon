# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Data models for the Pipeline Debugging Environment.

The pipeline debugging environment simulates supply chain pipeline failures
and requires agents to diagnose and fix issues through systematic investigation.
"""

from openenv.core.env_server.types import Action, Observation
from pydantic import Field
from typing import Optional, Dict, Any


class TeamHackathonAction(Action):
    """
    Action for the Pipeline Debugging environment.
    
    Agents can take diagnostic actions (inspect logs) or fix actions (apply solutions).
    """
    
    action_type: str = Field(
        ...,
        description="Type of action: 'check_logs', 'check_api', 'check_metrics', 'retry_pipeline', 'apply_batching', 'fix_sync'"
    )
    
    parameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional parameters for the action"
    )


class TeamHackathonObservation(Observation):
    """
    Observation from the Pipeline Debugging environment.
    
    Contains information about the current pipeline state, failure indicators,
    and feedback from previous actions.
    """
    model_config = {"extra": "allow"}  # Allow extra fields to catch errors
    # Task information
    task_id: str = Field(default="", description="Current task identifier")
    task_difficulty: str = Field(default="easy", description="Task difficulty: easy, medium, hard")
    
    # Pipeline state
    pipeline_name: str = Field(default="", description="Name of the pipeline")
    issue_description: str = Field(default="", description="Description of the issue")
    
    # Failure indicators (normalized 0-1)
    inventory_lag_score: float = Field(default=0.0, description="Inventory lag severity (0-1)")
    inventory_error_count: float = Field(default=0.0, description="Inventory error frequency (0-1)")
    api_response_time: float = Field(default=0.0, description="API response time severity (0-1)")
    api_error_rate: float = Field(default=0.0, description="API error rate (0-1)")
    latency_score: float = Field(default=0.0, description="Latency severity (0-1)")
    network_congestion: float = Field(default=0.0, description="Network congestion (0-1)")
    
    # Action feedback
    last_action: Optional[str] = Field(default=None, description="Last action taken")
    action_result: Optional[str] = Field(default=None, description="Result of last action")
    actions_taken: int = Field(default=0, description="Number of actions taken so far")
    
    # Episode state
    step_count: int = Field(default=0, description="Current step in episode")
    max_steps: int = Field(default=10, description="Maximum steps allowed")
    
    # Diagnosis state
    diagnosis_complete: bool = Field(default=False, description="Whether diagnosis is complete")
    fix_applied: bool = Field(default=False, description="Whether fix has been applied")
    
    # Score information
    current_score: float = Field(default=0.001, description="Current episode score (strictly between 0 and 1)")
    
    # Additional context
    hints: Optional[str] = Field(default=None, description="Hints for the agent")
    inventory_log_excerpt: Optional[str] = Field(
        default=None, description="Recent inventory-side evidence relevant to the incident"
    )
    api_log_excerpt: Optional[str] = Field(
        default=None, description="Recent API-side evidence relevant to the incident"
    )
    metrics_summary: Optional[str] = Field(
        default=None, description="Summary of recent infrastructure and latency metrics"
    )
    business_impact_summary: Optional[str] = Field(
        default=None, description="High-level business impact of the current incident"
    )
