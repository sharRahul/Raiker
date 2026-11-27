"""Trusted task-copy eligibility shared by approval review and dispatch.

The action's arguments describe a target, never proof of confinement. Eligibility
comes from the runtime's owner-bound task tree and a fresh measured boundary.
Unknown tools and destinations retain their ordinary approval requirement.
"""

from pathlib import Path
from typing import Any

from raiker.contracts.models import PolicyDecision, ToolAction
from raiker.execution.code_placement import sandbox_available
from raiker.execution.task_tree import TaskTreeAuthority
from raiker.tools.filesystem import FilesystemSafetyError, patch_target_paths


def ordinary_approval(action: ToolAction, decision: PolicyDecision) -> bool:
    """Only the ordinary policy pause can be satisfied by a preparation scope."""
    from raiker.runtime.authority.critical import classify_critical

    return (
        decision.decision == "needs_approval"
        and action.risk_level != "critical"
        and classify_critical(action.tool_name, action.tool_name, action.arguments) is None
        and decision.reasons == [
            f"{action.tool_name}_requires_approval", "phase2_action_bound_approval_required",
        ]
    )


def internal_preparation(
    authority: Any, *, owner_principal_id: str, session_id: str | None,
    tool_name: str, arguments: dict[str, Any],
) -> bool:
    """A local task draft is bookkeeping, never permission to run or schedule it."""
    return (
        isinstance(authority, TaskTreeAuthority)
        and authority.tree.owner_principal_id == owner_principal_id
        and authority.tree.session_id == session_id
        and tool_name == "create_task"
        and set(arguments) <= {"title", "description"}
        and isinstance(arguments.get("title"), str)
        and 0 < len(arguments["title"].strip()) <= 500
        and ("description" not in arguments or isinstance(arguments["description"], str))
    )


def confined_preparation(
    authority: Any,
    *,
    workspace_root: Path,
    owner_principal_id: str,
    session_id: str | None,
    tool_name: str,
    arguments: dict[str, Any],
) -> bool:
    """Whether preparation is confined to this owner's disposable task tree."""
    if not isinstance(authority, TaskTreeAuthority):
        return False
    tree = authority.tree
    if tree.owner_principal_id != owner_principal_id or tree.session_id != session_id:
        return False
    if tool_name in {"shell", "process"}:
        # Commands are launched only by NativeSandboxBackend, which takes a
        # disposable copy and measures the boundary again at launch. No remote
        # environment, extra egress, credentials or long-lived process is
        # delegated by the sandbox posture.
        if any(arguments.get(key) for key in (
            "background", "interactive", "network_policy_id", "credential_bindings",
        )):
            return False
        return (
            tree.registry.bound_root(owner_principal_id, session_id or "") is not None
            and sandbox_available(workspace_root, fresh=True)
        )
    if tool_name not in {"write_file", "edit_file", "apply_patch"}:
        return False
    requested = arguments.get("path")
    targets = (
        patch_target_paths(str(arguments.get("patch", "")))
        if tool_name == "apply_patch" else [requested]
    )
    if not targets or any(not isinstance(path, str) or not path for path in targets):
        return False
    try:
        for requested_path in targets:
            target = authority.resolve_write(str(requested_path)).path
            if not any(target != root and root in target.parents for _, root in tree.copy_roots()):
                return False
    except (FilesystemSafetyError, OSError, ValueError):
        return False
    return sandbox_available(workspace_root, fresh=True)
