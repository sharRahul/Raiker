from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path, PurePath
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from raiker.contracts.ids import new_id, utc_now

TERMINAL_STATES = frozenset({"cancelled", "failed", "complete"})

# The operation kinds a retry can really dispatch again (BUG-75). `install` is
# absent on purpose: it has no background worker to reconstruct, so offering
# Retry for it would be the record-only control this fix exists to remove.
RETRYABLE_KINDS = frozenset({"download", "convert", "deploy", "pull"})

# Payload keys that may be persisted. An allowlist rather than a blocklist, so a
# caller cannot accidentally durably store a token by adding a field: everything
# not named here is dropped before the row is written.
_PAYLOAD_KEYS = frozenset(
    {
        "repo_id", "revision", "variant", "destination", "model", "source",
        "output", "quantization", "model_path", "model_id",
        "framework", "profile_id",
    }
)


@dataclass(frozen=True)
class ModelOperationRequest:
    kind: str
    target: str
    confirmed: bool
    source_url: str | None = None
    destination: str | None = None


@dataclass(frozen=True)
class ModelOperation:
    operation_id: str
    owner_principal_id: str
    kind: str
    target: str
    state: str
    phase: str
    progress_bytes: int
    total_bytes: int | None
    progress_percent: int | None
    source_url: str | None
    destination: str | None
    error_code: str | None
    error_detail: str | None
    created_at: str
    updated_at: str
    # The secret-safe typed payload a retry dispatches from, and the path a
    # confirmed cleanup would delete. Never part of the API projection: the
    # owner reads the *redacted* destination, and only the confirm dialog for
    # "Delete partial files" is told the exact approved path.
    payload_json: str = "{}"

    def payload(self) -> dict[str, Any]:
        try:
            parsed = json.loads(self.payload_json or "{}")
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def to_row(self) -> dict[str, Any]:
        """Every column, in schema order. Storage only."""
        return asdict(self)

    def to_dict(self) -> dict[str, Any]:
        """The owner-facing projection: redacted, plus what the controls can do."""
        data = asdict(self)
        payload = self.payload()
        data.pop("payload_json", None)
        data["retryable"] = self.kind in RETRYABLE_KINDS and bool(payload)
        data["partial_files_present"] = bool(
            payload.get("destination") and self.state in {"failed", "cancelled"}
        )
        return data


class ModelOperationService:
    def __init__(self, store: Any) -> None:
        self.store = store

    def start(
        self,
        owner_principal_id: str,
        request: ModelOperationRequest,
        payload: dict[str, Any] | None = None,
    ) -> ModelOperation:
        if not request.confirmed:
            raise ValueError("confirmation_required")
        if request.kind not in {"install", "download", "convert", "deploy", "pull"}:
            raise ValueError("unsupported_operation_kind")
        now = utc_now()
        operation = ModelOperation(
            operation_id=new_id("mop_"),
            owner_principal_id=owner_principal_id,
            kind=request.kind,
            target=request.target,
            state="queued",
            phase="queued",
            progress_bytes=0,
            total_bytes=None,
            progress_percent=None,
            source_url=_redact_source_url(request.source_url),
            destination=_redact_destination(request.destination),
            error_code=None,
            error_detail=None,
            created_at=now,
            updated_at=now,
            payload_json=json.dumps(_safe_payload(payload), sort_keys=True),
        )
        self.store.save_model_operation(operation)
        return operation

    def list(self, owner_principal_id: str) -> list[ModelOperation]:
        return self.store.list_model_operations(owner_principal_id)

    def require(self, owner_principal_id: str, operation_id: str) -> ModelOperation:
        """One owner-scoped operation, or ``KeyError``."""
        operation: ModelOperation = self.store.require_model_operation(
            owner_principal_id, operation_id
        )
        return operation

    def running(self, owner_principal_id: str, operation_id: str, *, phase: str) -> ModelOperation:
        operation = self.store.require_model_operation(owner_principal_id, operation_id)
        return self.store.save_model_operation(
            replace(
                operation,
                state="running",
                phase=phase,
                updated_at=utc_now(),
            )
        )

    def progress(
        self,
        owner_principal_id: str,
        operation_id: str,
        *,
        completed_bytes: int,
        total_bytes: int | None,
        phase: str,
    ) -> ModelOperation:
        operation = self.store.require_model_operation(owner_principal_id, operation_id)
        completed = max(0, completed_bytes)
        total = max(completed, total_bytes) if total_bytes is not None else None
        percent = min(99, int(completed * 100 / total)) if total else None
        return self.store.save_model_operation(
            replace(
                operation,
                state="running",
                phase=phase,
                progress_bytes=completed,
                total_bytes=total,
                progress_percent=percent,
                updated_at=utc_now(),
            )
        )

    def complete(self, owner_principal_id: str, operation_id: str) -> ModelOperation:
        operation = self.store.require_model_operation(owner_principal_id, operation_id)
        total = operation.total_bytes
        return self.store.save_model_operation(
            replace(
                operation,
                state="complete",
                phase="complete",
                progress_bytes=total or operation.progress_bytes,
                progress_percent=100,
                updated_at=utc_now(),
            )
        )

    def fail(self, owner_principal_id: str, operation_id: str, *, code: str) -> ModelOperation:
        operation = self.store.require_model_operation(owner_principal_id, operation_id)
        return self.store.save_model_operation(
            replace(
                operation,
                state="failed",
                phase="failed",
                error_code=code,
                error_detail=None,
                updated_at=utc_now(),
            )
        )

    def cancel(self, owner_principal_id: str, operation_id: str) -> ModelOperation:
        operation = self.store.require_model_operation(owner_principal_id, operation_id)
        if operation.state in TERMINAL_STATES:
            return operation
        if operation.state == "queued":
            # Nothing has started, so there is nothing to co-operate with: the
            # request reaches its terminal state immediately rather than sitting
            # in `cancel_requested` waiting for a worker that never ran.
            return self.cancelled(owner_principal_id, operation_id)
        return self.store.save_model_operation(
            replace(operation, state="cancel_requested", updated_at=utc_now())
        )

    def cancel_requested(self, owner_principal_id: str, operation_id: str) -> bool:
        """Whether a worker should stop. The cooperative half of Cancel.

        Read at every bounded step by every worker, so cancellation reaches a
        terminal state promptly instead of only when the job happens to end. A
        row that has vanished counts as cancelled: the owner cleared it.
        """
        try:
            operation = self.store.require_model_operation(owner_principal_id, operation_id)
        except KeyError:
            return True
        return operation.state == "cancel_requested"

    def cancelled(self, owner_principal_id: str, operation_id: str) -> ModelOperation:
        """Move a cancel request to its terminal state."""
        operation = self.store.require_model_operation(owner_principal_id, operation_id)
        return self.store.save_model_operation(
            replace(
                operation,
                state="cancelled",
                phase="cancelled",
                error_code=None,
                error_detail=None,
                updated_at=utc_now(),
            )
        )

    def retry(self, owner_principal_id: str, operation_id: str) -> ModelOperation:
        """Re-queue a failed operation. The caller dispatches its worker by kind."""
        operation = self.store.require_model_operation(owner_principal_id, operation_id)
        if operation.kind not in RETRYABLE_KINDS or not operation.payload():
            raise ValueError("operation_not_retryable")
        return self.store.save_model_operation(
            replace(
                operation,
                state="queued",
                phase="queued",
                progress_bytes=0,
                progress_percent=None,
                error_code=None,
                error_detail=None,
                updated_at=utc_now(),
            )
        )

    def partial_files(self, owner_principal_id: str, operation_id: str) -> dict[str, Any]:
        """What a confirmed cleanup would delete: the exact path and its bytes.

        Named exactly, because a destructive confirmation that says "the
        destination" is not a confirmation. The path is only ever produced for a
        terminal operation, and the caller still checks it against the owner's
        approved model-library roots before anything is removed.
        """
        operation = self.store.require_model_operation(owner_principal_id, operation_id)
        path = str(operation.payload().get("destination") or "")
        if not path or operation.state not in TERMINAL_STATES:
            return {"path": None, "exists": False, "bytes": 0, "file_count": 0}
        target = Path(path)
        if not target.exists():
            return {"path": path, "exists": False, "bytes": 0, "file_count": 0}
        files = [item for item in target.rglob("*") if item.is_file()] if target.is_dir() else [target]
        return {
            "path": path,
            "exists": True,
            "bytes": sum(item.stat().st_size for item in files),
            "file_count": len(files),
        }

    def cleanup(self, owner_principal_id: str, operation_id: str) -> bool:
        """Clear the durable record. Metadata only — files are never touched here."""
        operation = self.store.require_model_operation(owner_principal_id, operation_id)
        if operation.state not in TERMINAL_STATES:
            return False
        return self.store.delete_model_operation(owner_principal_id, operation_id)

    def recover_abandoned(self) -> int:
        return self.store.fail_running_model_operations()


def _safe_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Keep only the allowlisted, non-secret keys a retry actually needs."""
    if not payload:
        return {}
    return {
        key: str(value)
        for key, value in payload.items()
        if key in _PAYLOAD_KEYS and value is not None and str(value)
    }


def _redact_source_url(value: str | None) -> str | None:
    if value is None:
        return None
    parts = urlsplit(value)
    host = parts.hostname or ""
    if parts.port is not None:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, "", ""))


def _redact_destination(value: str | None) -> str | None:
    if value is None:
        return None
    filename = PurePath(value.replace("\\", "/")).name
    return f"<model-library>/{filename}" if filename else "<model-library>"
