from __future__ import annotations

import shutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from raiker.execution.profiles import ExecutionProfile, validate_execution_profile
from raiker.readiness.contracts import (
    canonical_json,
    deterministic_dict,
    deterministic_hash_id,
    sorted_tuple,
    validate_json_safe_metadata,
    validate_non_empty_strings,
)
from raiker.runtime.executors.containers import container_image_allowlist

REMOTE_CONTAINER_CLOUD_DISABLED_REASON = (
    "phase3_slice_p_metadata_only_remote_container_cloud_not_enabled"
)
REQUIRED_PREENABLEMENT_GATES = (
    "remote_execution_policy_defined",
    "container_execution_policy_defined",
    "cloud_execution_policy_defined",
    "hosted_routine_policy_defined",
    "runtime_job_policy_defined",
    "job_dispatch_policy_defined",
    "worker_queue_policy_defined",
    "worker_policy_defined",
    "scheduler_policy_defined",
    "file_watcher_policy_defined",
    "daemon_policy_defined",
    "client_transport_policy_defined",
    "external_dispatch_policy_defined",
    "credential_materialization_policy_defined",
    "secret_injection_policy_defined",
    "provider_integration_policy_defined",
    "sandbox_runtime_policy_defined",
    "process_execution_policy_defined",
    "shell_execution_policy_defined",
    "network_execution_policy_defined",
    "runtime_execution_policy_defined",
    "test_coverage_defined",
)
DISABLED_RUNTIME_FLAGS = {
    "remote_execution_enabled": False,
    "container_execution_enabled": False,
    "cloud_execution_enabled": False,
    "hosted_routines_enabled": False,
    "runtime_jobs_enabled": False,
    "job_dispatch_enabled": False,
    "worker_queues_enabled": False,
    "workers_enabled": False,
    "schedulers_enabled": False,
    "file_watchers_enabled": False,
    "daemons_enabled": False,
    "client_transport_enabled": False,
    "external_dispatch_enabled": False,
    "credential_materialization_enabled": False,
    "secret_injection_enabled": False,
    "provider_integrations_enabled": False,
    "sandbox_runtime_enabled": False,
    "process_execution_enabled": False,
    "shell_execution_enabled": False,
    "network_execution_enabled": False,
    "runtime_execution_enabled": False,
}


def container_readiness(
    *,
    gate_enabled: bool,
    profiles: Sequence[ExecutionProfile],
    image_allowlist: frozenset[str] | None = None,
    executable_available: Callable[[str], bool] | None = None,
    bridge_available: bool = True,
) -> dict[str, Any]:
    if not gate_enabled:
        return {
            "ready_for_container_execution": False,
            "container_execution_enabled": False,
            "container_blockers": ["container_gate_disabled"],
        }
    candidates = [profile for profile in profiles if profile.enabled and profile.kind == "container"]
    if not candidates:
        return {
            "ready_for_container_execution": False,
            "container_execution_enabled": False,
            "container_blockers": ["container_profile_missing"],
        }
    allowed = image_allowlist if image_allowlist is not None else container_image_allowlist()
    executable = executable_available or (lambda name: shutil.which(name) is not None)
    blockers: list[str] = []
    for profile in candidates:
        reason = validate_execution_profile(profile)
        if reason:
            blockers.append(reason)
            continue
        assert profile.runtime is not None
        assert profile.image is not None
        if profile.image not in allowed:
            blockers.append(f"container_image_not_allowed:{profile.profile_id}")
            continue
        if not executable(profile.runtime):
            blockers.append(f"container_runtime_unavailable:{profile.runtime}")
            continue
        if not bridge_available:
            blockers.append(f"container_tool_bridge_unavailable:{profile.profile_id}")
            continue
        return {
            "ready_for_container_execution": True,
            "container_execution_enabled": True,
            "container_blockers": [],
        }
    return {
        "ready_for_container_execution": False,
        "container_execution_enabled": False,
        "container_blockers": sorted(set(blockers)),
    }


@dataclass(frozen=True)
class RemoteContainerCloudReadinessContract:
    workspace_id: str = "local-workspace"
    target_capability: str = "remote_container_cloud_execution"
    slice_id: str = "phase3_slice_p"
    readiness_version: str = "1.0"
    required_gates: tuple[str, ...] = REQUIRED_PREENABLEMENT_GATES
    satisfied_gates: tuple[str, ...] = ()
    blockers: tuple[str, ...] = REQUIRED_PREENABLEMENT_GATES
    disabled_reason: str = REMOTE_CONTAINER_CLOUD_DISABLED_REASON
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "workspace_id",
            "target_capability",
            "slice_id",
            "readiness_version",
            "disabled_reason",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{field_name} must be a non-empty string")
        validate_non_empty_strings("required_gates", self.required_gates)
        if not isinstance(self.satisfied_gates, tuple) or any(
            not isinstance(value, str) or not value for value in self.satisfied_gates
        ):
            raise ValueError("satisfied_gates must be a tuple of non-empty strings")
        if not self.blockers:
            raise ValueError(
                "blockers must be non-empty while remote/container/cloud execution is disabled"
            )
        validate_non_empty_strings("blockers", self.blockers)
        validate_json_safe_metadata(self.metadata)

    @property
    def readiness_id(self) -> str:
        payload = {
            "workspace_id": self.workspace_id,
            "target_capability": self.target_capability,
            "slice_id": self.slice_id,
            "readiness_version": self.readiness_version,
            "required_gates": list(self.required_gates),
            "satisfied_gates": list(sorted_tuple(self.satisfied_gates)),
            "blockers": list(sorted_tuple(self.blockers)),
        }
        return deterministic_hash_id("rccr", payload)

    @property
    def ready_for_remote_execution(self) -> bool:
        return False

    @property
    def ready_for_container_execution(self) -> bool:
        return False

    @property
    def ready_for_cloud_execution(self) -> bool:
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "readiness_id": self.readiness_id,
            "workspace_id": self.workspace_id,
            "target_capability": self.target_capability,
            "slice_id": self.slice_id,
            "readiness_version": self.readiness_version,
            "metadata_only": True,
            "ready_for_remote_execution": self.ready_for_remote_execution,
            "ready_for_container_execution": self.ready_for_container_execution,
            "ready_for_cloud_execution": self.ready_for_cloud_execution,
            "required_gates": list(self.required_gates),
            "satisfied_gates": list(self.satisfied_gates),
            "blockers": list(self.blockers),
            "disabled_reason": self.disabled_reason,
            **DISABLED_RUNTIME_FLAGS,
            "metadata": deterministic_dict(self.metadata),
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


def create_remote_container_cloud_readiness_contract(
    **kwargs: Any,
) -> RemoteContainerCloudReadinessContract:
    satisfied = tuple(sorted(kwargs.pop("satisfied_gates", ())))
    blockers = tuple(gate for gate in REQUIRED_PREENABLEMENT_GATES if gate not in set(satisfied))
    return RemoteContainerCloudReadinessContract(
        satisfied_gates=satisfied, blockers=blockers, **kwargs
    )
