"""Workstream B / Slice B1 — checkpoint pre-image capture.

Every workspace-file mutation executed through the broker/relay records the
*pre-image* of the file it is about to overwrite (or the fact that the file did
not yet exist) into a content-addressed blob store under
``.raiker/checkpoints/objects/``, plus a metadata-only manifest row. That
manifest is the safety net the rest of the plan builds on: B2's restore executor
puts a file back byte-for-byte from its pre-image blob, and because a restore is
itself a governed mutation it captures its own pre-image, so restores are
reversible too.

Design invariants:

* **Content-addressed & deduplicated.** A blob's name is the SHA-256 of its
  bytes, so identical pre-images across many mutations share one object and the
  same content always yields the same address (verifiable, tamper-evident).
* **Workspace-scoped.** Only paths that resolve inside the workspace root are
  captured; a path that escapes the workspace is not eligible (and the executor
  that produced it would itself refuse it) — capture never reaches outside.
* **Size-capped.** Files larger than ``MAX_PRE_IMAGE_BYTES`` are not snapshot;
  the manifest records ``oversize`` honestly rather than silently pretending the
  file is restorable.
* **Metadata-only events.** Neither the manifest nor the event log ever holds
  file content — only the content-address, size, and status.
* **Never breaks the mutation.** Capture is a best-effort safety net wrapped by
  the caller so a capture failure can never fail or block the real mutation.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from raiker.contracts.ids import new_id, utc_now
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.filesystem import FilesystemSafetyError, resolve_workspace_path

# 8 MiB: comfortably covers source/config/text mutations while bounding the
# blob store's growth and the cost of reading a pre-image into memory.
MAX_PRE_IMAGE_BYTES = 8 * 1024 * 1024

# Capabilities that mutate a single workspace file → the argument holding its
# path. Only these are pre-image-captured; anything else is skipped.
CAPTURE_PATH_ARG: dict[str, str] = {
    "file_write_execution": "path",
    "patch_apply_execution": "path",
}

# capture_status values recorded in the manifest.
STATUS_CAPTURED = "captured"  # pre-image blob stored; restorable
STATUS_ABSENT = "absent"  # file did not exist; restore == delete
STATUS_OVERSIZE = "oversize"  # file exceeded the cap; not restorable


@dataclass(frozen=True)
class PreImage:
    """A pre-mutation snapshot of a target file, taken *before* the executor runs."""

    capability: str
    workspace_path: str
    existed: bool
    size: int
    data: bytes | None
    status: str


class CheckpointCaptureService:
    def __init__(self, store: SQLiteStore, *, max_bytes: int = MAX_PRE_IMAGE_BYTES) -> None:
        self.store = store
        self.workspace_root = store.paths.workspace_root
        self.objects_dir = store.paths.checkpoints_dir / "objects"
        self.max_bytes = max_bytes

    def eligible(self, capability: str) -> bool:
        return capability in CAPTURE_PATH_ARG

    def snapshot_pre_image(
        self, capability: str, arguments: dict[str, object]
    ) -> PreImage | None:
        """Read the target file's current bytes *before* a mutation overwrites it.

        Returns ``None`` when the capability is not a file mutation, no path was
        given, or the path resolves outside the workspace (nothing to capture).
        """
        arg = CAPTURE_PATH_ARG.get(capability)
        if arg is None:
            return None
        raw_path = str(arguments.get(arg, ""))
        if not raw_path:
            return None
        try:
            resolved = resolve_workspace_path(self.workspace_root, raw_path)
        except FilesystemSafetyError:
            return None
        rel = str(resolved.relative_to(self.workspace_root))

        if not (resolved.exists() and resolved.is_file()):
            return PreImage(
                capability=capability,
                workspace_path=rel,
                existed=False,
                size=0,
                data=None,
                status=STATUS_ABSENT,
            )
        size = resolved.stat().st_size
        if size > self.max_bytes:
            return PreImage(
                capability=capability,
                workspace_path=rel,
                existed=True,
                size=size,
                data=None,
                status=STATUS_OVERSIZE,
            )
        data = resolved.read_bytes()
        return PreImage(
            capability=capability,
            workspace_path=rel,
            existed=True,
            size=len(data),
            data=data,
            status=STATUS_CAPTURED,
        )

    def _store_blob(self, data: bytes) -> str:
        """Write ``data`` into the content-addressed store, returning its sha256.

        Writes are idempotent: an existing object with the same address is left
        untouched (identical bytes ⇒ identical address).
        """
        digest = hashlib.sha256(data).hexdigest()
        blob_path = self.objects_dir / digest[:2] / digest
        if not blob_path.exists():
            blob_path.parent.mkdir(parents=True, exist_ok=True)
            # Write via a temp file + atomic replace so a crash mid-write never
            # leaves a truncated object at a valid-looking address.
            tmp = blob_path.with_name(f".{digest}.{uuid4().hex}.tmp")
            tmp.write_bytes(data)
            tmp.replace(blob_path)
        return digest

    def blob_path(self, digest: str) -> Path:
        return self.objects_dir / digest[:2] / digest

    def commit(
        self,
        pre_image: PreImage,
        *,
        session_id: str,
        turn_id: str | None,
        action_id: str,
        principal_id: str | None,
    ) -> dict[str, object]:
        """Persist the pre-image blob (if any) + a metadata-only manifest row.

        Returns the manifest metadata dict (no file content) suitable for a
        ``checkpoint_captured`` event payload.
        """
        sha256: str | None = None
        if pre_image.status == STATUS_CAPTURED and pre_image.data is not None:
            sha256 = self._store_blob(pre_image.data)
        manifest_id = new_id("ckcap_")
        created_at = utc_now()
        self.store.insert_checkpoint_capture_entry(
            manifest_id=manifest_id,
            session_id=session_id or "authz",
            turn_id=turn_id,
            action_id=action_id,
            capability=pre_image.capability,
            principal_id=principal_id,
            workspace_path=pre_image.workspace_path,
            pre_image_sha256=sha256,
            pre_image_size=pre_image.size,
            existed_before=pre_image.existed,
            capture_status=pre_image.status,
            created_at=created_at,
        )
        return {
            "manifest_id": manifest_id,
            "action_id": action_id,
            "capability": pre_image.capability,
            "workspace_path": pre_image.workspace_path,
            "pre_image_sha256": sha256,
            "pre_image_size": pre_image.size,
            "existed_before": pre_image.existed,
            "capture_status": pre_image.status,
        }
