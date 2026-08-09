from __future__ import annotations

from pathlib import Path

from raiker.models.local_operations import ModelOperationRequest, ModelOperationService
from raiker.storage.sqlite import SQLiteStore


def test_operation_lifecycle_is_durable_and_owner_scoped(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    service = ModelOperationService(store)
    operation = service.start("owner-a", ModelOperationRequest(kind="install", target="ollama", confirmed=True))

    assert operation.state == "queued"
    assert service.list("owner-a")[0].operation_id == operation.operation_id
    assert service.list("owner-b") == []
    assert service.cancel("owner-a", operation.operation_id).state == "cancel_requested"
    assert service.retry("owner-a", operation.operation_id).state == "queued"


def test_abandoned_running_operation_is_failed_on_recovery(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    service = ModelOperationService(store)
    operation = service.start("owner", ModelOperationRequest(kind="download", target="repo/model", confirmed=True))
    store.update_model_operation(operation.operation_id, state="running", phase="downloading")

    recovered = service.recover_abandoned()

    assert recovered == 1
    assert service.list("owner")[0].state == "failed"
    assert service.list("owner")[0].error_code == "host_restarted"


def test_cleanup_only_removes_terminal_owner_operations(tmp_path: Path) -> None:
    service = ModelOperationService(SQLiteStore(tmp_path))
    operation = service.start("owner", ModelOperationRequest(kind="install", target="ollama", confirmed=True))
    assert service.cleanup("owner", operation.operation_id) is False
    service.store.update_model_operation(operation.operation_id, state="cancelled")
    assert service.cleanup("owner", operation.operation_id) is True


def test_operation_storage_redacts_url_credentials_and_absolute_destination(tmp_path: Path) -> None:
    service = ModelOperationService(SQLiteStore(tmp_path))
    service.start(
        "owner",
        ModelOperationRequest(
            kind="download", target="repo/model", confirmed=True,
            source_url="https://user:secret@example.com/model.gguf?token=abc",
            destination="C:/Users/Alice/private/models/model.gguf",
        ),
    )
    stored = service.list("owner")[0]
    assert "secret" not in (stored.source_url or "")
    assert "token" not in (stored.source_url or "")
    assert "Alice" not in (stored.destination or "")
    assert stored.destination == "<model-library>/model.gguf"
