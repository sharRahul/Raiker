from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class StaticPolicyConfig:
    workspace_root: Path
    policy_id: str = "phase1-static"
    policy_version: str = "phase1-static-v1"
    allowed_read_actions: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "read_file",
                "list_directory",
                "glob",
                "grep",
                "stat_path",
                "diff_files",
                "git_status",
                "git_diff",
                "git_log",
                "memory_search",
                "memory_list",
                "memory_get",
                "user_create",
                "user_deactivate",
                "role_create",
                "role_grant",
                "role_revoke",
            }
        )
    )
    approval_required_actions: frozenset[str] = field(
        default_factory=lambda: frozenset({"shell", "write_file", "edit_file", "apply_patch", "memory_write", "memory_forget"})
    )
    denied_actions: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "write_file",
                "edit_file",
                "delete_file",
                "network_request",
                "web_fetch",
                "plugin_execute",
                "remote_execute",
            }
        )
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "workspace_root", Path(self.workspace_root).resolve())
