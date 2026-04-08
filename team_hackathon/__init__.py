# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Team Hackathon Environment."""


def __getattr__(name: str):
    if name in {"TeamHackathonAction", "TeamHackathonObservation"}:
        from .models import TeamHackathonAction, TeamHackathonObservation

        return {
            "TeamHackathonAction": TeamHackathonAction,
            "TeamHackathonObservation": TeamHackathonObservation,
        }[name]
    if name == "TeamHackathonEnv":
        from .client import TeamHackathonEnv

        return TeamHackathonEnv
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "TeamHackathonAction",
    "TeamHackathonObservation",
    "TeamHackathonEnv",
]
