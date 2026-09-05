from __future__ import annotations

from pathlib import Path

import pytest

from raiker.models.local_operations import ModelOperationRequest, ModelOperationService
from raiker.storage.sqlite import SQLiteStore


def test_operation_lifecycle_is_durable_and_owner_scoped(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    service = ModelOperationService(store)
    operation = service.start("owner-a", ModelOperationRequest(kind="install", target="ollama", confirmed=True))

    assert operation.state == "queued"
    assert service.list("owner-a")[0].operation_id == operation.operation_id
    assert service.list("owner-b") == []
    # BUG-75 — nothing has started, so there is no worker to co-operate with:
    # the request reaches its terminal state rather than waiting for one.
    assert service.cancel("owner-a", operation.operation_id).state == "cancelled"


def test_cancelling_a_running_operation_waits_for_its_worker(tmp_path: Path) -> None:
    service = ModelOperationService(SQLiteStore(tmp_path))
    operation = service.start(
        "owner", ModelOperationRequest(kind="pull", target="tiny", confirmed=True),
        payload={"model": "tiny"},
    )
    service.running("owner", operation.operation_id, phase="pulling")

    assert service.cancel("owner", operation.operation_id).state == "cancel_requested"
    assert service.cancel_requested("owner", operation.operation_id) is True
    assert service.cancelled("owner", operation.operation_id).state == "cancelled"
    assert service.cancel_requested("owner", operation.operation_id) is False


def test_retry_requires_a_dispatchable_payload(tmp_path: Path) -> None:
    """A retry that cannot reconstruct its job is refused, not silently re-queued."""
    service = ModelOperationService(SQLiteStore(tmp_path))
    install = service.start(
        "owner", ModelOperationRequest(kind="install", target="ollama", confirmed=True)
    )
    service.fail("owner", install.operation_id, code="whatever")
    try:
        service.retry("owner", install.operation_id)
    except ValueError as exc:
        assert str(exc) == "operation_not_retryable"
    else:  # pragma: no cover - the assertion above is the contract
        raise AssertionError("an install has no worker to dispatch and must not be retryable")

    pull = service.start(
        "owner", ModelOperationRequest(kind="pull", target="tiny", confirmed=True),
        payload={"model": "tiny"},
    )
    service.fail("owner", pull.operation_id, code="ollama_pull_failed")
    requeued = service.retry("owner", pull.operation_id)
    assert requeued.state == "queued"
    assert requeued.payload() == {"model": "tiny"}
    assert requeued.to_dict()["retryable"] is True


def test_partial_files_names_the_exact_path_and_size(tmp_path: Path) -> None:
    """A destructive confirmation that says "the destination" is not one."""
    destination = tmp_path / "library" / "snapshot"
    destination.mkdir(parents=True)
    (destination / "model.gguf").write_bytes(b"x" * 128)
    service = ModelOperationService(SQLiteStore(tmp_path))
    operation = service.start(
        "owner",
        ModelOperationRequest(
            kind="download", target="repo/model", confirmed=True, destination=str(destination)
        ),
        payload={"destination": str(destination)},
    )
    # A running operation is not a cleanup candidate: its files are not partial yet.
    assert service.partial_files("owner", operation.operation_id)["exists"] is False
    service.fail("owner", operation.operation_id, code="hugging_face_download_failed")

    summary = service.partial_files("owner", operation.operation_id)
    assert summary["path"] == str(destination)
    assert summary["exists"] is True
    assert summary["bytes"] == 128
    assert summary["file_count"] == 1
    # Clear record stays metadata-only: the bytes are still on disk afterwards.
    assert service.cleanup("owner", operation.operation_id) is True
    assert (destination / "model.gguf").exists()


def test_the_payload_never_stores_a_credential(tmp_path: Path) -> None:
    service = ModelOperationService(SQLiteStore(tmp_path))
    operation = service.start(
        "owner",
        ModelOperationRequest(kind="download", target="repo/model", confirmed=True),
        payload={"repo_id": "org/model", "token": "hf_secret", "authorization": "Bearer x"},
    )
    stored = service.list("owner")[0]
    assert stored.payload() == {"repo_id": "org/model"}
    assert "hf_secret" not in stored.payload_json
    # The owner-facing projection never carries the payload at all.
    assert "payload_json" not in operation.to_dict()


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


def test_a_late_progress_row_cannot_overwrite_a_cancellation(tmp_path: Path) -> None:
    """GCR-20 — the race that lost a Cancel, run in the order it happened.

    A worker read `running`, the owner pressed Cancel, and the worker then stored
    the progress row it had already computed — with `state="running"` — over the
    request. Every lifecycle write is an expected-state transition now, so the
    write that arrives second is refused rather than applied.
    """
    service = ModelOperationService(SQLiteStore(tmp_path))
    operation = service.start(
        "owner",
        ModelOperationRequest(kind="pull", target="tiny", confirmed=True),
        payload={"model": "tiny"},
    )
    service.running("owner", operation.operation_id, phase="pulling")

    assert service.cancel("owner", operation.operation_id).state == "cancel_requested"
    late = service.progress(
        "owner", operation.operation_id, completed_bytes=50, total_bytes=100, phase="pulling"
    )

    assert late.state == "cancel_requested"
    assert service.cancel_requested("owner", operation.operation_id) is True


def test_a_completion_that_arrives_after_a_cancel_settles_as_cancelled(tmp_path: Path) -> None:
    """GCR-23 — the owner's decision stands, and the row still reaches a terminal state."""
    service = ModelOperationService(SQLiteStore(tmp_path))
    operation = service.start(
        "owner",
        ModelOperationRequest(kind="download", target="repo/model", confirmed=True),
        payload={"repo_id": "org/model"},
    )
    service.running("owner", operation.operation_id, phase="downloading")
    service.cancel("owner", operation.operation_id)

    settled = service.complete("owner", operation.operation_id)

    assert settled.state == "cancelled"
    assert settled.phase == "cancelled"


def test_a_worker_cannot_claim_an_operation_the_owner_already_cancelled(tmp_path: Path) -> None:
    service = ModelOperationService(SQLiteStore(tmp_path))
    operation = service.start(
        "owner",
        ModelOperationRequest(kind="pull", target="tiny", confirmed=True),
        payload={"model": "tiny"},
    )
    # Cancelled while still queued: it goes straight to its terminal state.
    assert service.cancel("owner", operation.operation_id).state == "cancelled"

    assert service.running("owner", operation.operation_id, phase="pulling").state == "cancelled"


def test_retry_is_refused_from_a_running_or_completed_operation(tmp_path: Path) -> None:
    """GCR-21 — Retry checked the kind and the payload, and never the state.

    So pressing it against a job that was still running re-queued the row and
    started a second worker over the same destination, and pressing it against a
    job that had succeeded ran the whole expensive thing again.
    """
    service = ModelOperationService(SQLiteStore(tmp_path))
    operation = service.start(
        "owner",
        ModelOperationRequest(kind="download", target="repo/model", confirmed=True),
        payload={"repo_id": "org/model"},
    )
    service.running("owner", operation.operation_id, phase="downloading")

    with pytest.raises(ValueError, match="operation_not_retryable_from_state"):
        service.retry("owner", operation.operation_id)

    service.complete("owner", operation.operation_id)
    with pytest.raises(ValueError, match="operation_not_retryable_from_state"):
        service.retry("owner", operation.operation_id)


def test_only_one_of_two_simultaneous_retries_claims_the_operation(tmp_path: Path) -> None:
    """The re-queue *is* the claim, so two presses cannot both dispatch a worker."""
    service = ModelOperationService(SQLiteStore(tmp_path))
    operation = service.start(
        "owner",
        ModelOperationRequest(kind="pull", target="tiny", confirmed=True),
        payload={"model": "tiny"},
    )
    service.fail("owner", operation.operation_id, code="ollama_pull_failed")

    assert service.retry("owner", operation.operation_id).state == "queued"
    with pytest.raises(ValueError, match="operation_not_retryable_from_state"):
        service.retry("owner", operation.operation_id)


def test_a_cancelled_operation_can_be_started_again(tmp_path: Path) -> None:
    service = ModelOperationService(SQLiteStore(tmp_path))
    operation = service.start(
        "owner",
        ModelOperationRequest(kind="pull", target="tiny", confirmed=True),
        payload={"model": "tiny"},
    )
    service.running("owner", operation.operation_id, phase="pulling")
    service.cancel("owner", operation.operation_id)
    service.cancelled("owner", operation.operation_id)

    assert service.retry("owner", operation.operation_id).state == "queued"


def test_a_conversion_owns_its_artifacts_and_never_its_output_directory(tmp_path: Path) -> None:
    """GCR-19 — the cleanup boundary is the operation's files, not a library folder.

    The output directory of a conversion is a directory the owner chose for
    their converted models. It holds the ones that succeeded. Reporting it as
    "the files this job left behind" made a confirmed cleanup of one failure a
    confirmed deletion of all of them.
    """
    library = tmp_path / "library"
    library.mkdir()
    unrelated = library / "already-converted.Q4_K_M.gguf"
    unrelated.write_bytes(b"y" * 64)
    intermediate = library / "mistral-abcdefabcdef.bf16.gguf"
    intermediate.write_bytes(b"x" * 32)
    service = ModelOperationService(SQLiteStore(tmp_path))
    operation = service.start(
        "owner",
        ModelOperationRequest(
            kind="convert", target="mistral@abc", confirmed=True, destination=str(library)
        ),
        payload={
            "source": str(tmp_path / "source"),
            "output": str(library),
            "destination": str(library),
            "artifacts": [str(intermediate), str(library / "mistral-abcdefabcdef.Q4_K_M.gguf")],
        },
    )
    service.fail("owner", operation.operation_id, code="model_conversion_failed")

    summary = service.partial_files("owner", operation.operation_id)

    assert summary["paths"] == [str(intermediate)]
    assert str(library) not in summary["paths"]
    assert summary["path"] is None
    assert summary["bytes"] == 32
    assert summary["file_count"] == 1


def test_a_conversion_recorded_before_artifacts_existed_offers_no_cleanup(tmp_path: Path) -> None:
    """A row written by an older Raiker names a shared directory and nothing else.

    It is not treated as an operation-owned target: the button is not offered,
    and `Clear record` still removes the row. Guessing here is what the defect
    was.
    """
    library = tmp_path / "library"
    library.mkdir()
    (library / "already-converted.Q4_K_M.gguf").write_bytes(b"y" * 64)
    service = ModelOperationService(SQLiteStore(tmp_path))
    operation = service.start(
        "owner",
        ModelOperationRequest(
            kind="convert", target="mistral@abc", confirmed=True, destination=str(library)
        ),
        payload={"source": str(tmp_path / "source"), "output": str(library),
                 "destination": str(library)},
    )
    service.fail("owner", operation.operation_id, code="model_conversion_failed")

    summary = service.partial_files("owner", operation.operation_id)

    assert summary["paths"] == []
    assert summary["exists"] is False
    assert service.require("owner", operation.operation_id).to_dict()[
        "partial_files_present"
    ] is False
