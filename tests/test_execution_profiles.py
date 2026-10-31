from __future__ import annotations

import json

from raiker.execution.profiles import (
    ExecutionProfile,
    resolve_tool_profile,
    retired_container_tools,
    validate_execution_profile,
)


def test_assigned_profile_resolves_supported_tool() -> None:
    profile = ExecutionProfile("ssh-review", "ssh", tools=("shell",))

    resolution = resolve_tool_profile("shell", [profile])

    assert resolution.profile == profile
    assert resolution.reason_code is None


def test_a_container_kind_is_invalid_not_host_fallback() -> None:
    profile = ExecutionProfile("container-review", "container", tools=("grep",))  # type: ignore[arg-type]

    resolution = resolve_tool_profile("grep", [profile])

    assert validate_execution_profile(profile) == "execution_profile_kind_invalid:container-review"
    assert resolution.profile is None
    assert resolution.reason_code == "execution_profile_kind_invalid:container-review"


def test_duplicate_tool_assignments_fail_closed() -> None:
    first = ExecutionProfile("first", "ssh", tools=("shell",))
    second = ExecutionProfile("second", "daytona", tools=("shell",))

    resolution = resolve_tool_profile("shell", [first, second])

    assert resolution.profile is None
    assert resolution.reason_code == "execution_profile_ambiguous:shell"


def test_unassigned_tool_uses_explicit_local_profile() -> None:
    resolution = resolve_tool_profile("read_file", [])

    assert resolution.profile is not None
    assert resolution.profile.profile_id == "local_native"
    assert resolution.reason_code is None


def test_only_enabled_retired_container_rows_hold_their_tools() -> None:
    rows = [
        {"profile_type": "container", "enabled": 1, "config_json": json.dumps({"tools": ["grep"]})},
        {"profile_type": "container", "enabled": 0, "config_json": json.dumps({"tools": ["glob"]})},
        {"profile_type": "ssh", "enabled": 1, "config_json": json.dumps({"tools": ["shell"]})},
        {"profile_type": "container", "enabled": 1, "config_json": "not json"},
    ]

    assert retired_container_tools(rows) == frozenset({"grep"})
