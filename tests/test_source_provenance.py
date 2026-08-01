"""Resolving a memory's stored coordinates into the passage it came from (BUG-27).

What matters here is not that a happy path works — it is that every way of
*not* resolving produces its own named answer. Provenance you cannot check is
worth nothing; provenance that lies about why it cannot be checked is worse.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from raiker.memory.store import MemoryGovernance, write_memory
from raiker.runtime.source_provenance import (
    STATUS_NO_PROVENANCE,
    STATUS_RESOLVED,
    STATUS_SOURCE_CHANGED,
    STATUS_SOURCE_DELETED,
    SourceProvenanceService,
    build_excerpt,
    locate_passage,
)
from raiker.storage.sqlite import SQLiteStore

TURN_TEXT = (
    "Before we start, please remember that I prefer metric units in every report, "
    "and keep the summary under a page."
)
PASSAGE = "I prefer metric units in every report"


def _store_with_turn(tmp_path: Path) -> SQLiteStore:
    store = SQLiteStore(tmp_path)
    store.create_session("sess_1", str(tmp_path))
    store.insert_turn("sess_1", "turn_1", TURN_TEXT)
    return store


# ── locating a passage ──────────────────────────────────────────────────────


def test_a_passage_is_found_across_rewrapping_and_case() -> None:
    """A memory is stored as the sentence it means; a transcript may have
    wrapped or re-cased it, and that must not break provenance."""
    source = "Before we start,\n  please remember that I PREFER metric\n units in every report."
    start, length = locate_passage(source, "i prefer metric units in every report")
    assert start >= 0
    assert source[start : start + length].lower().replace("\n", " ").split() == [
        "i", "prefer", "metric", "units", "in", "every", "report",
    ]


def test_a_passage_that_is_not_there_is_not_approximated() -> None:
    """Never highlight something near it: a changed source must read as changed."""
    assert locate_passage(TURN_TEXT, "I prefer imperial units") == (-1, 0)
    assert locate_passage("", "anything") == (-1, 0)
    assert locate_passage("anything", "") == (-1, 0)


def test_an_excerpt_is_bounded_and_carries_the_offsets_of_the_passage() -> None:
    long_source = ("filler " * 2000) + PASSAGE + (" trailer" * 2000)
    excerpt, start, length, truncated = build_excerpt(long_source, PASSAGE)
    assert truncated is True
    assert len(excerpt) < len(long_source)
    assert excerpt[start : start + length] == PASSAGE


def test_an_unfound_passage_still_shows_the_source_without_a_highlight() -> None:
    excerpt, start, length, _ = build_excerpt(TURN_TEXT, "not in here at all")
    assert excerpt.startswith("Before we start")
    assert (start, length) == (-1, 0)


# ── resolving stored coordinates ────────────────────────────────────────────


def test_stored_coordinates_resolve_to_the_passage(tmp_path: Path) -> None:
    store = _store_with_turn(tmp_path)
    result = SourceProvenanceService(store).resolve(
        {"source_session_id": "sess_1", "source_turn_id": "turn_1"}, PASSAGE, "principal_owner"
    )
    assert result.status == STATUS_RESOLVED
    assert result.excerpt[result.highlight_start : result.highlight_start + result.highlight_length] == PASSAGE
    assert result.session_id == "sess_1"
    assert result.resolution_method == "matching_text"


def test_memory_capture_persists_utf8_byte_coordinates_and_hash(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    source = "Résumé notes: I prefer metric units in every report."
    store.create_session("sess_1", str(tmp_path))
    store.insert_turn("sess_1", "turn_1", source)
    entry = write_memory(
        PASSAGE,
        workspace_root=tmp_path,
        store=store,
        owner_principal_id="principal_owner",
        governance=MemoryGovernance(
            source_event_id="evt_1",
            source_session_id="sess_1",
            source_turn_id="turn_1",
            source_type="chat",
            confidence=1,
            trust_score=1,
            retention="until_forget",
            approval_state="approved",
            created_by="principal_owner",
        ),
    )
    start = entry.provenance["source_byte_start"]
    end = entry.provenance["source_byte_end"]
    captured = source.encode("utf-8")[start:end]
    assert captured.decode("utf-8") == PASSAGE
    assert entry.provenance["source_passage_sha256"] == hashlib.sha256(captured).hexdigest()

    result = SourceProvenanceService(store).resolve(
        entry.provenance, "wording no longer needed for lookup", "principal_owner"
    )
    assert result.status == STATUS_RESOLVED
    assert result.resolution_method == "stored_coordinates"
    assert result.excerpt[result.highlight_start : result.highlight_start + result.highlight_length] == PASSAGE


def test_changed_coordinates_fall_back_to_matching_text(tmp_path: Path) -> None:
    store = _store_with_turn(tmp_path)
    result = SourceProvenanceService(store).resolve(
        {
            "source_session_id": "sess_1",
            "source_turn_id": "turn_1",
            "source_byte_start": 0,
            "source_byte_end": 6,
            "source_passage_sha256": "not-the-current-hash",
        },
        PASSAGE,
        "principal_owner",
    )
    assert result.status == STATUS_RESOLVED
    assert result.resolution_method == "matching_text"


def test_a_record_with_no_coordinates_says_so_rather_than_guessing(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    result = SourceProvenanceService(store).resolve({}, PASSAGE, "principal_owner")
    assert result.status == STATUS_NO_PROVENANCE
    assert result.excerpt == ""


def test_a_deleted_source_is_reported_as_deleted(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    result = SourceProvenanceService(store).resolve(
        {"source_session_id": "sess_gone", "source_turn_id": "turn_gone"}, PASSAGE, "principal_owner"
    )
    assert result.status == STATUS_SOURCE_DELETED


def test_a_source_that_no_longer_holds_the_passage_is_reported_as_changed(
    tmp_path: Path,
) -> None:
    store = _store_with_turn(tmp_path)
    result = SourceProvenanceService(store).resolve(
        {"source_session_id": "sess_1", "source_turn_id": "turn_1"},
        "I prefer imperial units in every report",
        "principal_owner",
    )
    assert result.status == STATUS_SOURCE_CHANGED
    assert result.highlight_start == -1
    # The source is still shown — the owner can read it and judge for themselves.
    assert "Before we start" in result.excerpt
