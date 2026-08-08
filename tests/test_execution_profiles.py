from __future__ import annotations

from raiker.execution.profiles import ExecutionProfile, resolve_tool_profile


def test_container_profile_resolves_supported_tool() -> None:
    profile = ExecutionProfile(
        "container-review",
        "container",
        runtime="podman",
        image="raiker-tools:approved",
        tools=("grep",),
        repository_access="read_only",
        writable_output=True,
    )

    resolution = resolve_tool_profile("grep", [profile])

    assert resolution.profile == profile
    assert resolution.reason_code is None


def test_invalid_container_runtime_is_a_refusal_not_host_fallback() -> None:
    profile = ExecutionProfile(
        "container-review",
        "container",
        runtime="nerdctl",  # type: ignore[arg-type]
        image="raiker-tools:approved",
        tools=("grep",),
        repository_access="read_only",
    )

    resolution = resolve_tool_profile("grep", [profile])

    assert resolution.profile is None
    assert resolution.reason_code == "container_runtime_invalid:container-review"


def test_duplicate_tool_assignments_fail_closed() -> None:
    first = ExecutionProfile(
        "first", "container", runtime="docker", image="approved", tools=("grep",)
    )
    second = ExecutionProfile(
        "second", "container", runtime="podman", image="approved", tools=("grep",)
    )

    resolution = resolve_tool_profile("grep", [first, second])

    assert resolution.profile is None
    assert resolution.reason_code == "execution_profile_ambiguous:grep"


def test_unassigned_tool_uses_explicit_local_profile() -> None:
    resolution = resolve_tool_profile("read_file", [])

    assert resolution.profile is not None
    assert resolution.profile.profile_id == "local_native"
    assert resolution.reason_code is None
