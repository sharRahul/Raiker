from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from raiker.readiness.contracts import (
    canonical_json,
    deterministic_dict,
    deterministic_hash_id,
    sorted_tuple,
    validate_json_safe_metadata,
    validate_non_empty_strings,
)

STORAGE_CLEANUP_READINESS_DISABLED_REASON = (
    "phase3_slice_m_metadata_only_storage_cleanup_execution_not_enabled"
)
REQUIRED_PREENABLEMENT_GATES = (
    "cleanup_governance_policy_defined",
    "retention_to_cleanup_authorization_defined",
    "deletion_safety_policy_defined",
    "purge_safety_policy_defined",
    "tombstone_policy_defined",
    "rollback_policy_defined",
    "approval_handoff_policy_defined",
    "audit_evidence_policy_defined",
    "worker_scheduler_daemon_policy_defined",
    "test_coverage_defined",
)
DISABLED_RUNTIME_FLAGS = {
    "cleanup_execution_enabled": False,
    "deletion_execution_enabled": False,
    "purge_execution_enabled": False,
    "tombstone_execution_enabled": False,
    "rollback_execution_enabled": False,
    "cleanup_jobs_enabled": False,
    "deletion_jobs_enabled": False,
    "worker_queues_enabled": False,
    "workers_enabled": False,
    "schedulers_enabled": False,
    "file_watchers_enabled": False,
    "daemons_enabled": False,
    "runtime_execution_enabled": False,
}


@dataclass(frozen=True)
class StorageCleanupExecutionReadinessContract:
    workspace_id: str = "local-workspace"
    target_capability: str = "storage_cleanup_execution"
    slice_id: str = "phase3_slice_m"
    readiness_version: str = "1.0"
    required_gates: tuple[str, ...] = REQUIRED_PREENABLEMENT_GATES
    satisfied_gates: tuple[str, ...] = ()
    blockers: tuple[str, ...] = REQUIRED_PREENABLEMENT_GATES
    disabled_reason: str = STORAGE_CLEANUP_READINESS_DISABLED_REASON
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
                "blockers must be non-empty while storage cleanup execution is disabled"
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
        return deterministic_hash_id("scer", payload)

    @property
    def ready_for_cleanup_execution(self) -> bool:
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "readiness_id": self.readiness_id,
            "workspace_id": self.workspace_id,
            "target_capability": self.target_capability,
            "slice_id": self.slice_id,
            "readiness_version": self.readiness_version,
            "metadata_only": True,
            "ready_for_cleanup_execution": self.ready_for_cleanup_execution,
            "required_gates": list(self.required_gates),
            "satisfied_gates": list(self.satisfied_gates),
            "blockers": list(self.blockers),
            "disabled_reason": self.disabled_reason,
            **DISABLED_RUNTIME_FLAGS,
            "metadata": deterministic_dict(self.metadata),
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


def create_storage_cleanup_execution_readiness_contract(
    **kwargs: Any,
) -> StorageCleanupExecutionReadinessContract:
    satisfied = tuple(sorted(kwargs.pop("satisfied_gates", ())))
    blockers = tuple(gate for gate in REQUIRED_PREENABLEMENT_GATES if gate not in set(satisfied))
    return StorageCleanupExecutionReadinessContract(
        satisfied_gates=satisfied, blockers=blockers, **kwargs
    )
