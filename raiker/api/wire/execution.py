# SPDX-License-Identifier: Apache-2.0
"""Configuring, selecting, probing and resetting an execution environment."""

from __future__ import annotations

from typing_extensions import TypedDict

from raiker.control.views.execution import ExecutionEnvironmentView


class ExecutionEnvironmentConfigured(TypedDict):
    ok: bool
    profile_id: str


class ExecutionEnvironmentEnabled(TypedDict):
    """DEC-11 step 6 — an environment turned on or off, and the commands that stopped with it."""

    ok: bool
    profile_id: str
    enabled: bool
    #: Commands that were running there and were asked to stop.
    stopped_runs: int


class ExecutionEnvironmentSelected(TypedDict):
    ok: bool
    selected_profile_id: str


class ExecutionEnvironmentProbed(TypedDict):
    ok: bool
    environment: ExecutionEnvironmentView


class ExecutionEnvironmentReset(TypedDict):
    ok: bool
    profile_id: str
    session_id: str
    recreated: bool
