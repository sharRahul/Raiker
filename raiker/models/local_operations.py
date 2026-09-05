from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path, PurePath
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from raiker.contracts.ids import new_id, utc_now

TERMINAL_STATES = frozenset({"cancelled", "failed", "complete"})

# The states a worker may still be advancing from. Every lifecycle write names
# the states it expects, and the store refuses the write when the row has
# already moved on (GCR-20), so a late progress row can no longer overwrite a
# cancellation the owner asked for while the worker was busy.
_ACTIVE_STATES = ("queued", "running")
_STOPPABLE_STATES = ("queued", "running", "cancel_requested")

# The operation kinds a retry can really dispatch again (BUG-75). `install` is
# absent on purpose: it has no background worker to reconstruct, so offering
# Retry for it would be the record-only control this fix exists to remove.
RETRYABLE_KINDS = frozenset({"download", "convert", "deploy", "pull"})

# The states a retry may start from. A running job is not retried, it is
# already running; a completed one is not retried, it succeeded (GCR-21).
RETRYABLE_STATES = ("failed", "cancelled")

# Payload keys that may be persisted. An allowlist rather than a blocklist, so a
# caller cannot accidentally durably store a token by adding a field: everything
# not named here is dropped before the row is written.
_PAYLOAD_KEYS = frozenset(
    {
        "repo_id", "revision", "variant", "destination", "model", "source",
        "output", "quantization", "model_path", "model_id",
        "framework", "profile_id", "artifacts",
    }
)

# The kinds whose recorded `destination` is a directory this operation created
# for itself, and therefore may delete whole. A conversion's destination is the
# owner's shared library output directory and is never one of them (GCR-19):
# a conversion names its exact artifacts instead.
_OPERATION_OWNED_DESTINATION_KINDS = frozenset({"download"})


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

    def cleanup_targets(self) -> tuple[str, ...]:
        """The exact paths a confirmed cleanup may remove — and no others.

        An operation may delete only what it can prove it created (GCR-19). A
        job that recorded its artifacts names them; a job whose destination is a
        directory it made for itself names that directory; anything else — a
        conversion written into the owner's shared output directory, or a row
        stored before artifacts were recorded — names nothing, and its bytes are
        left for the owner to remove deliberately.
        """
        payload = self.payload()
        recorded = payload.get("artifacts")
        if isinstance(recorded, str) and recorded:
            try:
                parsed = json.loads(recorded)
            except ValueError:
                parsed = None
            if isinstance(parsed, list):
                return tuple(str(item) for item in parsed if str(item))
        destination = str(payload.get("destination") or "")
        if destination and self.kind in _OPERATION_OWNED_DESTINATION_KINDS:
            return (destination,)
        return ()

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
            self.cleanup_targets() and self.state in set(RETRYABLE_STATES)
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

    def _transition(
        self,
        owner_principal_id: str,
        operation_id: str,
        expected_states: Sequence[str],
        **updates: Any,
    ) -> ModelOperation:
        """Apply one expected-state transition, or report the row unchanged.

        A refused transition is never an error for a worker: it means the owner
        cancelled, or another worker already landed the outcome. The caller gets
        the row as it now stands and can read its state to decide what to do,
        rather than writing over a decision it did not see (GCR-20).
        """
        moved = self.store.transition_model_operation(
            owner_principal_id, operation_id, expected_states=expected_states, **updates
        )
        if moved is not None:
            return moved
        current: ModelOperation = self.store.require_model_operation(
            owner_principal_id, operation_id
        )
        return current

    def running(self, owner_principal_id: str, operation_id: str, *, phase: str) -> ModelOperation:
        """Claim an operation for a worker. Refused once it has been cancelled."""
        return self._transition(
            owner_principal_id, operation_id, _ACTIVE_STATES, state="running", phase=phase
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
        completed = max(0, completed_bytes)
        total = max(completed, total_bytes) if total_bytes is not None else None
        percent = min(99, int(completed * 100 / total)) if total else None
        # `running` only: a progress row that arrived after the owner pressed
        # Cancel used to reinstate `running` and lose the request.
        return self._transition(
            owner_principal_id,
            operation_id,
            ("running",),
            state="running",
            phase=phase,
            progress_bytes=completed,
            total_bytes=total,
            progress_percent=percent,
        )

    def complete(self, owner_principal_id: str, operation_id: str) -> ModelOperation:
        operation = self.store.require_model_operation(owner_principal_id, operation_id)
        total = operation.total_bytes
        settled = self._transition(
            owner_principal_id,
            operation_id,
            _ACTIVE_STATES,
            state="complete",
            phase="complete",
            progress_bytes=total or operation.progress_bytes,
            progress_percent=100,
        )
        if settled.state == "cancel_requested":
            # The work finished and the owner had already asked it to stop. The
            # owner's decision is the one that stands, and the row reaches a
            # terminal state rather than waiting for a worker that has gone.
            return self.cancelled(owner_principal_id, operation_id)
        return settled

    def fail(self, owner_principal_id: str, operation_id: str, *, code: str) -> ModelOperation:
        return self._transition(
            owner_principal_id,
            operation_id,
            _STOPPABLE_STATES,
            state="failed",
            phase="failed",
            error_code=code,
            error_detail=None,
        )

    def cancel(self, owner_principal_id: str, operation_id: str) -> ModelOperation:
        operation = self.store.require_model_operation(owner_principal_id, operation_id)
        if operation.state in TERMINAL_STATES:
            return operation
        if operation.state == "queued":
            # Nothing has started, so there is nothing to co-operate with: the
            # request reaches its terminal state immediately rather than sitting
            # in `cancel_requested` waiting for a worker that never ran. If a
            # worker claimed it in between, this write is refused and the
            # cooperative path below is taken instead.
            settled = self.store.transition_model_operation(
                owner_principal_id,
                operation_id,
                expected_states=("queued",),
                state="cancelled",
                phase="cancelled",
                error_code=None,
                error_detail=None,
            )
            if settled is not None:
                return settled
        return self._transition(
            owner_principal_id, operation_id, ("running",), state="cancel_requested"
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
        return self._transition(
            owner_principal_id,
            operation_id,
            _STOPPABLE_STATES,
            state="cancelled",
            phase="cancelled",
            error_code=None,
            error_detail=None,
        )

    def retry(self, owner_principal_id: str, operation_id: str) -> ModelOperation:
        """Re-queue a **terminal** operation. The caller dispatches its worker.

        Retry used to check only that the kind was retryable and a payload
        existed, so pressing it against a running or already-completed job
        re-queued the row and started a second expensive worker over the same
        destination (GCR-21). The claim is the transition itself: two
        simultaneous presses cannot both take it.
        """
        operation = self.store.require_model_operation(owner_principal_id, operation_id)
        if operation.kind not in RETRYABLE_KINDS or not operation.payload():
            raise ValueError("operation_not_retryable")
        if operation.state not in RETRYABLE_STATES:
            raise ValueError("operation_not_retryable_from_state")
        claimed = self.store.transition_model_operation(
            owner_principal_id,
            operation_id,
            expected_states=RETRYABLE_STATES,
            state="queued",
            phase="queued",
            progress_bytes=0,
            progress_percent=None,
            error_code=None,
            error_detail=None,
        )
        if claimed is None:
            raise ValueError("operation_not_retryable_from_state")
        return claimed

    def partial_files(self, owner_principal_id: str, operation_id: str) -> dict[str, Any]:
        """What a confirmed cleanup would delete: the exact paths and their bytes.

        Named exactly, because a destructive confirmation that says "the
        destination" is not a confirmation — and because the destination of a
        conversion is the owner's shared output directory, which held other
        models (GCR-19). Only paths this operation can prove it created are
        listed; the caller still checks each against the owner's approved
        model-library roots before anything is removed.
        """
        operation = self.store.require_model_operation(owner_principal_id, operation_id)
        targets = operation.cleanup_targets()
        if not targets or operation.state not in TERMINAL_STATES:
            return {"path": None, "paths": [], "exists": False, "bytes": 0, "file_count": 0}
        present = [path for path in targets if Path(path).exists()]
        files: list[Path] = []
        for path in present:
            target = Path(path)
            if target.is_dir():
                files.extend(item for item in target.rglob("*") if item.is_file())
            else:
                files.append(target)
        return {
            "path": targets[0] if len(targets) == 1 else None,
            "paths": present,
            "exists": bool(present),
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
    kept: dict[str, Any] = {}
    for key, value in payload.items():
        if key not in _PAYLOAD_KEYS or value is None:
            continue
        # `artifacts` is the one list-valued key: the exact paths this operation
        # owns, stored as JSON so the row stays one flat string column.
        text = (
            json.dumps([str(item) for item in value if str(item)], sort_keys=True)
            if key == "artifacts" and isinstance(value, list | tuple)
            else str(value)
        )
        if text and text != "[]":
            kept[key] = text
    return kept


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
