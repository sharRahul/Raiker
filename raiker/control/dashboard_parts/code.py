# mypy: disable-error-code="misc"
"""Code workspace repositories and the repository code map (GCR-43).

One part of :class:`raiker.control.dashboard.DashboardService`, which inherits it. Every method
is typed against the whole store (``self: DashboardService``), so a call into another
part is checked exactly as it was when every method lived in one class. mypy
reports that self-type as ``misc`` on a mixin, which is the one code this file
turns off.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from raiker.contracts.ids import new_id
from raiker.control.dashboard import _GITHUB_NAME, _GITHUB_REF, CodeReposView, CodeRepoView
from raiker.control.dtos import ControlResult
from raiker.events.writer import EventLogWriter
from raiker.tools.git import resolve_repository_root

if TYPE_CHECKING:
    from raiker.control.dashboard import DashboardService


class CodeService:

    # The Build workspace points a coding chat at a repository. Connecting one is
    # governance-neutral bookkeeping: a local folder must resolve inside the
    # workspace (fail closed), a GitHub repository records only its `owner/repo`
    # coordinate, and neither stores a credential nor grants a capability. GitHub
    # content still reaches a turn only through the brokered `github_read` tool
    # under the `connector_github_runtime` gate, which is disabled/fail-closed
    # until the owner enables it.

    def list_code_repos(self: DashboardService, *, owner_principal_id: str) -> CodeReposView:
        from raiker.runtime.connectors import GITHUB_TOKEN_ENV

        gate = self.control.get_capability_gate("connector_github_runtime", owner_principal_id)
        rows = self.store.list_code_repos(owner_principal_id)
        return CodeReposView(
            repos=tuple(self._code_repo_view(row) for row in rows),
            selected_repo_id=next(
                (str(row["repo_id"]) for row in rows if row.get("selected")), None
            ),
            github_gate_state=gate.state if gate is not None else "unknown",
            github_decision_mode=gate.decision_mode if gate is not None else "ask",
            github_token_configured=bool(os.environ.get(GITHUB_TOKEN_ENV, "").strip()),
        )

    def _code_repo_view(self: DashboardService, row: dict[str, Any]) -> CodeRepoView:
        local_subpath = row.get("local_subpath")
        exists = False
        if local_subpath:
            candidate = (self.workspace_root / str(local_subpath)).resolve()
            root = self.workspace_root.resolve()
            exists = (candidate == root or root in candidate.parents) and candidate.is_dir()
        return CodeRepoView(
            repo_id=str(row["repo_id"]),
            kind=str(row["kind"]),
            label=str(row["label"]),
            selected=bool(row.get("selected")),
            created_at=str(row["created_at"]),
            local_subpath=str(local_subpath) if local_subpath else None,
            local_exists=exists,
            github_owner=str(row["github_owner"]) if row.get("github_owner") else None,
            github_repo=str(row["github_repo"]) if row.get("github_repo") else None,
            branch=str(row["branch"]) if row.get("branch") else None,
        )

    def connect_local_repo(
        self: DashboardService, raw_path: str, *, owner_principal_id: str, user_id: str | None = None
    ) -> ControlResult:
        """Reference a workspace-contained folder as a repository.

        Reuses the same containment check as every other workspace path read:
        a path that resolves outside the workspace, or does not exist, is refused.
        """
        try:
            relative_path, path = self._workspace_source(raw_path)
        except ValueError as exc:
            reason = str(exc).replace("brain_source", "repo")
            return ControlResult(ok=False, reason_code=reason)
        if not path.is_dir():
            return ControlResult(ok=False, reason_code="repo_not_a_directory")
        repo_id = new_id("repo_")
        label = Path(relative_path).name or relative_path
        if not self.store.insert_code_repo(
            repo_id=repo_id,
            owner_principal_id=owner_principal_id,
            kind="local",
            label=label,
            local_subpath=relative_path,
        ):
            return ControlResult(ok=False, reason_code="repo_already_connected")
        self._record_repo_event(
            "code_repo_connected",
            owner_principal_id,
            user_id,
            {"repo_id": repo_id, "kind": "local", "local_subpath": relative_path},
        )
        indexed = self._index_code_map(relative_path, repo_id, owner_principal_id, user_id)
        return ControlResult(
            ok=True,
            data={
                "repo_id": repo_id,
                "kind": "local",
                "local_subpath": relative_path,
                "code_map": indexed,
            },
        )

    def connect_github_repo(
        self: DashboardService,
        owner: str,
        repo: str,
        branch: str | None,
        *,
        owner_principal_id: str,
        user_id: str | None = None,
    ) -> ControlResult:
        """Record a GitHub `owner/repo` coordinate. Performs no network call.

        Reads against it later go through the brokered ``github_read`` tool, so a
        disabled ``connector_github_runtime`` gate still fails closed.
        """
        clean_owner = owner.strip()
        clean_repo = repo.strip()
        clean_branch = (branch or "").strip() or None
        if not _GITHUB_NAME.fullmatch(clean_owner) or not _GITHUB_NAME.fullmatch(clean_repo):
            return ControlResult(ok=False, reason_code="invalid_github_repo")
        if clean_branch is not None and not _GITHUB_REF.fullmatch(clean_branch):
            return ControlResult(ok=False, reason_code="invalid_github_branch")
        repo_id = new_id("repo_")
        if not self.store.insert_code_repo(
            repo_id=repo_id,
            owner_principal_id=owner_principal_id,
            kind="github",
            label=f"{clean_owner}/{clean_repo}",
            github_owner=clean_owner,
            github_repo=clean_repo,
            branch=clean_branch,
        ):
            return ControlResult(ok=False, reason_code="repo_already_connected")
        self._record_repo_event(
            "code_repo_connected",
            owner_principal_id,
            user_id,
            {
                "repo_id": repo_id,
                "kind": "github",
                "github_owner": clean_owner,
                "github_repo": clean_repo,
                "branch": clean_branch or "",
            },
        )
        return ControlResult(
            ok=True,
            data={
                "repo_id": repo_id,
                "kind": "github",
                "label": f"{clean_owner}/{clean_repo}",
                "branch": clean_branch,
            },
        )

    def disconnect_code_repo(
        self: DashboardService, repo_id: str, *, owner_principal_id: str, user_id: str | None = None
    ) -> ControlResult:
        """Forget a repository reference. Never touches the folder or the remote."""
        if not self.store.delete_code_repo(owner_principal_id, repo_id):
            return ControlResult(ok=False, reason_code="unknown_repo")
        self._record_repo_event(
            "code_repo_disconnected", owner_principal_id, user_id, {"repo_id": repo_id}
        )
        return ControlResult(ok=True, data={"repo_id": repo_id})

    def select_code_repo(self: DashboardService, repo_id: str | None, *, owner_principal_id: str) -> ControlResult:
        """Point the Build workspace at one repository, or at none with ``None``."""
        row = None
        if repo_id is not None:
            row = self.store.load_code_repo(owner_principal_id, repo_id)
            if row is None:
                return ControlResult(ok=False, reason_code="unknown_repo")
        self.store.select_code_repo(owner_principal_id, repo_id)
        # B9 — selecting a repository that was connected before the code map
        # existed (or before the owner turned it on) is the other moment the map
        # should be built. Already-indexed repositories are left alone: selecting
        # is not a request to re-scan.
        indexed = None
        if row is not None and str(row.get("kind", "")) == "local":
            from raiker.graph.codemap_service import CodeMapService

            subpath = str(row.get("local_subpath") or "")
            service = CodeMapService(
                self.workspace_root, self.store, principal_id=owner_principal_id
            )
            if subpath and service.index_row(subpath) is None:
                indexed = self._index_code_map(subpath, repo_id or "", owner_principal_id, None)
        return ControlResult(ok=True, data={"selected_repo_id": repo_id, "code_map": indexed})


    def code_map_status(self: DashboardService, *, owner_principal_id: str) -> dict[str, Any]:
        """What Build shows about the index: the gate, the repository, the counts."""
        from raiker.graph.codemap_service import CodeMapService

        return CodeMapService(
            self.workspace_root, self.store, principal_id=owner_principal_id
        ).status()

    def code_map_paths(
        self: DashboardService, *, owner_principal_id: str, fragment: str, limit: int = 12
    ) -> dict[str, Any]:
        """Paths matching an `@`-mention fragment, from the index the owner built."""
        from raiker.graph.codemap_service import CodeMapService

        return CodeMapService(
            self.workspace_root, self.store, principal_id=owner_principal_id
        ).complete_paths(fragment, limit=limit)

    def rebuild_code_map(
        self: DashboardService, *, owner_principal_id: str, user_id: str | None = None
    ) -> ControlResult:
        """Re-scan the selected repository on the owner's explicit request."""
        from raiker.graph.codemap_service import CodeMapService

        service = CodeMapService(self.workspace_root, self.store, principal_id=owner_principal_id)
        result = service.build()
        if str(result.get("status", "")) not in ("indexed", "partial"):
            error = result.get("error", {}) if isinstance(result.get("error"), dict) else {}
            return ControlResult(ok=False, reason_code=str(error.get("type", "code_map_failed")))
        self._record_repo_event(
            "code_map_indexed",
            owner_principal_id,
            user_id,
            {k: v for k, v in result.items() if k not in ("languages", "skipped")},
        )
        return ControlResult(ok=True, data=result)

    def _index_code_map(
        self: DashboardService,
        relative_path: str,
        repo_id: str,
        owner_principal_id: str,
        user_id: str | None,
    ) -> dict[str, Any] | None:
        """Index a just-connected folder, and say so in the audit trail.

        Best-effort by design: connecting a repository is bookkeeping that must
        succeed whether or not a scan can. A gate that is off, a folder that
        cannot be read, or a scan that raises leaves the reference connected and
        the map simply not built — which is what the Build panel then reports.
        """
        from raiker.graph.codemap_service import CodeMapService, CodeMapTarget

        try:
            service = CodeMapService(
                self.workspace_root, self.store, principal_id=owner_principal_id
            )
            if service.governance_refusal("Code map indexing") is not None:
                return None
            root = resolve_repository_root(self.workspace_root, relative_path)
            # `resolve_repository_root` falls back to the workspace root for a
            # sub-path it cannot contain. Indexing the whole workspace under the
            # folder's name would be a quietly wrong answer, so refuse instead.
            if root == self.workspace_root.resolve() and relative_path not in ("", "."):
                return None
            result = service.build(
                target=CodeMapTarget(
                    repo_path=relative_path, root=root, repo_id=repo_id, label=relative_path
                )
            )
        except Exception:  # noqa: BLE001 — a derived index never blocks the reference
            return None
        if str(result.get("status", "")) not in ("indexed", "partial"):
            return None
        self._record_repo_event(
            "code_map_indexed",
            owner_principal_id,
            user_id,
            {k: v for k, v in result.items() if k not in ("languages", "skipped")},
        )
        return result

    def _record_repo_event(
        self: DashboardService,
        event_type: str,
        owner_principal_id: str,
        user_id: str | None,
        payload: dict[str, Any],
    ) -> None:
        """Audit one repository reference change in the account's Inbox session.

        The Inbox session is created the same way scheduled work creates it, so
        the record is visible to the account that made the change rather than
        landing in a session nobody can read.
        """
        from raiker.events.types import make_event

        session_id = f"sess_inbox_{owner_principal_id}"
        self.store.create_session(
            session_id, str(self.store.paths.workspace_root), title="Inbox", user_id=user_id
        )
        EventLogWriter(self.store).append(
            make_event(
                session_id=session_id,
                turn_id=None,
                event_type=event_type,
                actor="dashboard_service",
                payload={**payload, "principal_id": owner_principal_id},
            )
        )
