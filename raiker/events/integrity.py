from __future__ import annotations

import hashlib
import json
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
    return {
        "session_id": session_id,
        "total_events": total,
        "passed": passed,
        "failed": total - passed,
        "chain_intact": chain_ok,
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
