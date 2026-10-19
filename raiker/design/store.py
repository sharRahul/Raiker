"""Rows for Raiker Design's structured documents (DW-01, DW-06, DW-08, DW-11).

Every read and write names the owner, and an id that belongs to someone else
reads exactly like one that was never issued. A document's change is written
with optimistic concurrency: it names the version it was made against, and a
second writer that got there first makes it a conflict rather than a silent
overwrite.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any

from raiker.contracts.ids import new_id, utc_now
from raiker.design.document import all_nodes, content_hash


class VersionConflict(Exception):
    """The document moved on since the version a change was made against."""


def _loads(raw: Any, default: Any) -> Any:
    try:
        value = json.loads(raw) if isinstance(raw, str) and raw else default
    except ValueError:
        return default
    return value


def _dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def diff_scope(before: Mapping[str, Any], after: Mapping[str, Any]) -> set[str]:
    """The frame and node ids that differ between two states of a document."""

    def index(document: Mapping[str, Any]) -> dict[str, str]:
        out: dict[str, str] = {}
        for frame in document.get("frames") or []:
            out[str(frame["id"])] = _dumps({k: v for k, v in frame.items() if k != "nodes"})
        for _frame, node in all_nodes(document):
            out[str(node["id"])] = _dumps({k: v for k, v in node.items() if k != "children"})
        return out

    a, b = index(before), index(after)
    return {key for key in a.keys() | b.keys() if a.get(key) != b.get(key)}


# ── Documents ────────────────────────────────────────────────────────────


def _document_view(row: Mapping[str, Any], *, with_doc: bool) -> dict[str, Any]:
    view = {
        "document_id": str(row["document_id"]),
        "title": str(row["title"]),
        "project_id": row["project_id"],
        "system_id": row["system_id"],
        "system_version": row["system_version"],
        "current_version": int(row["current_version"]),
        "content_hash": str(row["content_hash"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "deleted_at": row["deleted_at"],
    }
    document = _loads(row["doc_json"], {"frames": []})
    view["frame_count"] = len(document.get("frames") or [])
    if with_doc:
        view["document"] = document
    return view


def create_document(
    store: Any, *, owner: str, title: str, project_id: str | None, document: Mapping[str, Any],
) -> dict[str, Any]:
    document_id = new_id("ddoc_")
    system = document.get("system") or {}
    system_id, system_version = system.get("id"), system.get("version")
    now = utc_now()
    digest = content_hash(document)
    with store.connect() as connection:
        connection.execute(
            """INSERT INTO design_documents
               (document_id, owner_principal_id, title, project_id, system_id, system_version,
                current_version, doc_json, content_hash, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)""",
            (document_id, owner, title, project_id, system_id, system_version, _dumps(document), digest, now, now),
        )
        connection.execute(
            """INSERT INTO design_document_versions
               (document_id, version, owner_principal_id, actor, kind, summary, scope_json, ops_json,
                doc_json, content_hash, undo_parent, redo_target, proposal_id, created_at)
               VALUES (?, 1, ?, 'owner', 'create', 'Created the design', '[]', '[]', ?, ?, NULL, NULL, NULL, ?)""",
            (document_id, owner, _dumps(document), digest, now),
        )
    found = get_document(store, owner=owner, document_id=document_id)
    assert found is not None
    return found


def get_document(store: Any, *, owner: str, document_id: str, include_deleted: bool = False) -> dict[str, Any] | None:
    with store.connect() as connection:
        row = connection.execute(
            "SELECT * FROM design_documents WHERE document_id = ? AND owner_principal_id = ? "
            "AND (? OR deleted_at IS NULL)",
            (document_id, owner, 1 if include_deleted else 0),
        ).fetchone()
    return _document_view(dict(row), with_doc=True) if row is not None else None


def list_documents(store: Any, *, owner: str, deleted: bool = False, limit: int = 100) -> list[dict[str, Any]]:
    with store.connect() as connection:
        rows = connection.execute(
            "SELECT * FROM design_documents WHERE owner_principal_id = ? AND (deleted_at IS NOT NULL) = ? "
            "ORDER BY updated_at DESC, rowid DESC LIMIT ?",
            (owner, 1 if deleted else 0, max(1, min(int(limit), 200))),
        ).fetchall()
    return [_document_view(dict(row), with_doc=False) for row in rows]


_UNCHANGED = object()


def update_document_meta(
    store: Any, *, owner: str, document_id: str, title: Any = _UNCHANGED, project_id: Any = _UNCHANGED
) -> bool:
    """Rename or file. A field left out keeps its value; ``project_id`` None unfiles."""
    with store.connect() as connection:
        cursor = connection.execute(
            "UPDATE design_documents SET title = CASE WHEN ? THEN ? ELSE title END, "
            "project_id = CASE WHEN ? THEN ? ELSE project_id END, updated_at = ? "
            "WHERE document_id = ? AND owner_principal_id = ? AND deleted_at IS NULL",
            (
                title is not _UNCHANGED, None if title is _UNCHANGED else title,
                project_id is not _UNCHANGED, None if project_id is _UNCHANGED else project_id,
                utc_now(), document_id, owner,
            ),
        )
    return bool(cursor.rowcount == 1)


def set_document_deleted(store: Any, *, owner: str, document_id: str, deleted: bool) -> bool:
    """Put away (``deleted``) or bring back; each only from the opposite state."""
    with store.connect() as connection:
        cursor = connection.execute(
            "UPDATE design_documents SET deleted_at = ? WHERE document_id = ? AND owner_principal_id = ? "
            "AND (deleted_at IS NULL) = ?",
            (utc_now() if deleted else None, document_id, owner, 1 if deleted else 0),
        )
    return bool(cursor.rowcount == 1)


def commit_version(
    store: Any, *, owner: str, document_id: str, base_version: int, document: Mapping[str, Any],
    actor: str, kind: str, summary: str, scope: Iterable[str], operations: list[Any],
    undo_parent: int | None, redo_target: int | None = None, proposal_id: str | None = None,
) -> int:
    """Write *document* as the next version. :class:`VersionConflict` when *base_version* is stale."""
    now = utc_now()
    digest = content_hash(document)
    version = base_version + 1
    with store.connect() as connection:
        # The system choice lives in the document, so undo and restore carry it;
        # the columns mirror it for listing.
        system = document.get("system") or {}
        cursor = connection.execute(
            "UPDATE design_documents SET current_version = ?, doc_json = ?, content_hash = ?, updated_at = ?, "
            "system_id = ?, system_version = ? "
            "WHERE document_id = ? AND owner_principal_id = ? AND current_version = ? AND deleted_at IS NULL",
            (version, _dumps(document), digest, now, system.get("id"), system.get("version"),
             document_id, owner, base_version),
        )
        if cursor.rowcount != 1:
            raise VersionConflict(document_id)
        connection.execute(
            """INSERT INTO design_document_versions
               (document_id, version, owner_principal_id, actor, kind, summary, scope_json, ops_json,
                doc_json, content_hash, undo_parent, redo_target, proposal_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (document_id, version, owner, actor, kind, summary[:300], _dumps(sorted(set(scope))),
             _dumps(operations), _dumps(document), digest, undo_parent, redo_target, proposal_id, now),
        )
    return version


def _version_view(row: Mapping[str, Any], *, with_doc: bool) -> dict[str, Any]:
    view = {
        "version": int(row["version"]),
        "actor": str(row["actor"]),
        "kind": str(row["kind"]),
        "summary": str(row["summary"]),
        "scope": list(_loads(row["scope_json"], [])),
        "operation_count": len(_loads(row["ops_json"], [])),
        "content_hash": str(row["content_hash"]),
        "undo_parent": row["undo_parent"],
        "redo_target": row["redo_target"],
        "proposal_id": row["proposal_id"],
        "created_at": str(row["created_at"]),
    }
    if with_doc:
        view["document"] = _loads(row["doc_json"], {"frames": []})
    return view


def get_version(store: Any, *, owner: str, document_id: str, version: int) -> dict[str, Any] | None:
    with store.connect() as connection:
        row = connection.execute(
            "SELECT * FROM design_document_versions WHERE document_id = ? AND owner_principal_id = ? AND version = ?",
            (document_id, owner, int(version)),
        ).fetchone()
    return _version_view(dict(row), with_doc=True) if row is not None else None


def list_versions(store: Any, *, owner: str, document_id: str, limit: int = 100) -> list[dict[str, Any]]:
    with store.connect() as connection:
        rows = connection.execute(
            "SELECT * FROM design_document_versions WHERE document_id = ? AND owner_principal_id = ? "
            "ORDER BY version DESC LIMIT ?",
            (document_id, owner, max(1, min(int(limit), 500))),
        ).fetchall()
    return [_version_view(dict(row), with_doc=False) for row in rows]


def scope_since(store: Any, *, owner: str, document_id: str, version: int) -> dict[str, int]:
    """Every id changed after *version*, with the first later version that changed it."""
    with store.connect() as connection:
        rows = connection.execute(
            "SELECT version, scope_json FROM design_document_versions WHERE document_id = ? "
            "AND owner_principal_id = ? AND version > ? ORDER BY version",
            (document_id, owner, int(version)),
        ).fetchall()
    changed: dict[str, int] = {}
    for row in rows:
        for node_id in _loads(row["scope_json"], []):
            changed.setdefault(str(node_id), int(row["version"]))
    return changed


# ── Design systems ───────────────────────────────────────────────────────


def _system_view(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "system_id": str(row["system_id"]),
        "version": int(row["version"]),
        "name": str(row["name"]),
        "source_note": str(row["source_note"]),
        "variables": _loads(row["variables_json"], {}),
        "created_at": str(row["created_at"]),
    }


def save_system(store: Any, *, owner: str, system_id: str | None, name: str, source_note: str,
                variables: Mapping[str, Any]) -> dict[str, Any] | None:
    """A new system (``system_id`` None) or the next version of an existing one."""
    with store.connect() as connection:
        if system_id is None:
            system_id, version = new_id("dsys_"), 1
        else:
            row = connection.execute(
                "SELECT MAX(version) AS v FROM design_systems WHERE system_id = ? AND owner_principal_id = ?",
                (system_id, owner),
            ).fetchone()
            if row is None or row["v"] is None:
                return None
            version = int(row["v"]) + 1
        connection.execute(
            """INSERT INTO design_systems (system_id, version, owner_principal_id, name, source_note, variables_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (system_id, version, owner, name, source_note, _dumps(variables), utc_now()),
        )
    return get_system(store, owner=owner, system_id=system_id, version=version)


def get_system(store: Any, *, owner: str, system_id: str, version: int | None = None) -> dict[str, Any] | None:
    with store.connect() as connection:
        if version is None:
            row = connection.execute(
                "SELECT * FROM design_systems WHERE system_id = ? AND owner_principal_id = ? ORDER BY version DESC LIMIT 1",
                (system_id, owner),
            ).fetchone()
        else:
            row = connection.execute(
                "SELECT * FROM design_systems WHERE system_id = ? AND owner_principal_id = ? AND version = ?",
                (system_id, owner, int(version)),
            ).fetchone()
    return _system_view(dict(row)) if row is not None else None


def list_systems(store: Any, *, owner: str) -> list[dict[str, Any]]:
    """The latest version of each of this owner's systems."""
    with store.connect() as connection:
        rows = connection.execute(
            """SELECT s.* FROM design_systems s
               JOIN (SELECT system_id, MAX(version) AS v FROM design_systems
                     WHERE owner_principal_id = ? GROUP BY system_id) latest
                 ON latest.system_id = s.system_id AND latest.v = s.version
               WHERE s.owner_principal_id = ? ORDER BY s.name COLLATE NOCASE""",
            (owner, owner),
        ).fetchall()
    return [_system_view(dict(row)) for row in rows]


# ── Proposals ────────────────────────────────────────────────────────────


def _proposal_view(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "proposal_id": str(row["proposal_id"]),
        "document_id": str(row["document_id"]),
        "base_version": int(row["base_version"]),
        "frame_id": str(row["frame_id"]),
        "brief": str(row["brief"]),
        "provider": str(row["provider"]),
        "model": str(row["model"]),
        "plan": _loads(row["plan_json"], {}),
        "operations": _loads(row["operations_json"], []),
        "status": str(row["status"]),
        "result": _loads(row["result_json"], None),
        "created_at": str(row["created_at"]),
        "decided_at": row["decided_at"],
    }


def save_proposal(store: Any, *, owner: str, document_id: str, base_version: int, frame_id: str, brief: str,
                  provider: str, model: str, plan: Mapping[str, Any], operations: list[Any]) -> dict[str, Any]:
    proposal_id = new_id("dprop_")
    with store.connect() as connection:
        connection.execute(
            """INSERT INTO design_proposals
               (proposal_id, owner_principal_id, document_id, base_version, frame_id, brief, provider, model,
                plan_json, operations_json, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (proposal_id, owner, document_id, base_version, frame_id, brief, provider, model,
             _dumps(plan), _dumps(operations), utc_now()),
        )
    found = get_proposal(store, owner=owner, proposal_id=proposal_id)
    assert found is not None
    return found


def get_proposal(store: Any, *, owner: str, proposal_id: str) -> dict[str, Any] | None:
    with store.connect() as connection:
        row = connection.execute(
            "SELECT * FROM design_proposals WHERE proposal_id = ? AND owner_principal_id = ?", (proposal_id, owner)
        ).fetchone()
    return _proposal_view(dict(row)) if row is not None else None


def list_proposals(store: Any, *, owner: str, document_id: str, limit: int = 20) -> list[dict[str, Any]]:
    with store.connect() as connection:
        rows = connection.execute(
            "SELECT * FROM design_proposals WHERE owner_principal_id = ? AND document_id = ? "
            "ORDER BY created_at DESC, rowid DESC LIMIT ?",
            (owner, document_id, max(1, min(int(limit), 100))),
        ).fetchall()
    return [_proposal_view(dict(row)) for row in rows]


def decide_proposal(store: Any, *, owner: str, proposal_id: str, status: str, result: Mapping[str, Any]) -> bool:
    """Record the owner's decision once; a decided proposal is never decided again."""
    with store.connect() as connection:
        cursor = connection.execute(
            "UPDATE design_proposals SET status = ?, result_json = ?, decided_at = ? "
            "WHERE proposal_id = ? AND owner_principal_id = ? AND status = 'pending'",
            (status, _dumps(result), utc_now(), proposal_id, owner),
        )
    return bool(cursor.rowcount == 1)


# ── Exports and handoffs ─────────────────────────────────────────────────


def _export_view(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "export_id": str(row["export_id"]),
        "document_id": str(row["document_id"]),
        "version": int(row["version"]),
        "frame_id": str(row["frame_id"]),
        "format": str(row["format"]),
        "settings": _loads(row["settings_json"], {}),
        "validation_outcome": str(_loads(row["validation_json"], {}).get("outcome") or "unknown"),
        "media_type": str(row["media_type"]),
        "sha256": str(row["sha256"]),
        "byte_size": int(row["byte_size"]),
        "created_at": str(row["created_at"]),
    }


def save_export(store: Any, *, owner: str, document_id: str, version: int, frame_id: str, fmt: str,
                settings: Mapping[str, Any], validation: Mapping[str, Any], media_type: str, sha256: str,
                data: bytes) -> dict[str, Any]:
    export_id = new_id("dexp_")
    with store.connect() as connection:
        connection.execute(
            """INSERT INTO design_exports
               (export_id, owner_principal_id, document_id, version, frame_id, format, settings_json,
                validation_json, media_type, sha256, byte_size, data, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (export_id, owner, document_id, version, frame_id, fmt, _dumps(settings), _dumps(validation),
             media_type, sha256, len(data), data, utc_now()),
        )
        row = connection.execute("SELECT * FROM design_exports WHERE export_id = ?", (export_id,)).fetchone()
    return _export_view(dict(row))


def list_exports(store: Any, *, owner: str, document_id: str, limit: int = 20) -> list[dict[str, Any]]:
    with store.connect() as connection:
        rows = connection.execute(
            "SELECT * FROM design_exports WHERE owner_principal_id = ? AND document_id = ? "
            "ORDER BY created_at DESC, rowid DESC LIMIT ?",
            (owner, document_id, max(1, min(int(limit), 100))),
        ).fetchall()
    return [_export_view(dict(row)) for row in rows]


def export_bytes(store: Any, *, owner: str, export_id: str) -> tuple[dict[str, Any], bytes] | None:
    with store.connect() as connection:
        row = connection.execute(
            "SELECT * FROM design_exports WHERE export_id = ? AND owner_principal_id = ?", (export_id, owner)
        ).fetchone()
    if row is None:
        return None
    return _export_view(dict(row)), bytes(row["data"])


def save_handoff(store: Any, *, owner: str, document_id: str, version: int, frame_ids: list[str], target: str,
                 attachment_id: str, sha256: str) -> dict[str, Any]:
    handoff_id = new_id("dhand_")
    now = utc_now()
    with store.connect() as connection:
        connection.execute(
            """INSERT INTO design_handoffs
               (handoff_id, owner_principal_id, document_id, version, frame_ids_json, target, attachment_id,
                sha256, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (handoff_id, owner, document_id, version, _dumps(frame_ids), target, attachment_id, sha256, now),
        )
    return {"handoff_id": handoff_id, "document_id": document_id, "version": version, "frame_ids": frame_ids,
            "target": target, "attachment_id": attachment_id, "sha256": sha256, "created_at": now}


def list_handoffs(store: Any, *, owner: str, document_id: str, limit: int = 10) -> list[dict[str, Any]]:
    with store.connect() as connection:
        rows = connection.execute(
            "SELECT * FROM design_handoffs WHERE owner_principal_id = ? AND document_id = ? "
            "ORDER BY created_at DESC, rowid DESC LIMIT ?",
            (owner, document_id, max(1, min(int(limit), 50))),
        ).fetchall()
    return [
        {"handoff_id": str(row["handoff_id"]), "document_id": str(row["document_id"]), "version": int(row["version"]),
         "frame_ids": list(_loads(row["frame_ids_json"], [])), "target": str(row["target"]),
         "attachment_id": str(row["attachment_id"]), "sha256": str(row["sha256"]),
         "created_at": str(row["created_at"])}
        for row in rows
    ]


def asset_usage(store: Any, *, owner: str, asset_id: str) -> list[dict[str, Any]]:
    """DW-05 — the live documents that place *asset_id*, so removing it is never silent."""
    with store.connect() as connection:
        rows = connection.execute(
            "SELECT document_id, title, doc_json FROM design_documents "
            "WHERE owner_principal_id = ? AND deleted_at IS NULL AND instr(doc_json, ?) > 0",
            (owner, asset_id),
        ).fetchall()
    used = []
    for row in rows:
        document = _loads(row["doc_json"], {"frames": []})
        layers = [node["id"] for _f, node in all_nodes(document) if node.get("asset_id") == asset_id]
        if layers:
            used.append({"document_id": str(row["document_id"]), "title": str(row["title"]), "layers": len(layers)})
    return used
