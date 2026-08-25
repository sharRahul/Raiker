"""Extraction and projection lifecycle for managed knowledge files."""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.contracts.ids import utc_now
from raiker.contracts.models import User
from raiker.knowledge.extractors import extract_managed_file, resolve_extractable_media_type
from raiker.knowledge.files import (
    ManagedFileError,
    ManagedFileRecord,
    ManagedFileScope,
    ManagedFileService,
)
from raiker.knowledge.indexing import ManagedFileIndexer, chunk_text
from raiker.storage.sqlite import SQLiteStore

OWNER = "principal_owner"
OTHER = "principal_other"


@pytest.fixture()
def owner_store(tmp_path: Path) -> SQLiteStore:
    store = SQLiteStore(tmp_path)
    now = utc_now()
    store.insert_user(User("user_owner", "Owner", None, True, now, now))
    store.insert_principal(OWNER, "human", "Owner", delegated_by_user_id="user_owner")
    store.insert_user(User("user_other", "Other", None, True, now, now))
    store.insert_principal(OTHER, "human", "Other", delegated_by_user_id="user_other")
    return store


@pytest.fixture()
def service(tmp_path: Path, owner_store: SQLiteStore) -> ManagedFileService:
    return ManagedFileService(tmp_path, owner_store)


@pytest.fixture()
def indexer(tmp_path: Path, owner_store: SQLiteStore) -> ManagedFileIndexer:
    return ManagedFileIndexer(tmp_path, owner_store)


@pytest.fixture()
def imported_text(service: ManagedFileService) -> ManagedFileRecord:
    return service.import_file(
        ManagedFileScope("memory"),
        "notes/handbook.md",
        b"# Handbook\n\nThe alpha deployment checklist lives here.\n",
        "text/markdown",
        OWNER,
    )


@pytest.fixture()
def imported_binary(service: ManagedFileService) -> ManagedFileRecord:
    return service.import_file(
        ManagedFileScope("memory"),
        "archive/data.custom",
        b"\x00\x01payload",
        "application/x-custom",
        OWNER,
    )


def test_text_file_is_chunked_with_provenance(
    indexer: ManagedFileIndexer, imported_text: ManagedFileRecord
) -> None:
    indexed = indexer.index(imported_text.file_id, OWNER)
    chunks = indexer.store.list_managed_file_chunks(imported_text.file_id, OWNER)

    assert indexed.index_state == "ready"
    assert chunks
    assert chunks[0]["source_file_id"] == imported_text.file_id
    assert chunks[0]["content_hash"] == imported_text.content_hash
    assert chunks[0]["scope_kind"] == "memory"
    assert chunks[0]["project_id"] is None
    assert "deployment checklist" in str(chunks[0]["text"])


def test_unknown_binary_is_metadata_only(
    indexer: ManagedFileIndexer, imported_binary: ManagedFileRecord
) -> None:
    indexed = indexer.index(imported_binary.file_id, OWNER)

    assert indexed.index_state == "metadata_only"
    assert indexed.index_error == "no_local_extractor"
    assert indexer.store.list_managed_file_chunks(imported_binary.file_id, OWNER) == []


def test_legacy_office_formats_stay_metadata_only(
    service: ManagedFileService, indexer: ManagedFileIndexer
) -> None:
    record = service.import_file(
        ManagedFileScope("memory"), "legacy/report.doc", b"\xd0\xcf\x11\xe0legacy", "application/msword", OWNER
    )

    indexed = indexer.index(record.file_id, OWNER)

    assert indexed.index_state == "metadata_only"
    assert indexed.index_error == "no_local_extractor"


def test_extension_resolves_a_reader_when_the_declared_type_has_none() -> None:
    assert resolve_extractable_media_type("notes/plan.md", "application/octet-stream") == "text/markdown"
    assert resolve_extractable_media_type("legacy/report.doc", "application/octet-stream") is None
    assert resolve_extractable_media_type("archive/data.custom", "application/x-custom") is None


def test_malformed_pdf_keeps_its_original_and_stays_unindexed(
    tmp_path: Path, service: ManagedFileService, indexer: ManagedFileIndexer
) -> None:
    record = service.import_file(
        ManagedFileScope("memory"), "docs/broken.pdf", b"%PDF-1.4 not really a pdf", "application/pdf", OWNER
    )

    indexed = indexer.index(record.file_id, OWNER)

    assert indexed.index_state in {"metadata_only", "failed"}
    assert indexed.index_error
    stored = tmp_path / ".raiker/memory-files/docs/broken.pdf"
    assert stored.read_bytes() == b"%PDF-1.4 not really a pdf"


def test_indexing_is_idempotent_for_one_revision(
    indexer: ManagedFileIndexer, imported_text: ManagedFileRecord
) -> None:
    indexer.index(imported_text.file_id, OWNER)
    first = [str(row["text"]) for row in indexer.store.list_managed_file_chunks(imported_text.file_id, OWNER)]

    indexer.index(imported_text.file_id, OWNER)
    second = [str(row["text"]) for row in indexer.store.list_managed_file_chunks(imported_text.file_id, OWNER)]

    assert first == second


def test_replacing_a_file_retires_the_previous_revision(
    tmp_path: Path, service: ManagedFileService, indexer: ManagedFileIndexer,
    imported_text: ManagedFileRecord,
) -> None:
    indexer.index(imported_text.file_id, OWNER)
    indexer.retire(imported_text.file_id, OWNER)
    replacement = service.import_file(
        ManagedFileScope("memory"),
        "notes/handbook.md",
        b"# Handbook\n\nThe beta rollout runbook lives here.\n",
        "text/markdown",
        OWNER,
    )
    indexer.index(replacement.file_id, OWNER)

    assert indexer.store.list_managed_file_chunks(imported_text.file_id, OWNER) == []
    hits = indexer.store.search_managed_file_chunks("deployment", owner_principal_id=OWNER)
    assert hits == []
    assert indexer.store.search_managed_file_chunks("rollout", owner_principal_id=OWNER)


def test_deleting_a_file_retires_every_projection(
    tmp_path: Path, service: ManagedFileService, indexer: ManagedFileIndexer,
    imported_text: ManagedFileRecord,
) -> None:
    indexer.index(imported_text.file_id, OWNER)

    indexer.retire(imported_text.file_id, OWNER)

    assert indexer.store.list_managed_file_chunks(imported_text.file_id, OWNER) == []
    assert indexer.store.search_managed_file_chunks("deployment", owner_principal_id=OWNER) == []
    assert not (tmp_path / ".raiker/memory-files/notes/handbook.md").exists()
    row = indexer.store.get_managed_file(imported_text.file_id, OWNER)
    assert row is not None
    assert row["retired_at"] is not None


def test_another_owner_cannot_index_or_retire_a_file(
    indexer: ManagedFileIndexer, imported_text: ManagedFileRecord
) -> None:
    with pytest.raises(ManagedFileError, match="managed_file_not_found"):
        indexer.index(imported_text.file_id, OTHER)
    with pytest.raises(ManagedFileError, match="managed_file_not_found"):
        indexer.retire(imported_text.file_id, OTHER)
    assert indexer.store.retire_managed_file_chunks(imported_text.file_id, OTHER) == 0


def test_search_is_scoped_to_the_owner(
    indexer: ManagedFileIndexer, imported_text: ManagedFileRecord
) -> None:
    indexer.index(imported_text.file_id, OWNER)

    assert indexer.store.search_managed_file_chunks("deployment", owner_principal_id=OWNER)
    assert indexer.store.search_managed_file_chunks("deployment", owner_principal_id=OTHER) == []


def test_missing_bytes_are_reported_without_losing_the_catalogue_row(
    tmp_path: Path, indexer: ManagedFileIndexer, imported_text: ManagedFileRecord
) -> None:
    (tmp_path / ".raiker/memory-files/notes/handbook.md").unlink()

    indexed = indexer.index(imported_text.file_id, OWNER)

    assert indexed.index_state == "failed"
    assert indexed.index_error == "file_unreadable"


def test_extract_managed_file_never_raises_for_a_missing_path(tmp_path: Path) -> None:
    result = extract_managed_file(tmp_path / "absent.md", "text/markdown")

    assert result.extracted is False
    assert result.reason == "file_unreadable"


def test_chunking_bounds_and_overlaps() -> None:
    text = "\n".join(f"line {index}" for index in range(600))

    chunks = chunk_text(text, size=200, overlap=20)

    assert len(chunks) > 1
    assert all(len(chunk) <= 200 for chunk in chunks)
    assert "line 0" in chunks[0]
    assert "line 599" in chunks[-1]
