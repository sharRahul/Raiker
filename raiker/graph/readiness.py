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

GRAPH_READINESS_DISABLED_REASON = "phase3_slice_j_metadata_only_graph_codemap_indexing_not_enabled"
REQUIRED_READINESS_GATES = (
    "source_scope_defined",
    "path_policy_defined",
    "secret_redaction_defined",
    "incremental_update_strategy_defined",
    "storage_schema_defined",
    "event_catalog_defined",
    "approval_policy_defined",
    "rollback_plan_defined",
    "worker_scheduler_plan_defined",
    "test_coverage_defined",
)
DISABLED_RUNTIME_FLAGS = {
    "graph_indexing_enabled": False,
    "graph_writes_enabled": False,
    "codemap_indexing_enabled": False,
    "indexing_jobs_enabled": False,
    "runtime_jobs_enabled": False,
    "workers_enabled": False,
    "schedulers_enabled": False,
    "file_watchers_enabled": False,
    "daemons_enabled": False,
    "runtime_execution_enabled": False,
}


@dataclass(frozen=True)
class GraphCodemapReadinessContract:
    workspace_id: str = "local-workspace"
    target_capability: str = "graph_codemap_indexing"
    slice_id: str = "phase3_slice_j"
    readiness_version: str = "1.0"
    required_gates: tuple[str, ...] = REQUIRED_READINESS_GATES
    satisfied_gates: tuple[str, ...] = ()
    blockers: tuple[str, ...] = REQUIRED_READINESS_GATES
    disabled_reason: str = GRAPH_READINESS_DISABLED_REASON
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
            raise ValueError("blockers must be non-empty while graph/codemap indexing is disabled")
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
        return deterministic_hash_id("gcr", payload)

    @property
    def ready_for_indexing(self) -> bool:
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "readiness_id": self.readiness_id,
            "workspace_id": self.workspace_id,
            "target_capability": self.target_capability,
            "slice_id": self.slice_id,
            "readiness_version": self.readiness_version,
            "metadata_only": True,
            "ready_for_indexing": self.ready_for_indexing,
            "required_gates": list(self.required_gates),
            "satisfied_gates": list(sorted_tuple(self.satisfied_gates)),
            "blockers": list(sorted_tuple(self.blockers)),
            "disabled_reason": self.disabled_reason,
            **DISABLED_RUNTIME_FLAGS,
            "metadata": deterministic_dict(self.metadata),
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


def create_readiness_contract(**kwargs: Any) -> GraphCodemapReadinessContract:
    satisfied = tuple(sorted(kwargs.pop("satisfied_gates", ())))
    blockers = tuple(
        kwargs.pop(
            "blockers",
            tuple(gate for gate in REQUIRED_READINESS_GATES if gate not in set(satisfied)),
        )
    )
    return GraphCodemapReadinessContract(satisfied_gates=satisfied, blockers=blockers, **kwargs)
