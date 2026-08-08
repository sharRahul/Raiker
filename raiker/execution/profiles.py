from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, cast

ExecutionKind = Literal["local", "container", "ssh", "daytona"]
ContainerRuntime = Literal["docker", "podman"]
RepositoryAccess = Literal["none", "read_only"]

CONTAINER_PROFILE_TOOLS = frozenset(
    {"glob", "grep", "list_directory", "read_file", "shell", "stat_path"}
)


@dataclass(frozen=True)
class ExecutionProfile:
    profile_id: str
    kind: ExecutionKind
    default_state: str = "disabled_until_configured"
    requires_approval: bool = True
    name: str = ""
    enabled: bool = True
    runtime: ContainerRuntime | None = None
    image: str | None = None
    tools: tuple[str, ...] = ()
    repository_access: RepositoryAccess = "none"
    writable_output: bool = False


@dataclass(frozen=True)
class ProfileResolution:
    profile: ExecutionProfile | None
    reason_code: str | None = None


DEFAULT_EXECUTION_PROFILES = (
    ExecutionProfile("local_native", "local", "enabled_policy_gated", True),
    ExecutionProfile("container_default", "container"),
    ExecutionProfile("ssh_default", "ssh"),
    ExecutionProfile("daytona_default", "daytona"),
)


def list_execution_profiles() -> list[ExecutionProfile]:
    return list(DEFAULT_EXECUTION_PROFILES)


def execution_profiles_from_rows(
    rows: Sequence[Mapping[str, Any]],
) -> list[ExecutionProfile]:
    profiles: list[ExecutionProfile] = []
    for row in rows:
        if str(row.get("profile_type")) != "container":
            continue
        try:
            config = json.loads(str(row.get("config_json") or "{}"))
        except (TypeError, ValueError):
            config = {}
        raw_tools = config.get("tools", [])
        tools = (
            tuple(str(tool) for tool in raw_tools if isinstance(tool, str))
            if isinstance(raw_tools, list)
            else ()
        )
        profiles.append(
            ExecutionProfile(
                profile_id=str(row.get("profile_id") or ""),
                kind="container",
                name=str(row.get("name") or ""),
                enabled=bool(row.get("enabled")),
                runtime=cast(ContainerRuntime | None, config.get("runtime")),
                image=str(config.get("image") or "") or None,
                tools=tools,
                repository_access=cast(
                    RepositoryAccess, config.get("repository_access", "none")
                ),
                writable_output=bool(config.get("writable_output", False)),
            )
        )
    return profiles


def validate_execution_profile(profile: ExecutionProfile) -> str | None:
    if not profile.profile_id.strip():
        return "execution_profile_id_required"
    if profile.kind not in {"local", "container", "ssh", "daytona"}:
        return f"execution_profile_kind_invalid:{profile.profile_id}"
    if len(set(profile.tools)) != len(profile.tools):
        return f"execution_profile_tools_duplicated:{profile.profile_id}"
    if profile.kind != "container":
        return None
    if profile.runtime not in {"docker", "podman"}:
        return f"container_runtime_invalid:{profile.profile_id}"
    if not profile.image or not profile.image.strip():
        return f"container_image_required:{profile.profile_id}"
    if profile.repository_access not in {"none", "read_only"}:
        return f"container_repository_access_invalid:{profile.profile_id}"
    unsupported = sorted(set(profile.tools) - CONTAINER_PROFILE_TOOLS)
    if unsupported:
        return f"container_profile_tool_unsupported:{unsupported[0]}"
    return None


def resolve_tool_profile(
    tool_name: str, profiles: list[ExecutionProfile] | tuple[ExecutionProfile, ...]
) -> ProfileResolution:
    assigned = [profile for profile in profiles if profile.enabled and tool_name in profile.tools]
    if len(assigned) > 1:
        return ProfileResolution(None, f"execution_profile_ambiguous:{tool_name}")
    if assigned:
        reason = validate_execution_profile(assigned[0])
        return ProfileResolution(None, reason) if reason else ProfileResolution(assigned[0])
    local = next(
        (profile for profile in profiles if profile.enabled and profile.profile_id == "local_native"),
        DEFAULT_EXECUTION_PROFILES[0],
    )
    reason = validate_execution_profile(local)
    return ProfileResolution(None, reason) if reason else ProfileResolution(local)


def plan_remote_execution(profile_id: str, command: str) -> dict[str, object]:
    known = {profile.profile_id for profile in DEFAULT_EXECUTION_PROFILES}
    return {
        "profile_id": profile_id,
        "command_preview": command,
        "can_execute": False,
        "requires_approval": True,
        "reason": "phase4_remote_execution_disabled"
        if profile_id in known
        else "unknown_execution_profile",
    }
