from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast

from raiker.execution.commands.models import CommandFeatures

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
    credential_delivery: bool = False
    credential_delta_quarantine: bool = False

    def __post_init__(self) -> None:
        if self.credential_delivery and not self.credential_delta_quarantine:
            raise ValueError("credential_delivery_requires_quarantine")

    @property
    def features(self) -> CommandFeatures:
        if self.kind == "local":
            return CommandFeatures(shell=False, concurrent_runs=False)
        if self.kind == "container":
            return CommandFeatures(
                shell="shell" in self.tools,
                pty=True,
                background=True,
                input=True,
                filtered_network=True,
                persistent_environment=True,
                persistent=True,
                restart_recovery=True,
                recoverable=True,
                concurrent_runs=True,
                credential_delivery=self.credential_delivery,
                credential_delta_quarantine=self.credential_delta_quarantine,
            )
        return CommandFeatures(shell=True, concurrent_runs=False)


@dataclass(frozen=True)
class ProfileResolution:
    profile: ExecutionProfile | None
    reason_code: str | None = None


@dataclass(frozen=True)
class ProfileProbe:
    profile: ExecutionProfile
    available: bool
    reason_code: str | None
    checked_at: str


@dataclass(frozen=True)
class CommandEnvironmentResolution:
    profile: ExecutionProfile | None
    available: bool
    reason_code: str | None
    selected_for_commands: bool
    assigned_tools: tuple[str, ...]
    features: CommandFeatures | None
    probe_checked_at: str


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


def _checked_at() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def probe_execution_profile(profile: ExecutionProfile) -> ProfileProbe:
    """Prove the selected profile's minimum command readiness.

    Container readiness includes a daemon and image probe, not merely the
    presence of a CLI executable. Remote backends keep their command features
    unavailable until their dedicated supervisor task supplies a proof.
    """
    checked_at = _checked_at()
    reason = validate_execution_profile(profile)
    if reason:
        return ProfileProbe(profile, False, reason, checked_at)
    if profile.kind == "local":
        return ProfileProbe(profile, True, None, checked_at)
    if profile.kind == "container":
        assert profile.runtime is not None and profile.image is not None
        if shutil.which(profile.runtime) is None:
            return ProfileProbe(
                profile, False, f"container_runtime_unavailable:{profile.runtime}", checked_at
            )
        try:
            daemon = subprocess.run(  # noqa: S603 - fixed validated runtime argv
                [profile.runtime, "info"], capture_output=True, timeout=5, check=False
            )
            if daemon.returncode != 0:
                return ProfileProbe(profile, False, "container_daemon_unreachable", checked_at)
            image = subprocess.run(  # noqa: S603 - fixed validated runtime argv
                [profile.runtime, "image", "inspect", profile.image],
                capture_output=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return ProfileProbe(profile, False, "container_daemon_unreachable", checked_at)
        if image.returncode != 0:
            return ProfileProbe(profile, False, "container_image_unavailable", checked_at)
        return ProfileProbe(profile, True, None, checked_at)
    return ProfileProbe(profile, False, f"{profile.kind}_command_supervisor_unavailable", checked_at)


def _selected_profile(store: Any, owner_principal_id: str, profile_id: str) -> ExecutionProfile | None:
    if profile_id == "local_native":
        return DEFAULT_EXECUTION_PROFILES[0]
    if profile_id == "container_default":
        return DEFAULT_EXECUTION_PROFILES[1]
    row = store.load_remote_execution_profile(profile_id, owner_principal_id=owner_principal_id)
    if row is None:
        return None
    try:
        config = json.loads(str(row.get("config_json") or "{}"))
    except (TypeError, ValueError):
        config = {}
    raw_kind = str(row.get("profile_type") or "")
    kind: ExecutionKind = "daytona" if raw_kind == "cloud" else cast(ExecutionKind, raw_kind)
    raw_tools = config.get("tools", ["shell"] if kind in {"ssh", "daytona"} else [])
    tools = tuple(str(tool) for tool in raw_tools if isinstance(tool, str))
    return ExecutionProfile(
        profile_id=profile_id,
        kind=kind,
        name=str(row.get("name") or ""),
        enabled=bool(row.get("enabled")),
        runtime=cast(ContainerRuntime | None, config.get("runtime")),
        image=str(config.get("image") or "") or None,
        tools=tools,
        repository_access=cast(RepositoryAccess, config.get("repository_access", "none")),
        writable_output=bool(config.get("writable_output", False)),
        credential_delivery=bool(config.get("credential_delivery", False)),
        credential_delta_quarantine=bool(config.get("credential_delta_quarantine", False)),
    )


def resolve_command_environment(
    store: Any,
    owner_principal_id: str,
    tool_name: str,
    *,
    probe: Any = probe_execution_profile,
) -> CommandEnvironmentResolution:
    checked_at = _checked_at()
    if tool_name not in {"shell", "run_command", "process"}:
        return CommandEnvironmentResolution(
            None,
            False,
            "selected_environment_tool_unsupported",
            True,
            (),
            None,
            checked_at,
        )
    profile_id = store.selected_execution_environment(owner_principal_id)
    profile = _selected_profile(store, owner_principal_id, profile_id)
    if profile is None or not profile.enabled:
        return CommandEnvironmentResolution(
            None, False, "selected_environment_unavailable", True, (), None, checked_at
        )
    if profile.kind != "local" and tool_name not in profile.tools:
        return CommandEnvironmentResolution(
            None,
            False,
            "selected_environment_tool_unsupported",
            True,
            profile.tools,
            profile.features,
            checked_at,
        )
    proof = probe(profile)
    return CommandEnvironmentResolution(
        profile,
        bool(proof.available),
        proof.reason_code,
        True,
        profile.tools,
        profile.features,
        proof.checked_at,
    )


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
