"""Projection lifecycle for managed knowledge files.

A managed file's *bytes* are the record; its chunks are a projection that can be
rebuilt, retired, and republished without touching what the owner imported. That
asymmetry is the whole design:

* ``index`` extracts bounded text and republishes one revision's chunks. It is
  idempotent by content hash — re-running it on an unchanged file produces the
  same projection, and re-running it after a replacement retires the stale
  revision before publishing the new one.
* ``retire`` drops every projection for a file. Deleting or replacing a file
  can therefore never leave a stale chunk marked current.
* An extraction failure is recorded as state on the catalogue row and never
  destroys the stored original.

Chunk text is untrusted source data. Nothing here executes an uploaded file, and
nothing here treats its content as instructions.
"""

from __future__ import annotations

from pathlib import Path

from raiker.knowledge.extractors import extract_managed_file
from raiker.knowledge.files import ManagedFileError, ManagedFileRecord, ManagedFileService
from raiker.storage.sqlite import SQLiteStore

#: Target characters per chunk. Large enough that a paragraph survives intact,
#: small enough that a hit quotes a passage rather than a chapter.
CHUNK_CHARS = 1_200

#: Characters repeated from the end of the previous chunk, so a sentence split
#: across a boundary is still findable from either side.
CHUNK_OVERLAP_CHARS = 120

#: Hard cap on chunks per file revision. A pathological upload must not be able
#: to grow the lexical index without bound.
MAX_CHUNKS_PER_FILE = 400

INDEX_STATE_QUEUED = "queued"
INDEX_STATE_INDEXING = "indexing"
INDEX_STATE_READY = "ready"
INDEX_STATE_METADATA_ONLY = "metadata_only"
INDEX_STATE_FAILED = "failed"


def chunk_text(text: str, *, size: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP_CHARS) -> list[str]:
    """Split *text* into bounded overlapping chunks, preferring line breaks.

    The split point is nudged back to the last newline in the final quarter of a
    chunk when there is one, so a chunk usually ends where the document does
    rather than mid-word.
    """
    if size < 1:
        raise ValueError("invalid_chunk_size")
    overlap = max(0, min(overlap, size - 1))
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    chunks: list[str] = []
    start = 0
    length = len(normalized)
    while start < length and len(chunks) < MAX_CHUNKS_PER_FILE:
        end = min(start + size, length)
        if end < length:
            window_start = start + (size * 3) // 4
            break_at = normalized.rfind("\n", window_start, end)
            if break_at > start:
                end = break_at
        piece = normalized[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= length:
            break
        start = max(end - overlap, start + 1)
    return chunks


class ManagedFileIndexer:
    """Publishes and retires the text projection of one owner's managed files."""

    def __init__(self, workspace_root: str | Path, store: SQLiteStore) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.store = store
        self.files = ManagedFileService(self.workspace_root, store)

    def index(self, file_id: str, owner_principal_id: str) -> ManagedFileRecord:
        """Extract and republish the projection for one file revision."""
        row = self.store.get_managed_file(file_id, owner_principal_id)
        if row is None:
            raise ManagedFileError("managed_file_not_found")
        record = ManagedFileRecord.from_row(row)
        if record.retired_at is not None:
            raise ManagedFileError("managed_file_retired")
        self.store.set_managed_file_index_state(
            file_id, owner_principal_id, INDEX_STATE_INDEXING, None
        )
        path = self.resolve_path(record, owner_principal_id)
        result = extract_managed_file(
            path, record.media_type, relative_path=record.relative_path
        )
        # The old revision's chunks go regardless of the new outcome: a file that
        # became unreadable must not keep answering with what it used to say.
        self.store.retire_managed_file_chunks(file_id, owner_principal_id)
        if not result.extracted:
            state = (
                INDEX_STATE_FAILED
                if result.reason in {"file_unreadable", "extraction_failed"}
                else INDEX_STATE_METADATA_ONLY
            )
            self.store.set_managed_file_index_state(
                file_id, owner_principal_id, state, result.reason
            )
            return self._reload(file_id, owner_principal_id)
        chunks = chunk_text(result.text)
        if not chunks:
            self.store.set_managed_file_index_state(
                file_id, owner_principal_id, INDEX_STATE_METADATA_ONLY, "no_extractable_text"
            )
            return self._reload(file_id, owner_principal_id)
        self.store.replace_managed_file_chunks(
            file_id=file_id,
            owner_principal_id=owner_principal_id,
            scope_kind=record.scope_kind,
            project_id=record.project_id,
            content_hash=record.content_hash,
            chunks=chunks,
        )
        self.store.set_managed_file_index_state(
            file_id,
            owner_principal_id,
            INDEX_STATE_READY,
            "truncated" if result.truncated else None,
        )
        return self._reload(file_id, owner_principal_id)

    def retire(self, file_id: str, owner_principal_id: str) -> ManagedFileRecord:
        """Retire one file completely: projections first, then bytes and row.

        Projections go before the bytes so an interrupted retirement can only
        ever leave a stored original with no index -- recoverable by re-indexing
        -- and never an index pointing at bytes that are gone.
        """
        if self.store.get_managed_file(file_id, owner_principal_id) is None:
            raise ManagedFileError("managed_file_not_found")
        self.store.retire_managed_file_chunks(file_id, owner_principal_id)
        return self.files.delete_file(file_id, owner_principal_id)

    def resolve_path(self, record: ManagedFileRecord, owner_principal_id: str) -> Path:
        """The contained on-disk path of *record*, re-validated on every read.

        Containment is re-derived from the scope rather than trusted from the
        stored string, so a tampered catalogue row cannot make the indexer read
        outside the managed root.
        """
        root = self.files.scope_root(record.scope(), owner_principal_id)
        return self.files.contained_destination(root, record.relative_path)

    def _reload(self, file_id: str, owner_principal_id: str) -> ManagedFileRecord:
        row = self.store.get_managed_file(file_id, owner_principal_id)
        if row is None:  # pragma: no cover - the row was read moments ago
            raise ManagedFileError("managed_file_not_found")
        return ManagedFileRecord.from_row(row)
