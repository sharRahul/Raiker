# SPDX-License-Identifier: Apache-2.0
"""Configuring, selecting, probing and resetting an execution environment."""

from __future__ import annotations

from typing_extensions import TypedDict

from raiker.control.views.execution import ExecutionEnvironmentView


class ExecutionEnvironmentConfigured(TypedDict):
    ok: bool
    profile_id: str


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
