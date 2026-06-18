from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionProfile:
    profile_id: str
    kind: str
    default_state: str = "disabled_until_configured"
    requires_approval: bool = True


DEFAULT_EXECUTION_PROFILES = (
    ExecutionProfile("local_native", "local", "enabled_policy_gated", True),
    ExecutionProfile("container_default", "container"),
    ExecutionProfile("ssh_default", "ssh"),
    ExecutionProfile("daytona_default", "daytona"),
)


def list_execution_profiles() -> list[ExecutionProfile]:
    return list(DEFAULT_EXECUTION_PROFILES)


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
