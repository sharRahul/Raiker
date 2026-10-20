"""Raiker Design's structured documents (DW-01 to DW-11): documents, versions, systems,
validation, exports, proposals and handoffs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from tests.contract_cases.base import Call, Cases, Seed, patched, plain

_TEXT = {"op": "add_node", "frame_id": "frame-1",
         "node": {"id": "title", "type": "text", "x": 40, "y": 40, "w": 600, "h": 80, "text": "Launch"}}


def _document(client: TestClient, h: dict[str, str]) -> str:
    """A document with one edit on it, so it has a version to undo, compare and restore."""
    doc = client.post("/api/design/documents", json={"title": "Contract"}, headers=h).json()
    client.post(f"/api/design/documents/{doc['document_id']}/operations",
                json={"base_version": 1, "operations": [_TEXT]}, headers=h)
    return str(doc["document_id"])


def _on_doc(build: Any) -> Seed:
    def seed(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
        return build(_document(client, h), client, h)  # type: ignore[no-any-return]

    return seed


def _system(client: TestClient, h: dict[str, str]) -> str:
    body = {"name": "Brand", "variables": {"colors": {"ink": "#111111"}}}
    return str(client.post("/api/design/systems", json=body, headers=h).json()["system_id"])


def _scripted_proposal(monkeypatch: Any) -> None:
    from raiker.models.contracts import ModelResponse
    from raiker.models.router import ModelRouter

    async def achat(self: Any, *args: Any, **kwargs: Any) -> ModelResponse:
        return ModelResponse(
            text='{"plan": {"summary": "Bigger title"}, "operations": '
            '[{"op": "update_node", "node_id": "title", "set": {"font_size": 64}}]}'
        )

    monkeypatch.setattr(ModelRouter, "achat", achat)


_CHOICE = {"model_profile": "anthropic-hosted", "model": "claude-haiku-5-5"}


def _proposal(decide: bool) -> Seed:
    def seed(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
        doc = _document(client, h)
        body = {"frame_id": "frame-1", "brief": "Bigger title", **_CHOICE}
        if not decide:
            return f"/api/design/documents/{doc}/proposals", body
        made = client.post(f"/api/design/documents/{doc}/proposals", json=body, headers=h).json()
        return f"/api/design/proposals/{made['proposal_id']}/decision", {"decision": "accept"}

    return patched(seed, _scripted_proposal)


def _listing(suffix: str, make: str | None = None, body: Any = None) -> Seed:
    """A list route on a document that already has one of what it lists."""

    def build(doc: str, client: TestClient, h: dict[str, str]) -> Call:
        if make is not None:
            client.post(f"/api/design/documents/{doc}/{make}", json=body, headers=h)
        return f"/api/design/documents/{doc}/{suffix}"

    return _on_doc(build)


def _deleted(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    doc = _document(client, h)
    client.delete(f"/api/design/documents/{doc}", headers=h)
    return f"/api/design/documents/{doc}/restore"


def _listed(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    _deleted(_ws, client, h)
    _document(client, h)
    return "/api/design/documents"


_EXPORT = {"frame_id": "frame-1", "format": "svg"}


def _png_base64() -> str:
    import base64
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), (17, 68, 170)).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


_IMPORT = {"filename": "logo.png", "media_type": "image/png", "data_base64": _png_base64()}


def _imported(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    made = client.post("/api/design/assets/import", json=_IMPORT, headers=h).json()
    return f"/api/design/assets/{made['generation']['generation_id']}/palette"

CASES: Cases = {
    ("GET", "/api/design/documents"): _listed,
    ("POST", "/api/design/documents"): plain("/api/design/documents", {"title": "New", "preset": "mobile"}),
    ("GET", "/api/design/documents/{document_id}"): _on_doc(lambda doc, c, h: f"/api/design/documents/{doc}"),
    ("PATCH", "/api/design/documents/{document_id}"): _on_doc(
        lambda doc, c, h: (f"/api/design/documents/{doc}", {"title": "Renamed"})
    ),
    ("DELETE", "/api/design/documents/{document_id}"): _on_doc(lambda doc, c, h: f"/api/design/documents/{doc}"),
    ("POST", "/api/design/documents/{document_id}/restore"): _deleted,
    ("POST", "/api/design/documents/{document_id}/operations"): _on_doc(
        lambda doc, c, h: (f"/api/design/documents/{doc}/operations", {
            "base_version": 2, "operations": [{"op": "update_node", "node_id": "title", "set": {"text": "Now"}}],
        })
    ),
    ("GET", "/api/design/documents/{document_id}/versions"): _listing("versions"),
    ("GET", "/api/design/documents/{document_id}/versions/{version}"): _listing("versions/1"),
    ("POST", "/api/design/documents/{document_id}/undo"): _on_doc(
        lambda doc, c, h: (f"/api/design/documents/{doc}/undo", {"base_version": 2})
    ),
    ("POST", "/api/design/documents/{document_id}/redo"): _on_doc(
        lambda doc, c, h: (
            c.post(f"/api/design/documents/{doc}/undo", json={"base_version": 2}, headers=h)
            and f"/api/design/documents/{doc}/redo",
            {"base_version": 3},
        )
    ),
    ("POST", "/api/design/documents/{document_id}/versions/{version}/restore"): _on_doc(
        lambda doc, c, h: (f"/api/design/documents/{doc}/versions/1/restore", {"base_version": 2})
    ),
    ("GET", "/api/design/systems"): lambda ws, c, h: (_system(c, h) and "/api/design/systems"),
    ("POST", "/api/design/systems"): plain(
        "/api/design/systems", {"name": "Acme", "variables": {"colors": {"brand": "#1144aa"}}}
    ),
    ("PUT", "/api/design/systems/{system_id}"): lambda ws, c, h: (
        f"/api/design/systems/{_system(c, h)}", {"name": "Brand", "variables": {"colors": {"ink": "#000000"}}}
    ),
    ("POST", "/api/design/documents/{document_id}/system/preview"): _on_doc(
        lambda doc, c, h: (f"/api/design/documents/{doc}/system/preview", {"system_id": _system(c, h)})
    ),
    ("POST", "/api/design/documents/{document_id}/system"): _on_doc(
        lambda doc, c, h: (f"/api/design/documents/{doc}/system", {"system_id": _system(c, h), "base_version": 2})
    ),
    ("GET", "/api/design/assets/{asset_id}/usage"): plain("/api/design/assets/img_contract/usage"),
    ("POST", "/api/design/assets/import"): plain("/api/design/assets/import", _IMPORT),
    ("GET", "/api/design/assets/{asset_id}/palette"): _imported,
    ("POST", "/api/design/systems/tokens"): plain(
        "/api/design/systems/tokens", {"filename": "tokens.css", "text": ":root { --brand: #1144aa; --gap: 8px; }"}
    ),
    ("GET", "/api/design/documents/{document_id}/validation"): _listing("validation"),
    ("POST", "/api/design/documents/{document_id}/exports"): _on_doc(
        lambda doc, c, h: (f"/api/design/documents/{doc}/exports", _EXPORT)
    ),
    ("GET", "/api/design/documents/{document_id}/exports"): _listing("exports", "exports", _EXPORT),
    ("POST", "/api/design/documents/{document_id}/proposals"): _proposal(decide=False),
    ("GET", "/api/design/documents/{document_id}/proposals"): patched(
        _on_doc(lambda doc, c, h: (
            c.post(f"/api/design/documents/{doc}/proposals",
                   json={"frame_id": "frame-1", "brief": "Bigger", **_CHOICE}, headers=h)
            and f"/api/design/documents/{doc}/proposals"
        )),
        _scripted_proposal,
    ),
    ("POST", "/api/design/proposals/{proposal_id}/decision"): _proposal(decide=True),
    ("POST", "/api/design/documents/{document_id}/handoff"): _on_doc(
        lambda doc, c, h: (f"/api/design/documents/{doc}/handoff", {"frame_ids": ["frame-1"], "target": "web"})
    ),
    ("GET", "/api/design/documents/{document_id}/handoffs"): _listing(
        "handoffs", "handoff", {"frame_ids": ["frame-1"]}
    ),
}
