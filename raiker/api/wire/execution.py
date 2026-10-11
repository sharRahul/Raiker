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


class ExecutionEnvironmentRemoved(TypedDict):
    """DEC-11 step 6 — a configured environment removed; what ran there is kept."""

    ok: bool
    profile_id: str
    removed: bool
    name: str
    #: Where work now runs by default, when the removed one was the default and
    #: the owner chose a replacement; ``None`` when it was not the default.
    selected_profile_id: str | None


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
