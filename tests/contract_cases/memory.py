"""Memory, the Knowledge Map's sources, and what Raiker may read."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from raiker.contracts.ids import utc_now
from raiker.control.service import RuntimeControlService
from raiker.memory.candidates import create_deferred_candidate
from raiker.memory.eidetic import propose_gist, record_observation
from raiker.memory.store import MemoryGovernance, write_memory
from raiker.storage.sqlite import SQLiteStore
from tests.contract_cases.base import Call, Cases, Seed, patched, plain

OWNER = "principal_owner"


def _memory(ws: Path, text: str = "Rahul uses Python.") -> None:
    write_memory(
        text, workspace_root=ws, store=SQLiteStore(ws),
        governance=MemoryGovernance(
            "evt_m", "", None, "test", 1.0, 1.0, "until_forget", "approved", OWNER
        ),
    )


def _memory_id(client: TestClient, h: dict[str, str]) -> str:
    rows = client.get("/api/memory", headers=h).json()
    assert rows, "no memory to address"
    return str(rows[0]["memory_id"])


def _on_memory(suffix: str, body: Any = None, method_headers: bool = False) -> Seed:
    def seed(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
        _memory(ws)
        memory_id = _memory_id(client, h)
        path = f"/api/memory/{memory_id}{suffix}"
        if method_headers:
            return path, body, {**h, "X-Memory-Purge-Confirm": memory_id}
        return path if body is None else (path, body)

    return seed


def _scope(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    _memory(ws)
    row = client.get("/api/memory", headers=h).json()[0]
    return (
        f"/api/memory/{row['memory_id']}/scope",
        {"scope": "account", "expected_updated_at": row.get("updated_at"), "reason": "contract"},
    )


def _export(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    _memory(ws)
    return "/api/memory/export"


def _candidate(ws: Path) -> str:
    candidate = create_deferred_candidate("evt_p", "Use tabs.", "global")
    SQLiteStore(ws).insert_memory_candidate(candidate, owner_principal_id=OWNER)
    return str(candidate.candidate_id)


def _proposals(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    _candidate(ws)
    return "/api/memory/proposals"


def _proposal_decision(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    return (
        f"/api/memory/proposals/{_candidate(ws)}/decision",
        {"decision": "approved", "expected_decision": "deferred"},
    )


def _relationships(prefix: str) -> Seed:
    def seed(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
        _memory(ws)
        client.post(f"/api/memory/{prefix}/scan", headers=h)
        return f"/api/memory/{prefix}"

    return seed


def _scan(prefix: str) -> Seed:
    def seed(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
        _memory(ws)
        return f"/api/memory/{prefix}/scan"

    return seed


def _relationship_candidate(ws: Path, client: TestClient, h: dict[str, str], prefix: str) -> str:
    _memory(ws)
    client.post(f"/api/memory/{prefix}/scan", headers=h)
    rows = client.get(f"/api/memory/{prefix}", headers=h).json()
    assert rows, "the scan proposed nothing"
    return str(rows[0]["candidate_id"])


def _relationship_decision(prefix: str) -> Seed:
    def seed(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
        candidate_id = _relationship_candidate(ws, client, h, prefix)
        return (
            f"/api/memory/{prefix}/{candidate_id}/decision",
            {"decision": "approved", "expected_decision": "needs_user_review"},
        )

    return seed


def _relationship_reject(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    candidate_id = _relationship_candidate(ws, client, h, "relationship-proposals")
    decided = client.post(
        f"/api/memory/relationship-proposals/{candidate_id}/decision",
        json={"decision": "approved", "expected_decision": "needs_user_review"},
        headers=h,
    ).json()
    return (
        f"/api/memory/entity-relationships/{decided['relationship_id']}/reject",
        {"reason": "contract", "expected_active": True},
    )


def _observation(ws: Path) -> str:
    store = SQLiteStore(ws)
    store.create_session("sess_obs", str(ws))
    item = record_observation(
        store=store, source_event_id="evt_o", session_id="sess_obs", summary="Read a file",
        content="file body", owner_principal_id=OWNER, turn_id="turn_o", tool_name="read_file",
    )
    return str(item.observation_id)


def _observations(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    _observation(ws)
    return "/api/memory/observations"


def _gist(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    gist = propose_gist(
        store=SQLiteStore(ws), observation_id=_observation(ws), summary="A gist", confidence=0.5
    )
    return f"/api/memory/gists/{gist.gist_id}/discard"


def _delete_observations(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    return "/api/memory/observations/delete", {"observation_ids": [_observation(ws)]}


def _cleanup(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    # Thirty-day retention, swept a century later: due, and confirmed by id.
    return (
        "/api/memory/eidetic/cleanup",
        {"observation_ids": [_observation(ws)], "now": "2126-01-01T00:00:00Z"},
    )


def _enable_embeddings(ws: Path) -> None:
    capability = "model_provider_runtime"
    service = RuntimeControlService(ws)
    service.activate_runtime_mode("local_single_user_runtime", None, "test")
    with SQLiteStore(ws).connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref)"
            " VALUES (?, ?, ?, ?)",
            (capability, OWNER, utc_now(), "docs/threat-models/model-provider.md"),
        )
    result = service.set_capability_state(
        capability, "enabled_runtime", None, "test", confirmation_token="confirm"
    )
    assert result.ok, result.reason_code


def _fake_embedder(monkeypatch: Any) -> None:
    from raiker.models.contracts import EmbeddingResponse
    from raiker.runtime.executors.models_runtime import ModelProviderExecutor

    def embedder(_self: Any, _principal_id: str) -> Any:
        return lambda provider, model, text: EmbeddingResponse(
            vector=[0.1, 0.2, 0.3], model=model, usage=None
        )

    monkeypatch.setattr(ModelProviderExecutor, "_default_embedder", embedder)


def _embedding_index(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    _enable_embeddings(ws)
    _memory(ws)
    return "/api/memory/embedding-index", {"provider": "llama.cpp", "model": "local-gguf"}


IMPORTED = {"memories": [{"text": "Deploys happen on Thursdays."}]}


def _upload(client: TestClient, h: dict[str, str]) -> str:
    uploaded = client.post(
        "/api/brain/sources/upload",
        json={
            "filename": "notes.md",
            "content_base64": base64.b64encode(b"# Notes\n\nA note.").decode(),
            "store_copy": True,
        },
        headers=h,
    )
    assert uploaded.status_code == 200, uploaded.text
    return str(uploaded.json()["path"])


def _brain_source(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    return "/api/brain/sources", {"path": _upload(client, h)}


def _brain_source_removed(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    path = _upload(client, h)
    client.post("/api/brain/sources", json={"path": path}, headers=h)
    return f"/api/brain/sources?path={path}"


def _brain_review(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    return "/api/brain/sources/review", {"path": _upload(client, h)}


def _brain_browse(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    path = _upload(client, h)
    return "/api/brain/sources/browse?path=" + path.rsplit("/", 1)[0]


def _folder(ws: Path) -> Path:
    folder = ws.parent / "granted-folder"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "readme.md").write_bytes(b"# Readme\n")
    return folder


def _grant(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    return "/api/brain/sources/grants", {"path": str(_folder(ws))}


def _revoke_grant(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    granted = client.post("/api/brain/sources/grants", json={"path": str(_folder(ws))}, headers=h).json()
    return f"/api/brain/sources/grants?root_id={granted['root_id']}"


def _knowledge_sources(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    client.post("/api/brain/sources/grants", json={"path": str(_folder(ws))}, headers=h)
    return "/api/knowledge-sources"


def _revoke_knowledge_source(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    granted = client.post("/api/brain/sources/grants", json={"path": str(_folder(ws))}, headers=h).json()
    return f"/api/knowledge-sources?kind=granted_folder&source_id={granted['root_id']}"


CASES: Cases = {
    ("GET", "/api/memory/proposals"): _proposals,
    ("POST", "/api/memory/proposals/{candidate_id}/decision"): _proposal_decision,
    ("GET", "/api/memory/relationship-proposals"): _relationships("relationship-proposals"),
    ("GET", "/api/memory/entity-proposals"): _relationships("entity-proposals"),
    ("POST", "/api/memory/relationship-proposals/scan"): _scan("relationship-proposals"),
    ("POST", "/api/memory/entity-proposals/scan"): _scan("entity-proposals"),
    ("POST", "/api/memory/relationship-proposals/{candidate_id}/decision"): _relationship_decision(
        "relationship-proposals"
    ),
    ("POST", "/api/memory/entity-proposals/{candidate_id}/decision"): _relationship_decision(
        "entity-proposals"
    ),
    ("POST", "/api/memory/entity-relationships/{relationship_id}/reject"): _relationship_reject,
    ("PUT", "/api/memory/{memory_id}/pin"): _on_memory("/pin", {"pinned": True}),
    ("GET", "/api/memory/export"): _export,
    ("POST", "/api/memory/import/preview"): plain("/api/memory/import/preview", IMPORTED),
    ("POST", "/api/memory/import"): plain("/api/memory/import", IMPORTED),
    ("POST", "/api/memory/reconcile"): plain("/api/memory/reconcile"),
    ("GET", "/api/memory/integrity"): plain("/api/memory/integrity"),
    ("POST", "/api/memory/conversation-index/rebuild"): plain("/api/memory/conversation-index/rebuild"),
    ("GET", "/api/memory/observations"): _observations,
    ("POST", "/api/memory/observations/delete"): _delete_observations,
    ("POST", "/api/memory/gists/{gist_id}/discard"): _gist,
    ("POST", "/api/memory/eidetic/cleanup"): _cleanup,
    ("PUT", "/api/memory/incognito"): plain("/api/memory/incognito", {"incognito": True}),
    ("PUT", "/api/memory/embedding-backend"): plain(
        "/api/memory/embedding-backend", {"embedding_backend": "auto"}
    ),
    ("POST", "/api/memory/embedding-index"): patched(_embedding_index, _fake_embedder),
    ("DELETE", "/api/memory/{memory_id}"): _on_memory(""),
    ("GET", "/api/memory/{memory_id}/source"): _on_memory("/source"),
    ("GET", "/api/memory/{memory_id}/history"): _on_memory("/history"),
    ("PUT", "/api/memory/{memory_id}/scope"): _scope,
    ("PUT", "/api/memory/{memory_id}/archive"): _on_memory("/archive", {"archived": True}),
    ("GET", "/api/memory/{memory_id}/purge-preview"): _on_memory("/purge-preview"),
    ("DELETE", "/api/memory/{memory_id}/purge"): _on_memory("/purge", None, method_headers=True),
    ("PUT", "/api/memory/{memory_id}"): _on_memory("", {"text": "Rahul uses Rust."}),
    ("POST", "/api/memory/{memory_id}/correct"): _on_memory(
        "/correct", {"text": "Rahul uses Go.", "reason": "contract"}
    ),
    ("PUT", "/api/memory/{memory_id}/search"): _on_memory("/search", {"enabled": False}),
    ("PUT", "/api/memory/{memory_id}/expiry"): _on_memory("/expiry", {"expires_at": None}),
    ("GET", "/api/brain"): plain("/api/brain"),
    ("GET", "/api/brain/settings"): plain("/api/brain/settings"),
    ("PUT", "/api/brain/settings"): plain("/api/brain/settings", {"settings": {"layout": "radial"}}),
    ("POST", "/api/brain/sources"): _brain_source,
    ("DELETE", "/api/brain/sources"): _brain_source_removed,
    ("GET", "/api/brain/sources/browse"): _brain_browse,
    ("GET", "/api/brain/sources/roots"): plain("/api/brain/sources/roots"),
    ("POST", "/api/brain/sources/grants"): _grant,
    ("DELETE", "/api/brain/sources/grants"): _revoke_grant,
    ("POST", "/api/brain/sources/upload"): lambda ws, c, h: (
        "/api/brain/sources/upload",
        {"filename": "n.md", "content_base64": base64.b64encode(b"# N").decode(), "store_copy": True},
    ),
    ("POST", "/api/brain/sources/review"): _brain_review,
    ("GET", "/api/knowledge-sources"): _knowledge_sources,
    ("DELETE", "/api/knowledge-sources"): _revoke_knowledge_source,
}
