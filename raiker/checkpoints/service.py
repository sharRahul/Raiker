from __future__ import annotations

import hashlib
import json
from pathlib import Path

from raiker.checkpoints.capture import (
    STATUS_ABSENT,
    STATUS_CAPTURED,
    STATUS_OVERSIZE,
    CheckpointCaptureService,
)
from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import Checkpoint
from raiker.storage.sqlite import SQLiteStore

# Restore operations a plan can prescribe per file (metadata-only vocabulary).
RESTORE_OP_CONTENT = "restore_content"  # rewrite the file from its pre-image blob
RESTORE_OP_DELETE = "delete"  # the file did not exist at the checkpoint → remove it
RESTORE_OP_SKIP_OVERSIZE = "skip_oversize"  # pre-image was never captured (over cap)


class CheckpointService:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store
        self.root = store.paths.checkpoints_dir
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, session_id: str, checkpoint_id: str) -> Path:
        return self.root / session_id / f"{checkpoint_id}.json"

    def write_turn_checkpoint(
        self,
        *,
        session_id: str,
        turn_id: str,
        runtime_state: str,
        summary: str,
        last_event_id: str,
    ) -> tuple[Checkpoint, Path]:
        checkpoint = Checkpoint(
            checkpoint_id=new_id("ckpt_"),
            session_id=session_id,
            turn_id=turn_id,
            created_at=utc_now(),
            runtime_state=runtime_state,
            summary=summary,
            last_event_id=last_event_id,
            memory_candidates=[],
        )
        path = self.path_for(session_id, checkpoint.checkpoint_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(checkpoint.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        self.store.insert_checkpoint(checkpoint, str(path))
        return checkpoint, path

    def read(self, path: str | Path) -> Checkpoint:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return Checkpoint(**data)

    def list_checkpoints(self, session_id: str | None = None, limit: int = 50) -> list[dict]:
        return self.store.list_checkpoints(session_id=session_id, limit=limit)

    def get_checkpoint(self, checkpoint_id: str) -> dict | None:
        return self.store.load_checkpoint_by_id(checkpoint_id)

    def _current_file_state(self, workspace_path: str) -> tuple[bool, str | None, int]:
        """Return (exists, sha256|None, size) for a workspace-relative path.

        Metadata only — the content is hashed, never returned or logged.
        """
        resolved = self.store.paths.workspace_root / workspace_path
        if not (resolved.exists() and resolved.is_file()):
            return (False, None, 0)
        data = resolved.read_bytes()
        return (True, hashlib.sha256(data).hexdigest(), len(data))

    def compute_restore_plan(
        self, checkpoint_id: str, *, restoring_principal_id: str | None = None
    ) -> dict[str, object]:
        """Compute a metadata-only per-file restore plan for a checkpoint.

        Restoring *to* a checkpoint rewinds every workspace file mutated after it
        back to the state it had at the checkpoint. That state is the pre-image of
        the *first* post-checkpoint mutation of each file (captured by B1). The
        plan carries only content-addresses and sizes — never file content.
        """
        checkpoint = self.get_checkpoint(checkpoint_id)
        if checkpoint is None:
            raise ValueError("checkpoint_not_found")
        created_at = str(checkpoint["created_at"])
        session_id = str(checkpoint["session_id"])
        entries = self.store.list_checkpoint_capture_entries(
            session_id=session_id, created_after=created_at, limit=100_000
        )
        # Entries come back newest-first; keeping the last write per path leaves
        # the *earliest* post-checkpoint entry — the file's state at the checkpoint.
        earliest_by_path: dict[str, dict] = {}
        for entry in entries:
            earliest_by_path[str(entry["workspace_path"])] = entry

        files: list[dict[str, object]] = []
        touches_other_principal = False
        for path in sorted(earliest_by_path):
            entry = earliest_by_path[path]
            status = str(entry["capture_status"])
            if status == STATUS_ABSENT:
                op = RESTORE_OP_DELETE
                target_sha: str | None = None
                target_size = 0
            elif status == STATUS_OVERSIZE:
                op = RESTORE_OP_SKIP_OVERSIZE
                target_sha = None
                target_size = int(entry["pre_image_size"])
            elif status == STATUS_CAPTURED:
                op = RESTORE_OP_CONTENT
                target_sha = entry["pre_image_sha256"]
                target_size = int(entry["pre_image_size"])
            else:  # unknown status → refuse to act on it
                op = RESTORE_OP_SKIP_OVERSIZE
                target_sha = None
                target_size = 0
            exists, current_sha, current_size = self._current_file_state(path)
            if op == RESTORE_OP_DELETE:
                changed = exists
            elif op == RESTORE_OP_CONTENT:
                changed = current_sha != target_sha
            else:
                changed = False
            changed_by_other_principal = bool(
                changed and restoring_principal_id
                and str(entry["principal_id"]) != restoring_principal_id
            )
            touches_other_principal = touches_other_principal or changed_by_other_principal
            files.append(
                {
                    "workspace_path": path,
                    "op": op,
                    "pre_image_sha256": target_sha,
                    "pre_image_size": target_size,
                    "current_sha256": current_sha,
                    "current_size": current_size,
                    "changed": changed,
                    "changed_by_other_principal": changed_by_other_principal,
                }
            )
        return {
            "status": "restore_plan",
            "checkpoint_id": checkpoint_id,
            "session_id": session_id,
            "checkpoint_created_at": created_at,
            "can_execute": True,
            "requires_approval": True,
            "files": files,
            "restore_content_count": sum(
                1 for f in files if f["op"] == RESTORE_OP_CONTENT
            ),
            "delete_count": sum(1 for f in files if f["op"] == RESTORE_OP_DELETE),
            "skip_count": sum(1 for f in files if f["op"] == RESTORE_OP_SKIP_OVERSIZE),
            "changed_count": sum(1 for f in files if f["changed"]),
            "touches_other_principal": touches_other_principal,
        }

    def plan_restore(self, checkpoint_id: str) -> dict[str, object]:
        """Dry-run restore preview (metadata-only). See ``compute_restore_plan``."""
        return self.compute_restore_plan(checkpoint_id)

    def capture_service(self) -> CheckpointCaptureService:
        return CheckpointCaptureService(self.store)

    def _fork_seed(self, checkpoint: dict) -> dict[str, object]:
        """Derive the seed a fork is materialized from (metadata-only).

        The seed is the checkpoint's state *summary* plus its *memory
        candidates* — never any workspace file content. ``summary`` lives on the
        checkpoint row; ``runtime_state`` and ``memory_candidates`` live in the
        manifest JSON, which is read best-effort (a missing/corrupt manifest
        degrades to an empty seed rather than failing the fork).
        """
        runtime_state = ""
        memory_candidates: list[dict[str, object]] = []
        manifest_path = checkpoint.get("manifest_path")
        if manifest_path:
            try:
                manifest = self.read(str(manifest_path))
                runtime_state = manifest.runtime_state
                memory_candidates = list(manifest.memory_candidates)
            except (OSError, ValueError, TypeError):
                pass
        return {
            "source_checkpoint_id": str(checkpoint["checkpoint_id"]),
            "source_session_id": str(checkpoint["session_id"]),
            "summary": str(checkpoint.get("summary", "")),
            "runtime_state": runtime_state,
            "memory_candidates": memory_candidates,
        }

    def _fork_manifest_path(self, session_id: str) -> Path:
        return self.root / "forks" / f"{session_id}.json"

    def plan_fork(self, checkpoint_id: str) -> dict[str, object]:
        """Metadata-only dry-run preview of a fork (B3).

        A fork materializes a *new* session seeded from the checkpoint's state
        summary and memory candidates; it mutates no workspace files, so — unlike
        restore — it is not an approval-required governed mutation.
        """
        checkpoint = self.get_checkpoint(checkpoint_id)
        if checkpoint is None:
            raise ValueError("checkpoint_not_found")
        seed = self._fork_seed(checkpoint)
        return {
            "status": "fork_plan",
            "checkpoint_id": checkpoint_id,
            "source_session_id": seed["source_session_id"],
            "summary": seed["summary"],
            "memory_candidate_count": len(seed["memory_candidates"]),  # type: ignore[arg-type]
            "can_execute": True,
            "requires_approval": False,
        }

    def execute_fork(
        self,
        checkpoint_id: str,
        *,
        new_session_id: str | None = None,
        title: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, object]:
        """Materialize a new session seeded from the checkpoint (B3).

        Creates a fresh session and records a metadata-only fork manifest
        capturing its lineage and seed (state summary + memory candidates). No
        workspace file is written or overwritten — the fork only branches
        conversation/session state, leaving the current workspace untouched.
        """
        checkpoint = self.get_checkpoint(checkpoint_id)
        if checkpoint is None:
            raise ValueError("checkpoint_not_found")
        seed = self._fork_seed(checkpoint)

        session_id = new_session_id or new_id("sess_")
        summary = str(seed["summary"])
        fork_title = title or (f"fork of {summary}".strip()[:120] if summary else "fork")
        self.store.create_session(
            session_id,
            str(self.store.paths.workspace_root),
            title=fork_title,
            user_id=user_id,
        )

        manifest = {
            "session_id": session_id,
            "forked_from_checkpoint_id": checkpoint_id,
            "source_session_id": seed["source_session_id"],
            "summary": summary,
            "runtime_state": seed["runtime_state"],
            "memory_candidates": seed["memory_candidates"],
            "created_at": utc_now(),
        }
        manifest_path = self._fork_manifest_path(session_id)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        return {
            "status": "forked",
            "checkpoint_id": checkpoint_id,
            "source_session_id": seed["source_session_id"],
            "session_id": session_id,
            "title": fork_title,
            "summary": summary,
            "memory_candidate_count": len(seed["memory_candidates"]),  # type: ignore[arg-type]
            "seed_manifest_path": str(manifest_path),
        }

    def load_fork_seed(self, session_id: str) -> dict[str, object] | None:
        """Return the fork manifest for a forked session, or ``None``."""
        path = self._fork_manifest_path(session_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
