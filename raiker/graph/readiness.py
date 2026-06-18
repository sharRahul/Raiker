from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

_JSON_SAFE_TYPES = (str, int, float, bool, type(None))

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
        for field_name in ("workspace_id", "target_capability", "slice_id", "readiness_version", "disabled_reason"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{field_name} must be a non-empty string")
        for field_name in ("required_gates", "satisfied_gates", "blockers"):
            values = getattr(self, field_name)
            if not isinstance(values, tuple) or any(not isinstance(value, str) or not value for value in values):
                raise ValueError(f"{field_name} must be a tuple of non-empty strings")
        if not self.blockers:
            raise ValueError("blockers must be non-empty while graph/codemap indexing is disabled")
        self._json_safe_metadata(self.metadata)

    @classmethod
    def _json_safe_metadata(cls, value: Any) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if not isinstance(key, str):
                    raise ValueError("metadata keys must be strings")
                cls._json_safe_metadata(nested)
            return
        if isinstance(value, list | tuple):
            for nested in value:
                cls._json_safe_metadata(nested)
            return
        if not isinstance(value, _JSON_SAFE_TYPES):
            raise ValueError("metadata must contain only JSON-safe values")

    @property
    def readiness_id(self) -> str:
        payload = {
            "workspace_id": self.workspace_id,
            "target_capability": self.target_capability,
            "slice_id": self.slice_id,
            "readiness_version": self.readiness_version,
            "required_gates": list(self.required_gates),
            "satisfied_gates": sorted(self.satisfied_gates),
            "blockers": sorted(self.blockers),
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]
        return f"gcr_{digest}"

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
            "satisfied_gates": list(self.satisfied_gates),
            "blockers": list(self.blockers),
            "disabled_reason": self.disabled_reason,
            **DISABLED_RUNTIME_FLAGS,
            "metadata": {key: self.metadata[key] for key in sorted(self.metadata)},
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


def create_readiness_contract(**kwargs: Any) -> GraphCodemapReadinessContract:
    satisfied = tuple(sorted(kwargs.pop("satisfied_gates", ())))
    blockers = tuple(gate for gate in REQUIRED_READINESS_GATES if gate not in set(satisfied))
    return GraphCodemapReadinessContract(satisfied_gates=satisfied, blockers=blockers, **kwargs)
