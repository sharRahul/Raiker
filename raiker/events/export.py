from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import ExportManifest
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore

SECRET_PATTERNS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "api-key",
    "bearer",
    "authorization",
    "private_key",
    "private-key",
    "-----begin",
)


def _is_secret_key(key: str) -> bool:
    lower = key.lower()
    return any(p in lower for p in SECRET_PATTERNS)


def _redact_list_values(values: list[Any]) -> list[Any]:
    return [
        redact_event_payload(value)
        if isinstance(value, dict)
        else _redact_list_values(value)
        if isinstance(value, list)
        else "***REDACTED***"
        if isinstance(value, str)
        and len(value) > 0
        and any(p in value.lower() for p in SECRET_PATTERNS)
        else value
        for value in values
    ]


def redact_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in payload.items():
        if _is_secret_key(key):
            redacted[key] = "***REDACTED***"
            continue
        if isinstance(value, dict):
            redacted[key] = redact_event_payload(value)
        elif isinstance(value, list):
            redacted[key] = _redact_list_values(value)
        elif isinstance(value, str) and len(value) > 0:
            if any(p in value.lower() for p in SECRET_PATTERNS):
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = value
        else:
            redacted[key] = value
    return redacted


def _read_event_from_jsonl(path: Path, offset: int) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as f:
            f.seek(offset)
            line = f.readline()
        return json.loads(line) if line else None
    except (OSError, json.JSONDecodeError):
        return None


def build_export_manifest(
    store: SQLiteStore,
    session_id: str | None = None,
    *,
    project_id: str | None = None,
    redact: bool = True,
    exported_by: str = "cli",
) -> ExportManifest | None:
    redact = redact or project_id is not None
    events = store.list_event_index(
        session_id=session_id, project_id=project_id, limit=10000
    )
    if not events:
        return None
    event_ids = [str(e["event_id"]) for e in events]
    first_evt = events[-1]
    last_evt = events[0]
    scope = {
        "session_ids": [session_id] if session_id else list({str(e["session_id"]) for e in events}),
        "event_count": len(events),
        "first_event_id": first_evt["event_id"],
        "last_event_id": last_evt["event_id"],
        "first_timestamp": first_evt["timestamp"],
        "last_timestamp": last_evt["timestamp"],
        "redacted": redact,
    }
    if project_id is not None:
        scope["project_id"] = project_id
    hash_input = json.dumps(
        {"event_ids": event_ids, "scope": scope, "exported_by": exported_by},
        sort_keys=True,
        separators=(",", ":"),
    )
    manifest_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
    return ExportManifest(
        export_id=new_id("aex_"),
        manifest_hash=manifest_hash,
        scope_json=json.dumps(scope, sort_keys=True),
        redacted=redact,
        event_count=len(events),
        first_event_id=str(first_evt["event_id"]),
        last_event_id=str(last_evt["event_id"]),
        first_timestamp=str(first_evt["timestamp"]),
        last_timestamp=str(last_evt["timestamp"]),
        export_path=None,
        exported_by=exported_by,
        created_at=utc_now(),
    )


def generate_export(
    store: SQLiteStore,
    session_id: str | None = None,
    *,
    project_id: str | None = None,
    redact: bool = True,
    exported_by: str = "cli",
) -> ExportManifest:
    redact = redact or project_id is not None
    manifest = build_export_manifest(
        store,
        session_id,
        project_id=project_id,
        redact=redact,
        exported_by=exported_by,
    )
    if manifest is None:
        scope: dict[str, object] = {"event_count": 0, "redacted": redact}
        if project_id is not None:
            scope["project_id"] = project_id
        return ExportManifest(
            export_id=new_id("aex_"),
            manifest_hash="empty",
            scope_json=json.dumps(scope),
            redacted=redact,
            event_count=0,
            first_event_id=None,
            last_event_id=None,
            first_timestamp=None,
            last_timestamp=None,
            export_path=None,
            exported_by=exported_by,
            created_at=utc_now(),
        )
    writer = EventLogWriter(store)
    events_dir = writer.events_dir
    exports_dir = events_dir.parent / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    export_path = exports_dir / f"{manifest.export_id}.jsonl"
    event_rows = store.list_event_index(
        session_id=session_id, project_id=project_id, limit=10000
    )
    with export_path.open("w", encoding="utf-8") as out:
        for row in reversed(event_rows):
            path_str = str(row.get("jsonl_path", ""))
            offset = row.get("jsonl_offset")
            if not path_str or offset is None:
                continue
            evt = _read_event_from_jsonl(Path(path_str), int(offset))
            if evt is None:
                continue
            if redact and "payload" in evt and isinstance(evt["payload"], dict):
                evt["payload"] = redact_event_payload(evt["payload"])
            out.write(json.dumps(evt, sort_keys=True, separators=(",", ":")) + "\n")
    updated = ExportManifest(
        export_id=manifest.export_id,
        manifest_hash=manifest.manifest_hash,
        scope_json=manifest.scope_json,
        redacted=manifest.redacted,
        event_count=manifest.event_count,
        first_event_id=manifest.first_event_id,
        last_event_id=manifest.last_event_id,
        first_timestamp=manifest.first_timestamp,
        last_timestamp=manifest.last_timestamp,
        export_path=str(export_path),
        exported_by=manifest.exported_by,
        created_at=manifest.created_at,
    )
    store.insert_audit_export(updated)
    return updated
