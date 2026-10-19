"""BR-D02 — the execution target a Build turn works against, stated and fingerprinted.

A project label is not a target. What a coding turn actually changes is a
folder, inside one repository, on one branch, executed through one command
environment. This module names those facts from the runtime's own sources — the
owner's repository selection, the folder on disk, ``git`` read through the same
credential-free environment the git tools use, and the selected execution
environment — and reduces the parts that must not move under a turn to one
fingerprint.

What the fingerprint covers, and what it deliberately leaves out:

* **Covered:** the folder, the repository's identity (its GitHub coordinate or
  its ``origin`` remote with any credentials stripped), the branch, and the
  selected command environment. A change to any of these means later commands,
  reads and checks no longer run against what the turn started on.
* **Not covered:** the commit. A Build turn may commit, and its own commit must
  not read as the target moving under it. The commit is recorded beside the
  fingerprint so a reviewer can still see where the turn began.
* **Not covered:** where code would be placed (sandbox or host). That answer is
  re-measured on a timer, and a measurement must not invent drift. It is shown,
  never fingerprinted.

The descriptor reads only. It starts no process other than read-only ``git``
queries, grants nothing, and is safe to call on every turn.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from raiker.contracts.ids import utc_now

#: The fields the fingerprint is computed over, in a fixed order.
FINGERPRINT_FIELDS: tuple[str, ...] = ("repo_kind", "identity", "folder", "branch", "environment")


def _git(root: Path, args: list[str]) -> str:
    from raiker.tools.git import _git as git  # the credential-free, hook-free read path

    try:
        proc = git(root, args, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def strip_credentials(remote: str) -> str:
    """A remote URL without a user, password or token in it.

    ``https://token@github.com/a/b.git`` and ``https://github.com/a/b.git`` name
    the same repository; only the second may be shown or stored. An scp-style
    ``git@host:path`` carries a login name, not a secret, and is kept.
    """
    text = remote.strip()
    if "://" not in text:
        return text
    try:
        parts = urlsplit(text)
    except ValueError:
        return ""
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, "", ""))


def _fingerprint(values: dict[str, Any]) -> str:
    material = json.dumps(
        {name: values.get(name) or "" for name in FINGERPRINT_FIELDS},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode()).hexdigest()


def _environment(store: Any, owner_principal_id: str) -> str:
    try:
        return str(store.selected_execution_environment(owner_principal_id) or "local_native")
    except Exception:  # noqa: BLE001 — an unreadable selection is stated, not guessed
        return ""


def _placement(store: Any, owner_principal_id: str, workspace_root: Path) -> tuple[str, str]:
    """Where code such as a test run would execute, and why — display only."""
    from raiker.execution.code_placement import place_code

    try:
        placement = place_code(store, owner_principal_id, ["python"], workspace_root)
    except Exception:  # noqa: BLE001 — unmeasured is reported as unknown
        return "unknown", "placement_unmeasured"
    return str(placement.kind), str(getattr(placement, "reason", "") or "")


def describe_target(
    store: Any,
    workspace_root: str | Path,
    owner_principal_id: str,
    repo: dict[str, Any] | None,
) -> dict[str, Any]:
    """The target a Build turn would run against right now, with its fingerprint.

    ``state`` is one of ``ready`` (a folder that exists), ``folder_missing`` (a
    local repository whose folder is gone or now escapes the workspace),
    ``remote_only`` (a GitHub coordinate with no checkout) and ``no_repository``.
    """
    from raiker.tools.filesystem import resolve_workspace_path

    root = Path(workspace_root).resolve()
    kind = str((repo or {}).get("kind") or "")
    values: dict[str, Any] = {
        "repo_id": (repo or {}).get("repo_id"),
        "repo_kind": kind or "none",
        "label": str((repo or {}).get("label") or ""),
        "identity": "",
        "folder": ".",
        "folder_exists": True,
        "git": False,
        "branch": "",
        "head": "",
        "environment": _environment(store, owner_principal_id),
    }
    state = "no_repository"
    if kind == "github":
        values["identity"] = f"github:{repo.get('github_owner')}/{repo.get('github_repo')}" if repo else ""
        values["branch"] = str((repo or {}).get("branch") or "")
        state = "remote_only"
    elif kind == "local":
        subpath = str((repo or {}).get("local_subpath") or "").strip() or "."
        values["folder"] = subpath
        folder: Path | None
        try:
            folder = resolve_workspace_path(root, subpath)
        except Exception:  # noqa: BLE001 — an escaping path is a missing target
            folder = None
        if folder is None or not folder.is_dir():
            values["folder_exists"] = False
            state = "folder_missing"
        else:
            state = "ready"
            if _git(folder, ["rev-parse", "--is-inside-work-tree"]) == "true":
                values["git"] = True
                values["branch"] = _git(folder, ["symbolic-ref", "--quiet", "--short", "HEAD"])
                values["head"] = _git(folder, ["rev-parse", "--short", "HEAD"])
                values["identity"] = strip_credentials(_git(folder, ["remote", "get-url", "origin"]))
            if not values["identity"]:
                values["identity"] = f"folder:{subpath}"
    placement, placement_reason = _placement(store, owner_principal_id, root)
    return {
        **values,
        "host": "this_computer" if values["environment"] in {"local_native", "native_sandbox", ""} else "remote",
        "state": state,
        "code_placement": placement,
        "code_placement_reason": placement_reason,
        "fingerprint": _fingerprint(values),
    }


def selected_repo(store: Any, owner_principal_id: str) -> dict[str, Any] | None:
    try:
        rows = store.list_code_repos(owner_principal_id)
    except Exception:  # noqa: BLE001 — no readable selection is no selection
        return None
    return next((dict(row) for row in rows if row.get("selected")), None)


def target_drift(started: dict[str, Any] | None, current: dict[str, Any] | None) -> list[str]:
    """The fingerprinted fields that differ between a turn's start and now.

    ``folder_exists`` is reported too: a folder that vanished has not changed
    name, but nothing about it can be verified any more.
    """
    if not started or not current:
        return []
    changed = [name for name in FINGERPRINT_FIELDS if (started.get(name) or "") != (current.get(name) or "")]
    if started.get("folder_exists") and not current.get("folder_exists"):
        changed.append("folder_exists")
    return changed


# ── The authority a turn started under (BR-07) ──────────────────────────────


def _github_repository(target: dict[str, Any]) -> str:
    """``github.com/owner/repo`` — the key delegations use — for a GitHub target, else empty."""
    identity = str(target.get("identity") or "")
    if identity.startswith("github:"):
        return "github.com/" + identity[len("github:") :]
    if identity.startswith("folder:") or not identity:
        return ""
    try:
        from raiker.runtime.git_credential import repository_key

        return str(repository_key(identity) or "")
    except Exception:  # noqa: BLE001 — a remote that is not GitHub has no delegation
        return ""


def authority_snapshot(store: Any, owner_principal_id: str, target: dict[str, Any]) -> dict[str, Any]:
    """BR-07 — the delegations and Git credential a Build turn starts under.

    Recorded with the target, never fingerprinted: they are not *where* the turn
    runs but *what it may do there*, and a resume compares them on their own.
    Only identifiers and timestamps — never a token.
    """
    from raiker.github.delegations import DelegationService, credential_owner

    account = credential_owner(store, owner_principal_id)
    repository = _github_repository(target)
    delegations: list[str] = []
    if repository:
        try:
            for row in DelegationService(store, account).delegations():
                if str(row.get("repository") or "").lower() == repository.lower() and row.get("state") == "active":
                    delegations.append(str(row["delegation_id"]))
        except Exception:  # noqa: BLE001 — unreadable delegations are none to depend on
            delegations = []
    credential: dict[str, str] | None = None
    try:
        selected = store.selected_git_credential(account)
    except Exception:  # noqa: BLE001
        selected = None
    if selected:
        credential = {
            "credential_id": str(selected.get("credential_id") or ""),
            "status": str(selected.get("status") or ""),
        }
    return {"repository": repository, "delegations": sorted(delegations), "credential": credential}


def delegation_summary(store: Any, owner_principal_id: str, target: dict[str, Any]) -> dict[str, Any]:
    """BR-01 — the repository delegations a Build turn here would act under, for the owner to read.

    Only active delegations on this target's GitHub identity, each with the
    operations it allows, its branch pattern, whether it may open a pull
    request, when it ends and how many actions it has left. Merging is never
    delegable, so it is never listed. Identifiers and patterns only.
    """
    from raiker.github.delegations import DelegationService, credential_owner

    account = credential_owner(store, owner_principal_id)
    repository = _github_repository(target)
    rows: list[dict[str, Any]] = []
    if repository:
        try:
            for row in DelegationService(store, account).delegations():
                if str(row.get("repository") or "").lower() != repository.lower() or row.get("state") != "active":
                    continue
                limit = row.get("max_actions")
                rows.append(
                    {
                        "delegation_id": str(row["delegation_id"]),
                        "operations": [str(item) for item in row.get("operations") or []],
                        "branch_pattern": row.get("branch_pattern"),
                        "allow_pull_request": bool(row.get("allow_pull_request")),
                        "expires_at": str(row.get("expires_at") or ""),
                        "actions_left": None if limit is None else max(0, int(limit) - int(row.get("actions_used") or 0)),
                    }
                )
        except Exception:  # noqa: BLE001 — unreadable delegations are shown as none
            rows = []
    try:
        credential = bool(store.selected_git_credential(account))
    except Exception:  # noqa: BLE001
        credential = False
    return {"repository": repository or None, "delegations": rows, "git_credential": credential}


def authority_drift(store: Any, owner_principal_id: str, started: dict[str, Any] | None) -> list[str]:
    """What the turn's recorded authority lost since it started, in words a reason code can carry.

    ``delegation_<state>`` for a delegation the turn started under that is no
    longer active (revoked, expired, exhausted, or gone), and
    ``credential_changed`` when the Git credential in use was removed, replaced
    by another, or changed state (expired, revoked, failed validation). A turn that started with no delegation and no credential has
    nothing to lose and never drifts here.
    """
    from raiker.github.delegations import DelegationError, DelegationService, credential_owner

    authority = (started or {}).get("authority")
    if not isinstance(authority, dict):
        return []
    account = credential_owner(store, owner_principal_id)
    reasons: list[str] = []
    service = DelegationService(store, account)
    for delegation_id in authority.get("delegations") or []:
        try:
            state = str(service.get(str(delegation_id)).get("state") or "missing")
        except (DelegationError, KeyError):
            state = "missing"
        except Exception:  # noqa: BLE001 — unreadable is not proof it still holds
            state = "unreadable"
        if state != "active":
            reasons.append(f"delegation_{state}")
    recorded = authority.get("credential")
    if isinstance(recorded, dict) and recorded.get("credential_id"):
        try:
            current = store.selected_git_credential(account)
        except Exception:  # noqa: BLE001
            current = None
        if (
            not current
            or str(current.get("credential_id") or "") != str(recorded.get("credential_id"))
            or str(current.get("status") or "") != str(recorded.get("status") or "")
        ):
            reasons.append("credential_changed")
    return sorted(set(reasons))


# ── A scheduled Build task's repository (BR-02 / BR-D03) ────────────────────


def record_task_target(store: Any, *, owner_principal_id: str, task_id: str, target: dict[str, Any]) -> bool:
    """Remember the repository a Build task was scheduled for. ``False`` when there is none."""
    if not target.get("repo_id"):
        return False
    with store.connect() as connection:
        connection.execute(
            """INSERT OR IGNORE INTO build_task_targets
               (task_id, owner_principal_id, repo_id, label, identity, folder, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                task_id,
                owner_principal_id,
                str(target["repo_id"]),
                str(target.get("label") or ""),
                str(target.get("identity") or ""),
                str(target.get("folder") or "."),
                utc_now(),
            ),
        )
    return True


def load_task_target(store: Any, *, owner_principal_id: str, task_id: str) -> dict[str, Any] | None:
    with store.connect() as connection:
        row = connection.execute(
            "SELECT * FROM build_task_targets WHERE owner_principal_id = ? AND task_id = ?",
            (owner_principal_id, task_id),
        ).fetchone()
    return dict(row) if row is not None else None


def task_target_mismatch(scheduled: dict[str, Any] | None, current: dict[str, Any]) -> list[str]:
    """What differs between the repository a task was scheduled for and Build's target now.

    ``repository`` when Build is pointed at another connected repository (or
    none), ``identity`` or ``folder`` when the same reference now names a
    different remote or folder. Empty when the task may run.
    """
    if not scheduled:
        return []
    if str(current.get("repo_id") or "") != str(scheduled.get("repo_id") or ""):
        return ["repository"]
    changed: list[str] = []
    if str(current.get("identity") or "") != str(scheduled.get("identity") or ""):
        changed.append("identity")
    if str(current.get("folder") or ".") != str(scheduled.get("folder") or "."):
        changed.append("folder")
    return changed


# ── The turn binding ─────────────────────────────────────────────────────────


def record_turn_target(
    store: Any, *, owner_principal_id: str, session_id: str, turn_id: str, target: dict[str, Any]
) -> None:
    """Remember the target a Build turn started on. The first record wins."""
    with store.connect() as connection:
        connection.execute(
            """INSERT OR IGNORE INTO build_turn_targets
               (owner_principal_id, session_id, turn_id, repo_id, target_json, fingerprint, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                owner_principal_id,
                session_id,
                turn_id,
                target.get("repo_id"),
                json.dumps(target, sort_keys=True),
                str(target.get("fingerprint") or ""),
                utc_now(),
            ),
        )


def load_turn_target(store: Any, *, owner_principal_id: str, turn_id: str) -> dict[str, Any] | None:
    with store.connect() as connection:
        row = connection.execute(
            "SELECT target_json FROM build_turn_targets WHERE owner_principal_id = ? AND turn_id = ?",
            (owner_principal_id, turn_id),
        ).fetchone()
    if row is None:
        return None
    try:
        value = json.loads(str(row["target_json"]))
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def running_turns_on_folder(
    store: Any,
    *,
    owner_principal_id: str,
    folder: str,
    exclude_session_id: str,
    window_seconds: int,
) -> list[str]:
    """BR-03 — other conversations' Build turns still running against *folder*.

    A turn counts while its row says ``running`` and it started within
    *window_seconds*: a host that died mid-turn leaves a row that would
    otherwise hold the folder for ever.
    """
    from datetime import UTC, datetime, timedelta

    cutoff = datetime.now(UTC) - timedelta(seconds=window_seconds)
    with store.connect() as connection:
        rows = connection.execute(
            """SELECT b.turn_id, b.session_id, b.target_json, t.created_at
               FROM build_turn_targets b JOIN turns t ON t.turn_id = b.turn_id
               WHERE b.owner_principal_id = ? AND b.session_id != ? AND t.status = 'running'""",
            (owner_principal_id, exclude_session_id),
        ).fetchall()
    running: list[str] = []
    for row in rows:
        try:
            started = datetime.fromisoformat(str(row["created_at"]).replace("Z", "+00:00"))
            target = json.loads(str(row["target_json"]))
        except (TypeError, ValueError):
            continue
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        if started < cutoff or not isinstance(target, dict):
            continue
        if target.get("repo_kind") == "local" and str(target.get("folder") or ".") == folder:
            running.append(str(row["turn_id"]))
    return running
