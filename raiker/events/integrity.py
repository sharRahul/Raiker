from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from raiker.storage.sqlite import SQLiteStore


def _read_event_line(path: Path, offset: int) -> str | None:
    try:
        with path.open("r", encoding="utf-8") as f:
            f.seek(offset)
            line = f.readline()
        return line.rstrip("\n") if line else None
    except OSError:
        return None


def _line_offsets(path: Path) -> list[int] | None:
    """Every line-start byte offset in ``path``, or ``None`` if it cannot be read.

    Read as bytes so the offsets are the same ones ``EventLogWriter.append``
    recorded from ``handle.tell()``; on Windows a text-mode read would count
    translated newlines and disagree.
    """
    offsets: list[int] = []
    try:
        with path.open("rb") as handle:
            position = 0
            for line in handle:
                if line.strip():
                    offsets.append(position)
                position += len(line)
    except OSError:
        return None
    return offsets


def _unindexed_lines(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Lines present in a session's JSONL that the index has never heard of.

    GCR-40 — verification used to start from the database and read each indexed
    line by its stored offset, so it could only ever check lines the index
    already knew about. A line the index was missing was invisible to the very
    check whose job is to say whether the log and the index agree, and the next
    append chained past it because `prev_hash` also comes from the index. An
    orphan was therefore both undetectable and permanent.
    """
    indexed: dict[str, set[int]] = {}
    for row in rows:
        path_str = str(row.get("jsonl_path", ""))
        offset = row.get("jsonl_offset")
        if path_str and offset is not None:
            indexed.setdefault(path_str, set()).add(int(offset))
    orphans: list[dict[str, Any]] = []
    for path_str, known in indexed.items():
        present = _line_offsets(Path(path_str))
        if present is None:
            orphans.append({"jsonl_path": path_str, "error": "cannot_read_jsonl"})
            continue
        orphans.extend(
            {"jsonl_path": path_str, "jsonl_offset": offset, "error": "unindexed_line"}
            for offset in present
            if offset not in known
        )
    return orphans


def verify_session_events(
    store: SQLiteStore, session_id: str
) -> dict[str, Any]:
    rows = store.list_session_events_for_integrity(session_id)
    results: list[dict[str, Any]] = []
    chain_ok = True
    prev_hash: str | None = None
    for i, row in enumerate(rows):
        event_id = str(row["event_id"])
        stored_hash = str(row.get("payload_sha256", ""))
        stored_prev = row.get("prev_event_sha256")
        path_str = str(row.get("jsonl_path", ""))
        offset = row.get("jsonl_offset")
        check: dict[str, Any] = {
            "event_id": event_id,
            "index": i,
            "stored_hash": stored_hash,
        }
        if path_str and offset is not None:
            line = _read_event_line(Path(path_str), int(offset))
            if line:
                computed = hashlib.sha256(line.encode("utf-8")).hexdigest()
                check["hash_matches"] = computed == stored_hash
                if computed != stored_hash:
                    check["error"] = "hash_mismatch"
                    check["computed_hash"] = computed
            else:
                check["error"] = "cannot_read_jsonl"
        else:
            check["error"] = "missing_path_or_offset"
        if stored_prev is not None:
            stored_prev_str = str(stored_prev)
            check["stored_prev_hash"] = stored_prev_str
            if prev_hash is not None and stored_prev_str != prev_hash:
                check["chain_gap"] = True
                check["expected_prev"] = prev_hash
                chain_ok = False
            else:
                check["chain_gap"] = False
        else:
            check["stored_prev_hash"] = None
            if i > 0:
                check["chain_gap"] = True
                check["expected_prev"] = prev_hash
                chain_ok = False
            else:
                check["chain_gap"] = False
        prev_hash = stored_hash
        results.append(check)
    total = len(results)
    passed = sum(1 for r in results if r.get("hash_matches") is not False and not r.get("chain_gap"))
    orphans = _unindexed_lines(rows)
    return {
        "session_id": session_id,
        "total_events": total,
        "passed": passed,
        "failed": total - passed,
        "chain_intact": chain_ok and not orphans,
        # A line the physical log holds and the index does not. Reported
        # separately from `failed`, which counts *indexed* events that did not
        # verify: these are events the index cannot count at all (GCR-40).
        "unindexed_lines": orphans,
        "details": results,
    }


def compute_session_root_hash(
    store: SQLiteStore, session_id: str
) -> str | None:
    rows = store.list_session_events_for_integrity(session_id)
    if not rows:
        return None
    concatenated = "".join(str(r["payload_sha256"]) for r in rows)
    return hashlib.sha256(concatenated.encode("utf-8")).hexdigest()
