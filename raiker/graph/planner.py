from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from raiker.contracts.ids import new_id, utc_now
from raiker.graph.governance import GRAPH_RUNTIME_DISABLED_REASON

DEFAULT_EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "target",
    "vendor",
}
DEFAULT_MAX_FILES = 500
DEFAULT_MAX_FILE_SIZE_BYTES = 256 * 1024


@dataclass(frozen=True)
class PathDecision:
    path: str
    included: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {"path": self.path, "included": self.included, "reason": self.reason}


@dataclass(frozen=True)
class GraphCodemapIndexPlan:
    plan_id: str
    workspace_root: str
    included_paths: list[str]
    excluded_paths: list[dict[str, object]]
    max_files: int
    max_file_size_bytes: int
    can_index: bool
    requires_approval: bool
    runtime_indexing_enabled: bool
    reasons: list[str]
    node_count_estimate: int
    edge_count_estimate: int
    policy_decision: str
    created_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "workspace_root": self.workspace_root,
            "included_paths": self.included_paths,
            "excluded_paths": self.excluded_paths,
            "max_files": self.max_files,
            "max_file_size_bytes": self.max_file_size_bytes,
            "can_index": self.can_index,
            "requires_approval": self.requires_approval,
            "runtime_indexing_enabled": self.runtime_indexing_enabled,
            "reasons": self.reasons,
            "node_count_estimate": self.node_count_estimate,
            "edge_count_estimate": self.edge_count_estimate,
            "policy_decision": self.policy_decision,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class GraphCodemapPlanner:
    workspace_root: Path
    max_files: int = DEFAULT_MAX_FILES
    max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES
    excluded_dirs: set[str] = field(default_factory=lambda: set(DEFAULT_EXCLUDED_DIRS))

    def __post_init__(self) -> None:
        object.__setattr__(self, "workspace_root", Path(self.workspace_root).resolve())

    def _relative(self, path: Path) -> str:
        return path.relative_to(self.workspace_root).as_posix() or "."

    def decide_path(self, path: str | Path) -> PathDecision:
        raw = Path(path)
        candidate = raw if raw.is_absolute() else self.workspace_root / raw
        if candidate.is_symlink():
            try:
                candidate.resolve(strict=True).relative_to(self.workspace_root)
            except (FileNotFoundError, ValueError):
                display = candidate.name if candidate.is_absolute() else str(path)
                return PathDecision(display, False, "symlink_escape")
        try:
            resolved = candidate.resolve(strict=False)
            resolved.relative_to(self.workspace_root)
        except ValueError:
            return PathDecision(str(path), False, "outside_workspace_root")
        rel = self._relative(resolved)
        parts = set(Path(rel).parts)
        ignored = sorted(parts & self.excluded_dirs)
        if ignored:
            return PathDecision(rel, False, f"excluded_directory:{ignored[0]}")
        if any(part.startswith(".") and part not in {"."} for part in Path(rel).parts):
            return PathDecision(rel, False, "hidden_or_system_path")
        if candidate.is_file():
            size = candidate.stat().st_size
            if size > self.max_file_size_bytes:
                return PathDecision(rel, False, "file_too_large")
            if _is_binary(candidate):
                return PathDecision(rel, False, "binary_file")
        return PathDecision(rel, True, "eligible_for_dry_run_planning")

    def create_plan(self) -> GraphCodemapIndexPlan:
        included: list[str] = []
        excluded: list[dict[str, object]] = []
        reasons = [GRAPH_RUNTIME_DISABLED_REASON, "no_graph_records_written", "no_background_indexing"]
        for current_root, dirnames, filenames in os.walk(self.workspace_root):
            root_path = Path(current_root)
            kept_dirs: list[str] = []
            for dirname in sorted(dirnames):
                decision = self.decide_path(root_path / dirname)
                if decision.included:
                    kept_dirs.append(dirname)
                else:
                    excluded.append(decision.to_dict())
            dirnames[:] = kept_dirs
            for filename in sorted(filenames):
                if len(included) >= self.max_files:
                    excluded.append(PathDecision(filename, False, "max_files_reached").to_dict())
                    continue
                decision = self.decide_path(root_path / filename)
                if decision.included:
                    included.append(decision.path)
                else:
                    excluded.append(decision.to_dict())
        return GraphCodemapIndexPlan(
            plan_id=new_id("graphplan_"),
            workspace_root=str(self.workspace_root),
            included_paths=included,
            excluded_paths=excluded,
            max_files=self.max_files,
            max_file_size_bytes=self.max_file_size_bytes,
            can_index=False,
            requires_approval=True,
            runtime_indexing_enabled=False,
            reasons=reasons,
            node_count_estimate=len(included),
            edge_count_estimate=0,
            policy_decision=GRAPH_RUNTIME_DISABLED_REASON,
            created_at=utc_now(),
        )


def _is_binary(path: Path) -> bool:
    try:
        chunk = path.read_bytes()[:1024]
    except OSError:
        return False
    return b"\x00" in chunk


def create_graph_codemap_plan(workspace_root: str | Path = ".") -> GraphCodemapIndexPlan:
    return GraphCodemapPlanner(Path(workspace_root)).create_plan()
