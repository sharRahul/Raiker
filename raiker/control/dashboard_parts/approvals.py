# mypy: disable-error-code="misc"
"""Approvals, and the preview and evidence an owner decides one from (GCR-43).

One part of :class:`raiker.control.dashboard.DashboardService`, which inherits it. Every method
is typed against the whole store (``self: DashboardService``), so a call into another
part is checked exactly as it was when every method lived in one class. mypy
reports that self-type as ``misc`` on a mixin, which is the one code this file
turns off.
"""

from __future__ import annotations

import difflib
import json
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from raiker.approval_previews import redact_secret_like_text
from raiker.checkpoints.capture import MAX_PRE_IMAGE_BYTES
from raiker.contracts.ids import utc_now
from raiker.control.views.approvals import ApprovalDetailView, ApprovalView
from raiker.control.views.security import IdentityView
from raiker.execution.code_placement import (
    COMMAND_CAPABILITIES,
    HOST_NETWORK_CODE_CAPABILITY,
    argv_of,
    place_code,
)
from raiker.runtime.authority.router import CAPABILITY_GATE_MAP
from raiker.tools.filesystem import (
    FilesystemSafetyError,
    proposed_edit_snapshot,
    proposed_patch_snapshot,
    proposed_write_snapshot,
    resolve_workspace_path,
)
from raiker.tools.git import (
    proposed_branch_snapshot,
    proposed_commit_snapshot,
    proposed_push_snapshot,
    repository_label,
    resolve_repository_root,
    selected_repository_subpath,
)

if TYPE_CHECKING:
    from raiker.control.dashboard import DashboardService


class ApprovalService:

    def list_approvals(
        self: DashboardService,
        status: str = "pending",
        *,
        user_id: str | None = None,
        principal_id: str | None = None,
    ) -> list[ApprovalView]:
        rows = self.store.list_approvals(status=status, user_id=user_id, principal_id=principal_id)
        # ADD-02 — one join for the whole page rather than a query per row, so a
        # batched turn's approvals can each say which decision they are.
        positions = self.store.suspended_turn_queue_positions(
            [str(row.get("approval_id", "")) for row in rows]
        )
        return [
            self._placed_approval_view(
                row, self._approval_view(row, queue=positions), principal_id
            )
            for row in rows
        ]

    def _placed_approval_view(
        self: DashboardService,
        row: dict[str, Any],
        view: ApprovalView,
        principal_id: str | None,
    ) -> ApprovalView:
        """Name the capability a code-running command will really run under (BUG-308).

        The router reclassifies a `shell` or `process` action whose program runs
        code on the host to `host_network_code_execution` when it executes, and
        the approval is what the owner reads before that. Labelling it by the
        tool alone said *Shell commands* above a `python` run with this machine's
        network — so the same placement rule is asked here.
        """
        if view.capability not in COMMAND_CAPABILITIES:
            return view
        try:
            arguments = json.loads(str(row.get("arguments_json") or "{}"))
        except (ValueError, TypeError):
            return view
        if not isinstance(arguments, dict):
            return view
        owner = principal_id or str(row.get("owner_principal_id") or row.get("principal_id") or "")
        placement = place_code(
            self.store, owner, argv_of(view.capability, arguments), self.workspace_root
        )
        if not placement.needs_host_network_capability:
            return view
        return replace(view, capability=HOST_NETWORK_CODE_CAPABILITY)

    def get_approval(
        self: DashboardService,
        approval_id: str,
        *,
        user_id: str | None = None,
        principal_id: str | None = None,
    ) -> ApprovalDetailView | None:
        row = self.store.load_approval(approval_id, user_id=user_id, principal_id=principal_id)
        if row is None:
            return None
        return self._approval_detail(row, principal_id=principal_id)

    @staticmethod
    def _proposal_identity(row: dict[str, Any]) -> IdentityView:
        principal_id = str(row.get("proposed_by") or "agent_runtime")
        principal_type = str(row.get("proposer_principal_type") or "unknown")
        turn_id = str(row.get("turn_id") or "") or None
        expires_at = str(row.get("machine_expires_at") or "") or None
        if row.get("machine_is_active") is not None and not bool(row.get("machine_is_active")):
            state = "inactive"
        elif expires_at and expires_at < utc_now():
            state = "expired"
        elif principal_type == "ai_agent":
            state = "active"
        else:
            state = "unknown"
        display_name = str(row.get("proposer_display_name") or "")
        if not display_name and principal_type == "ai_agent":
            display_name = f"Raiker agent · {turn_id or 'turn'}"
        return IdentityView(
            principal_id=principal_id,
            principal_type=principal_type,
            display_name=display_name or principal_id,
            subject=str(row.get("machine_subject") or "") or None,
            turn_id=turn_id,
            key_id=str(row.get("machine_key_id") or "") or None,
            issued_at=str(row.get("machine_issued_at") or "") or None,
            expires_at=expires_at,
            state=state,
        )

    @staticmethod
    def _authorizer_identity(row: dict[str, Any]) -> IdentityView | None:
        principal_id = str(row.get("approved_by") or "")
        if not principal_id:
            return None
        return IdentityView(
            principal_id=principal_id,
            principal_type=str(row.get("authorizer_principal_type") or "human"),
            display_name=str(row.get("authorizer_display_name") or principal_id),
            state="active",
        )

    @classmethod
    def _approval_view(
        cls: type[DashboardService], row: dict[str, Any], *, queue: dict[str, tuple[int, int]] | None = None
    ) -> ApprovalView:
        tool_name = str(row.get("tool_name", ""))
        status = str(row.get("status", ""))
        created_at = str(row.get("created_at", ""))
        expires_at = str(row.get("expires_at", "")) or None
        # An approval with no parked turn behind it is a batch of one, which is
        # what the defaults say.
        queue_position, queue_total = (queue or {}).get(str(row["approval_id"]), (1, 1))
        proposed_by = cls._proposal_identity(row)
        approved_by = cls._authorizer_identity(row)
        return ApprovalView(
            approval_id=str(row["approval_id"]),
            action_id=str(row.get("action_id", "")),
            status=status,
            tool_name=tool_name,
            capability=CAPABILITY_GATE_MAP.get(tool_name, tool_name),
            risk_level=str(row.get("risk_level", "")),
            session_id=str(row.get("session_id", "")),
            turn_id=row.get("turn_id"),
            created_at=created_at,
            age_seconds=cls._age_seconds(created_at),
            requires_approval=status == "pending",
            expires_at=expires_at,
            is_expired=status == "pending" and bool(expires_at and utc_now() > expires_at),
            proposed_by=proposed_by,
            approved_by=approved_by,
            machine_identity=(proposed_by if proposed_by.principal_type == "ai_agent" else None),
            critical=bool(row.get("critical")),
            resolved_by=(str(row["approved_by"]) if row.get("approved_by") else None),
            queue_position=queue_position,
            queue_total=queue_total,
        )

    def _approval_detail(
        self: DashboardService, row: dict[str, Any], *, principal_id: str | None = None
    ) -> ApprovalDetailView:
        from raiker.approvals.execution import ApprovalExecutionBridge

        approval_id = str(row["approval_id"])
        view = self._placed_approval_view(
            row,
            self._approval_view(
                row, queue=self.store.suspended_turn_queue_positions([approval_id])
            ),
            principal_id,
        )
        try:
            raw_args = json.loads(str(row.get("arguments_json", "{}")))
        except (ValueError, TypeError):
            raw_args = {}
        arguments = self._redact_arguments(raw_args)
        diff, diff_path, kind = self._build_preview(
            view.tool_name, raw_args, principal_id=principal_id
        )
        connector_write = view.tool_name == "connector_write"
        # BUG-06 — the notice is derived from what the server will actually do,
        # not from a constant. A file mutation executes only when the relay and
        # the target capability are both enabled; either gate being off returns
        # this approval to metadata-only, and the notice says so.
        relays = ApprovalExecutionBridge(self.store).executes_on_resolution(
            view.tool_name, principal_id, critical=view.critical
        )
        if connector_write:
            notice = "Approving this connector write executes this exact action once."
        elif relays and view.tool_name == "create_task":
            # BUG-62 — the file wording below promises a checkpointed diff, which
            # a task row does not have. Saying where it lands is the useful part.
            notice = (
                "Approving this creates the task above in Tasks, once, under a fresh "
                "capability, policy and posture check. It is a local row you can stop "
                "and delete there; nothing else runs until the task itself does."
            )
        elif relays and view.tool_name == "assign_session_project":
            notice = (
                "Approving this moves the proposing conversation into the project above, "
                "once. A project is an organizing scope: the move grants nothing, changes "
                "no gate, and is reversed in Projects."
            )
        elif relays and view.tool_name == "git_commit":
            # B11 — the file wording below promises a checkpointed rewind, and a
            # commit is not a file the checkpoint store holds a pre-image of.
            notice = (
                "Approving this records the change set above as one commit, once, "
                "under a fresh capability, policy and posture check. Repository "
                "hooks do not run. It is git history rather than a checkpointed "
                "file write, so undo it in git."
            )
        elif relays and view.tool_name == "git_branch":
            notice = (
                "Approving this creates the branch above and checks it out, once, "
                "under a fresh capability, policy and posture check. No commit is "
                "made and no file is changed; delete the branch in git to undo it."
            )
        elif relays and view.tool_name == "git_push":
            # BUG-67 — the branch and the commit above are local and the owner
            # can undo them in git. This one leaves the machine, so it is worded
            # like the GitHub write below rather than like its own siblings.
            notice = (
                "Approving this sends the commits above to the remote shown, once, "
                "with your own credential. It never forces and never deletes a "
                "branch, but it leaves this machine and git cannot take it back — "
                "undo it on the remote."
            )
        elif relays and view.tool_name == "github_write":
            notice = (
                "Approving this sends the request above to GitHub with your own "
                "token, once. It leaves this machine and cannot be unsent — close "
                "or delete it on GitHub to undo it."
            )
        elif relays and view.tool_name == "checkpoint_restore":
            # BUG-230 — the rewind. The wording below promises a checkpoint of
            # the previous contents, which is exactly what this action consumes
            # rather than produces; and the one fact an owner needs here is that
            # the restore is itself captured, so approving is not a one-way door.
            notice = (
                "Approving this rewinds the files listed above to their state at "
                "the checkpoint, once, under a fresh capability, policy and posture "
                "check. The restore captures its own pre-image first, so it appears "
                "as a new checkpoint and can be rewound the same way. Files marked "
                "skipped are left exactly as they are."
            )
        elif relays and view.tool_name in {"shell", "process"}:
            # A command is not a file write — nothing it changes has a pre-image,
            # so it never promises a checkpointed rewind — and when its code runs
            # with this machine's network, that is the one fact the owner is
            # deciding on (FIXED-620).
            where = (
                "It runs on this machine, with this machine's network: anything "
                "it sends has left and cannot be taken back."
                if view.capability == HOST_NETWORK_CODE_CAPABILITY
                else "It runs where Permissions says commands run."
            )
            notice = (
                "Approving this runs the command above, once, under a fresh "
                f"capability, policy and posture check. {where} A command is not a "
                "checkpointed file write, so what it changes cannot be rewound."
            )
        elif relays:
            # BUG-233 — the rewind sentence was a constant for the whole
            # file-mutation class, and for a file over the pre-image cap it was
            # false: the write still happens, its pre-image is recorded
            # `oversize`, and nothing can put it back. The owner read the promise
            # *before* deciding, so the check has to happen here, before the
            # decision, rather than at capture time after it.
            oversize = self._oversize_target(view.tool_name, raw_args)
            if oversize is not None:
                path, size_bytes = oversize
                notice = (
                    "Approving this performs the change shown above, once, in your "
                    "workspace — under a fresh capability, policy and posture check. "
                    f"**This change cannot be rewound.** `{path}` is "
                    f"{size_bytes // (1024 * 1024)} MiB, over the "
                    f"{MAX_PRE_IMAGE_BYTES // (1024 * 1024)} MiB checkpoint pre-image "
                    "cap, so no copy of the previous contents is kept."
                )
            else:
                notice = (
                    "Approving this performs the change shown above, once, in your "
                    "workspace — under a fresh capability, policy and posture check. "
                    "The previous file contents are checkpointed first, so it can be "
                    "rewound."
                )
        else:
            notice = (
                "Approval resolution is metadata-only. Recording a decision does "
                "NOT execute the action."
            )
        # BUG-218 — when Auto withheld this action rather than granting it, the
        # owner is looking at an approval they did not expect to see. Saying why,
        # first, is what makes it a question they can answer.
        withheld = self._alignment_withheld(view.approval_id, turn_id=view.turn_id)
        if withheld:
            notice = f"{withheld}\n\n{notice}"
        return ApprovalDetailView(
            approval=view,
            arguments=arguments,
            diff=diff,
            diff_path=diff_path,
            preview_kind=kind,
            metadata_only_notice=notice,
            executes_on_approval=connector_write or relays,
            execution_evidence=self._approval_execution_evidence(
                view.approval_id, turn_id=view.turn_id
            ),
        )

    def _alignment_withheld(self: DashboardService, approval_id: str, *, turn_id: str | None) -> str:
        """The sentence Auto's alignment check left behind, or ``""``.

        BUG-218 — read from the durable ``approval_requested`` event rather than
        recomputed here. The check is deterministic and would give the same
        answer, but recomputing it would also attach the sentence to approvals
        raised in **manual** mode, where the check never ran and Auto promised
        nothing. What the owner is told has to match what actually happened.
        """
        from raiker.events.query import EventViewer

        if not turn_id:
            return ""
        viewer = EventViewer(self.store)
        for row in viewer.list_events(turn_id=turn_id, event_type="approval_requested", limit=50):
            event = viewer.read_event_payload(str(row.get("event_id", "")))
            payload = event.get("payload") if isinstance(event, dict) else None
            if not isinstance(payload, dict) or payload.get("approval_id") != approval_id:
                continue
            alignment = payload.get("alignment")
            if isinstance(alignment, dict) and not alignment.get("aligned", True):
                return str(alignment.get("message") or "")
            return ""
        return ""

    def _approval_execution_evidence(
        self: DashboardService, approval_id: str, *, turn_id: str | None
    ) -> dict[str, Any]:
        """Return the durable relay evidence for one resolved approval."""
        from raiker.events.query import EventViewer

        viewer = EventViewer(self.store)
        # Relay audit events use the resolving API session id, not the original
        # chat session id. A turn id remains stable across both boundaries and
        # narrows the durable lookup to the approval's own execution history.
        event_rows = (
            viewer.list_events(turn_id=turn_id, event_type="approval_executed", limit=50)
            if turn_id
            else viewer.list_events(event_type="approval_executed", limit=500)
        )
        for row in event_rows:
            event = viewer.read_event_payload(str(row.get("event_id", "")))
            payload = event.get("payload") if isinstance(event, dict) else None
            if not isinstance(payload, dict) or payload.get("approval_id") != approval_id:
                continue
            result = payload.get("result")
            return {
                "principal_id": payload.get("principal_id"),
                **(result if isinstance(result, dict) else {}),
            }
        return {}

    @classmethod
    def _redact_arguments(cls: type[DashboardService], args: Any) -> dict[str, Any]:
        if not isinstance(args, dict):
            return {}
        return {str(k): cls._redact_value(v) for k, v in args.items()}

    @classmethod
    def _redact_value(cls: type[DashboardService], value: Any) -> Any:
        if isinstance(value, str):
            return redact_secret_like_text(value)
        if isinstance(value, list):
            return [cls._redact_value(v) for v in value]
        if isinstance(value, dict):
            return {str(k): cls._redact_value(v) for k, v in value.items()}
        return value

    def _git_root(self: DashboardService, principal_id: str | None) -> Path:
        """The repository a git approval was computed against (BUG-66).

        The same resolution the broker and the executor use, so the diff the
        owner reviews, the sentence they are shown, and the repository the change
        lands in are one answer rather than three.
        """
        scope: str | None = None
        if principal_id:
            try:
                scope = self.store.account_scope(principal_id) or principal_id
            except Exception:  # noqa: BLE001 — a storage failure falls back to the workspace
                scope = None
        return resolve_repository_root(
            self.workspace_root, selected_repository_subpath(self.store, scope)
        )

    #: Tools whose approval promises a checkpointed rewind, keyed by the argument
    #: naming the file the promise is about.
    _REWIND_PROMISE_TOOLS: dict[str, str] = {
        "write_file": "path",
        "edit_file": "path",
        "create_document": "path",
        "apply_patch": "path",
    }

    def _oversize_target(self: DashboardService, tool_name: str, args: dict[str, Any]) -> tuple[str, int] | None:
        """``(path, size)`` when the target is too large to checkpoint, else None.

        BUG-233. Only an *existing* file has a pre-image to lose, so a new file is
        not oversize however large the proposed content is: there is nothing to
        rewind to either way. A path that does not resolve inside the workspace is
        not this function's problem — the executor refuses it — so it reports no
        promise rather than guessing.
        """
        argument = self._REWIND_PROMISE_TOOLS.get(tool_name)
        if argument is None:
            return None
        raw_path = str(args.get(argument, "")).strip()
        if not raw_path:
            return None
        try:
            resolved = resolve_workspace_path(self.workspace_root, raw_path)
        except FilesystemSafetyError:
            return None
        try:
            if not resolved.is_file():
                return None
            size = resolved.stat().st_size
        except OSError:
            return None
        return (raw_path, size) if size > MAX_PRE_IMAGE_BYTES else None

    def _build_preview(
        self: DashboardService, tool_name: str, args: dict[str, Any], *, principal_id: str | None = None
    ) -> tuple[str | None, str | None, str]:
        """Return (diff, path, preview_kind). File mutations get a unified diff; never executes."""
        if tool_name == "checkpoint_restore":
            # BUG-230 — the approval carries the same preflight the Checkpoints
            # panel shows, recomputed here from the capture manifest rather than
            # taken from the caller, so the owner decides on what will actually
            # run. Metadata only: paths, operations and sizes, never content.
            from raiker.checkpoints.service import CheckpointService

            checkpoint_id = str(args.get("checkpoint_id", "")).strip()
            try:
                plan = CheckpointService(self.store).compute_restore_plan(
                    checkpoint_id, restoring_principal_id=principal_id
                )
            except (ValueError, OSError):
                return None, checkpoint_id or None, "arguments"
            files: list[dict[str, Any]] = plan.get("files", [])  # type: ignore[assignment]
            lines = [
                f"Checkpoint {checkpoint_id}",
                f"{plan['restore_content_count']} to rewrite, "
                f"{plan['delete_count']} to delete, {plan['skip_count']} skipped "
                f"(too large to have been captured).",
                "",
            ]
            for entry in files:
                marks: list[str] = []
                if entry.get("changed_by_other_principal"):
                    marks.append("last changed by a different principal")
                if entry.get("op") == "skip_oversize":
                    marks.append("not restorable — over the pre-image cap")
                suffix = f"  [{'; '.join(marks)}]" if marks else ""
                lines.append(f"{entry['op']:>16}  {entry['workspace_path']}{suffix}")
            return "\n".join(lines), checkpoint_id or None, "checkpoint_restore"
        if tool_name == "write_file":
            try:
                snapshot = proposed_write_snapshot(
                    self.workspace_root,
                    str(args.get("path", ".")),
                    str(args.get("text", "")),
                )
            except FilesystemSafetyError:
                return None, str(args.get("path", "")), "arguments"
            before = snapshot.get("before_snapshot") or ""
            after = str(snapshot.get("proposed_text", ""))
            path = str(snapshot.get("path", args.get("path", "")))
            diff = "".join(
                difflib.unified_diff(
                    redact_secret_like_text(before).splitlines(keepends=True),
                    redact_secret_like_text(after).splitlines(keepends=True),
                    fromfile=f"a/{path}",
                    tofile=f"b/{path}",
                )
            )
            return diff, path, "file_diff"
        if tool_name == "edit_file":
            try:
                snapshot = proposed_edit_snapshot(
                    self.workspace_root,
                    str(args.get("path", ".")),
                    str(args.get("old_text", "")),
                    str(args.get("new_text", "")),
                )
            except FilesystemSafetyError:
                return None, str(args.get("path", "")), "arguments"
            if snapshot["status"] == "failed":
                return None, str(args.get("path", "")), "arguments"
            before = snapshot.get("before_snapshot") or ""
            after = str(snapshot.get("proposed_text", ""))
            path = str(snapshot.get("path", args.get("path", "")))
            diff = "".join(
                difflib.unified_diff(
                    redact_secret_like_text(before).splitlines(keepends=True),
                    redact_secret_like_text(after).splitlines(keepends=True),
                    fromfile=f"a/{path}",
                    tofile=f"b/{path}",
                )
            )
            return diff, path, "file_diff"
        if tool_name == "apply_patch":
            try:
                snapshot = proposed_patch_snapshot(
                    self.workspace_root,
                    str(args["path"]) if args.get("path") else None,
                    str(args.get("patch", "")),
                )
            except FilesystemSafetyError:
                return None, str(args.get("path", "")), "arguments"
            if snapshot["status"] == "failed":
                return None, str(args.get("path", "")), "arguments"
            changes = snapshot.get("changes") or [snapshot]
            diffs: list[str] = []
            for change in changes:
                path = str(change.get("path", ""))
                diffs.append(
                    "".join(
                        difflib.unified_diff(
                            redact_secret_like_text(change.get("before_snapshot") or "").splitlines(
                                keepends=True
                            ),
                            redact_secret_like_text(
                                str(change.get("proposed_text", ""))
                            ).splitlines(keepends=True),
                            fromfile=f"a/{path}",
                            tofile=f"b/{path}",
                        )
                    )
                )
            paths = [str(item.get("path", "")) for item in changes]
            return "".join(diffs), ", ".join(paths), "file_diff"
        if tool_name == "connector_write":
            connector = str(args.get("connector_id", "connector"))
            operation = str(args.get("operation_id", "operation"))
            request_arguments = self._redact_value(args.get("arguments", {}))
            return (
                json.dumps(request_arguments, indent=2, sort_keys=True),
                f"{connector} / {operation}",
                "connector_request",
            )
        # B11 — the git write path. A commit is reviewed the way a file change
        # is, as a diff; a branch is reviewed as the two refs it moves between,
        # because there is no diff to show and pretending otherwise would be
        # worse than saying so.
        repo_root = self._git_root(principal_id)
        repository = repository_label(self.workspace_root, repo_root)
        if tool_name == "git_commit":
            snapshot = proposed_commit_snapshot(
                repo_root, str(args.get("message", "")), args.get("paths")
            )
            if snapshot["status"] != "success":
                return None, None, "arguments"
            header = "\n".join(
                f"{entry['state']:>10}  "
                + (
                    f"{entry['previous_path']} → {entry['path']}"
                    if entry.get("previous_path")
                    else entry["path"]
                )
                for entry in snapshot["files"]
            )
            body = redact_secret_like_text(str(snapshot["diff"]))
            truncated = "\n\n(diff truncated)" if snapshot["truncated"] else ""
            return (
                f"{snapshot['file_count']} file(s) on {snapshot['branch']} "
                f"in repository {repository}\n{header}\n\n{body}{truncated}",
                str(snapshot["branch"]),
                "git_change",
            )
        if tool_name == "git_branch":
            snapshot = proposed_branch_snapshot(
                repo_root,
                str(args.get("name", "")),
                str(args["base"]) if args.get("base") else None,
            )
            if snapshot["status"] != "success":
                return None, None, "arguments"
            lines = [
                f"repository    {repository}",
                f"new branch    {snapshot['name']}",
                f"branch from   {snapshot['base'] or snapshot['current_branch'] or snapshot['head']}",
                f"checked out   {snapshot['current_branch'] or '(detached HEAD)'} → {snapshot['name']}",
            ]
            if snapshot["uncommitted_files"]:
                lines.append(f"carried over  {snapshot['uncommitted_files']} uncommitted file(s)")
            return "\n".join(lines), str(snapshot["name"]), "git_change"
        # BUG-67 — a push has no diff either. What the owner needs before
        # deciding is where it goes and what it carries, so that is what is
        # shown: the remote and its host, the branch, and the commits that are
        # not there yet.
        if tool_name == "git_push":
            snapshot = proposed_push_snapshot(
                repo_root,
                str(args["remote"]) if args.get("remote") else None,
                str(args["branch"]) if args.get("branch") else None,
            )
            if snapshot["status"] != "success":
                return None, None, "arguments"
            lines = [
                f"repository    {repository}",
                f"remote        {snapshot['remote']} ({snapshot['host']})",
                f"branch        {snapshot['branch']}"
                + ("  — new on the remote" if snapshot["creates_remote_branch"] else ""),
                f"sending       {snapshot['commit_count']} commit(s)",
            ]
            if snapshot["behind"]:
                lines.append(
                    f"remote ahead  {snapshot['behind']} commit(s) this branch does not have"
                )
            lines.append("")
            lines.extend(f"  {line}" for line in snapshot["commits"])
            if snapshot["truncated"]:
                lines.append("  …")
            return (
                "\n".join(lines),
                f"{snapshot['remote']}/{snapshot['branch']}",
                "git_change",
            )
        if tool_name == "github_write":
            request_arguments = self._redact_value(
                {k: v for k, v in args.items() if k not in ("operation", "repo")}
            )
            return (
                json.dumps(request_arguments, indent=2, sort_keys=True),
                f"{args.get('repo', 'repository')} / {args.get('operation', 'write')}",
                "connector_request",
            )
        return None, None, "arguments"
