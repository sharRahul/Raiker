from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import PurePath
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from raiker.contracts.ids import new_id, utc_now

TERMINAL_STATES = frozenset({"cancelled", "failed", "complete"})


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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ModelOperationService:
    def __init__(self, store: Any) -> None:
        self.store = store

    def start(self, owner_principal_id: str, request: ModelOperationRequest) -> ModelOperation:
        if not request.confirmed:
            raise ValueError("confirmation_required")
        if request.kind not in {"install", "download", "convert", "deploy", "pull"}:
            raise ValueError("unsupported_operation_kind")
        now = utc_now()
        operation = ModelOperation(
            operation_id=new_id("mop_"), owner_principal_id=owner_principal_id,
            kind=request.kind, target=request.target, state="queued", phase="queued",
            progress_bytes=0, total_bytes=None, progress_percent=None,
            source_url=_redact_source_url(request.source_url), destination=_redact_destination(request.destination),
            error_code=None, error_detail=None, created_at=now, updated_at=now,
        )
        self.store.save_model_operation(operation)
        return operation

    def list(self, owner_principal_id: str) -> list[ModelOperation]:
        return self.store.list_model_operations(owner_principal_id)

    def cancel(self, owner_principal_id: str, operation_id: str) -> ModelOperation:
        operation = self.store.require_model_operation(owner_principal_id, operation_id)
        if operation.state in TERMINAL_STATES:
            return operation
        return self.store.save_model_operation(replace(operation, state="cancel_requested", updated_at=utc_now()))

    def retry(self, owner_principal_id: str, operation_id: str) -> ModelOperation:
        operation = self.store.require_model_operation(owner_principal_id, operation_id)
        return self.store.save_model_operation(replace(
            operation, state="queued", phase="queued", progress_bytes=0,
            progress_percent=None, error_code=None, error_detail=None, updated_at=utc_now(),
        ))

    def cleanup(self, owner_principal_id: str, operation_id: str) -> bool:
        operation = self.store.require_model_operation(owner_principal_id, operation_id)
        if operation.state not in TERMINAL_STATES:
            return False
        return self.store.delete_model_operation(owner_principal_id, operation_id)

    def recover_abandoned(self) -> int:
        return self.store.fail_running_model_operations()


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
