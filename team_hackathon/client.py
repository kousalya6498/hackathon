# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Team Hackathon Environment Client."""

from typing import Dict

from openenv.core import EnvClient
from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State

from .models import TeamHackathonAction, TeamHackathonObservation


class TeamHackathonEnv(
    EnvClient[TeamHackathonAction, TeamHackathonObservation, State]
):
    """
    Client for the Team Hackathon Environment.

    This client maintains a persistent WebSocket connection to the environment server,
    enabling efficient multi-step interactions with lower latency.
    Each client instance has its own dedicated environment session on the server.

    Example:
        >>> # Connect to a running server
        >>> with TeamHackathonEnv(base_url="http://localhost:8000") as client:
        ...     result = client.reset()
        ...     print(result.observation.echoed_message)
        ...
        ...     result = client.step(TeamHackathonAction(message="Hello!"))
        ...     print(result.observation.echoed_message)

    Example with Docker:
        >>> # Automatically start container and connect
        >>> client = TeamHackathonEnv.from_docker_image("team_hackathon-env:latest")
        >>> try:
        ...     result = client.reset()
        ...     result = client.step(TeamHackathonAction(message="Test"))
        ... finally:
        ...     client.close()
    """

    def _step_payload(self, action: TeamHackathonAction) -> Dict:
        """
        Convert TeamHackathonAction to JSON payload for step message.

        Args:
            action: TeamHackathonAction instance

        Returns:
            Dictionary representation suitable for JSON encoding
        """
        return {
            "action_type": action.action_type,
            "parameters": action.parameters,
        }

    def _parse_result(self, payload: Dict) -> StepResult[TeamHackathonObservation]:
        """
        Parse server response into StepResult[TeamHackathonObservation].

        Args:
            payload: JSON response data from server

        Returns:
            StepResult with TeamHackathonObservation
        """
        obs_data = payload.get("observation", {})
        observation = TeamHackathonObservation(**obs_data)

        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict) -> State:
        """
        Parse server response into State object.

        Args:
            payload: JSON response from state request

        Returns:
            State object with episode_id and step_count
        """
        return State(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
        )
