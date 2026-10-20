"""BUG-348 — the second Design round: components, notes, owner imports, vector PDF, receipts.

* A component is a named layer tree in the document; an instance is a group
  linked to it, updated from it only when the owner asks, and a broken link is
  a failed check (DW-06, DW-10).
* A note on a layer or frame is a typed, versioned change (DW-08) and rides a
  Build handoff while open.
* The owner's own picture is stored as an ``import`` asset with no provider;
  its palette and a tokens file are read here and propose, never save (DW-04,
  DW-06).
* A vector PDF keeps text as text and records what it could not encode (DW-11).
* A proposal's receipt exists before the model call; one the host did not
  survive reads as outcome unknown, and a failed call as failed (DW-12).
"""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfReader

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.design import store as design_store
from raiker.design.document import DesignError, apply_operations, blank_document, validate_document
from raiker.design.imports import extract_palette, parse_tokens
from raiker.design.pdf import render_pdf
from raiker.design.validation import validate
from raiker.models.contracts import ModelResponse
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def api(tmp_path: Path) -> tuple[TestClient, dict[str, str], Path]:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    client = TestClient(create_app(tmp_path))
    token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
    return client, {"Authorization": f"Bearer {token}"}, tmp_path


def _card() -> list[dict[str, Any]]:
    return [
        {"op": "add_node", "frame_id": "frame-1", "node": {"id": "bg", "type": "rect", "x": 100, "y": 100, "w": 200,
                                                           "h": 80, "fill": "#1144aa"}},
        {"op": "add_node", "frame_id": "frame-1", "node": {"id": "label", "type": "text", "x": 110, "y": 110,
                                                           "w": 180, "h": 60, "text": "Buy", "color": "#ffffff"}},
        {"op": "group_nodes", "node_ids": ["bg", "label"], "group_id": "button", "name": "Button"},
    ]


def _png(color: tuple[int, int, int, int] = (17, 68, 170, 255), size: tuple[int, int] = (40, 20)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


# ── Components ──────────────────────────────────────────────────────────


def test_a_component_is_placed_as_linked_ordinary_layers_and_updated_only_on_request() -> None:
    doc, _t, _s = apply_operations(blank_document(), _card(), actor="owner")
    doc, touched, _s = apply_operations(doc, [{"op": "define_component", "component_id": "cta", "node_id": "button"}],
                                        actor="owner")
    assert touched == {"cta"} and doc["components"]["cta"]["name"] == "Button"
    assert doc["components"]["cta"]["nodes"][0]["x"] == 0  # drawn from the origin
    doc, _t, _s = apply_operations(doc, [{"op": "place_component", "component_id": "cta", "frame_id": "frame-1",
                                          "node_id": "cta-1", "x": 500, "y": 600}], actor="owner")
    instance = doc["frames"][0]["nodes"][-1]
    assert instance["component_id"] == "cta" and (instance["x"], instance["y"]) == (500, 600)
    label = next(n for n in instance["children"][0]["children"] if n["type"] == "text")
    # Editing an instance is an ordinary edit; the component does not follow it.
    doc, _t, _s = apply_operations(doc, [{"op": "update_node", "node_id": label["id"], "set": {"text": "Now"}}],
                                   actor="owner")
    assert doc["components"]["cta"]["nodes"][0]["children"][1]["text"] == "Buy"
    doc, _t, _s = apply_operations(doc, [{"op": "update_instance", "node_id": "cta-1"}], actor="owner")
    again = doc["frames"][0]["nodes"][-1]
    assert (again["x"], again["y"]) == (500, 600)
    assert next(n for n in again["children"][0]["children"] if n["type"] == "text")["text"] == "Buy"
    assert validate_document(doc)["components"]["cta"]["name"] == "Button"


def test_a_broken_component_link_is_a_failed_check_and_instances_keep_their_layers() -> None:
    doc, _t, _s = apply_operations(blank_document(), [
        *_card(), {"op": "define_component", "component_id": "cta", "node_id": "button"},
        {"op": "place_component", "component_id": "cta", "frame_id": "frame-1", "node_id": "cta-1", "x": 0, "y": 0},
    ], actor="owner")
    ok = validate(doc, asset_state=lambda _a: "ok", variables=None)
    assert next(c for c in ok["checks"] if c["check"] == "components")["status"] == "pass"
    doc, _t, _s = apply_operations(doc, [{"op": "remove_component", "component_id": "cta"}], actor="owner")
    assert "components" not in doc and doc["frames"][0]["nodes"][-1]["children"]
    broken = validate(doc, asset_state=lambda _a: "ok", variables=None)
    check = next(c for c in broken["checks"] if c["check"] == "components")
    assert check["status"] == "fail" and check["findings"][0]["node_id"] == "cta-1"
    with pytest.raises(DesignError, match="unknown_component"):
        apply_operations(doc, [{"op": "update_instance", "node_id": "cta-1"}], actor="owner")


# ── Notes ───────────────────────────────────────────────────────────────


def test_notes_are_versioned_changes_on_real_targets(api: Any) -> None:
    client, h, _ws = api
    doc = client.post("/api/design/documents", json={"title": "Notes"}, headers=h).json()
    did = doc["document_id"]

    def ops(base: int, operations: list[dict[str, Any]]) -> Any:
        return client.post(f"/api/design/documents/{did}/operations",
                           json={"base_version": base, "operations": operations}, headers=h)

    ops(1, _card())
    missing = ops(2, [{"op": "add_note", "note": {"id": "n1", "target": "nope", "text": "Hi"}}])
    assert missing.json()["detail"]["reason_code"].startswith("unknown_note_target")
    added = ops(2, [{"op": "add_note", "note": {"id": "n1", "target": "label", "text": "Make this “Buy now”"}}]).json()
    assert added["version"] == 3 and added["document"]["document"]["notes"][0]["author"] == "owner"
    versions = client.get(f"/api/design/documents/{did}/versions", headers=h).json()["versions"]
    assert versions[0]["scope"] == ["n1"]
    handoff = client.post(f"/api/design/documents/{did}/handoff", json={"frame_ids": ["frame-1"]}, headers=h).json()
    text = SQLiteStore(_ws).load_attachment(handoff["attachment_id"])["data"].decode()  # type: ignore[index]
    assert "Open notes" in text and "Buy now" in text
    resolved = ops(3, [{"op": "update_note", "note_id": "n1", "set": {"resolved": True}}]).json()
    assert resolved["document"]["document"]["notes"][0]["resolved"] is True
    undone = client.post(f"/api/design/documents/{did}/undo", json={"base_version": 4}, headers=h).json()
    assert undone["document"]["document"]["notes"][0]["resolved"] is False
    gone = ops(5, [{"op": "remove_note", "note_id": "n1"}]).json()
    assert "notes" not in gone["document"]["document"]


# ── Owner imports ───────────────────────────────────────────────────────


def test_the_owners_picture_is_an_import_asset_with_no_provider(api: Any) -> None:
    client, h, ws = api
    body = {"filename": "logo.png", "media_type": "image/png", "data_base64": base64.b64encode(_png()).decode()}
    made = client.post("/api/design/assets/import", json=body, headers=h).json()["generation"]
    assert made["kind"] == "import" and made["provider"] == "owner" and made["model"] == ""
    assert made["size"] == "40x20" and made["has_image"]
    with SQLiteStore(ws).connect() as connection:
        audited = connection.execute(
            "SELECT COUNT(*) FROM events_index WHERE event_type = 'design_asset_imported'"
        ).fetchone()[0]
    assert audited == 1
    gallery = client.get("/api/images", headers=h).json()["generations"]
    assert gallery[0]["generation_id"] == made["generation_id"]
    assert client.get(f"/api/images/{made['generation_id']}/bytes", headers=h).content == _png()
    lying = {**body, "media_type": "image/jpeg"}
    refused = client.post("/api/design/assets/import", json=lying, headers=h)
    assert refused.status_code == 400 and refused.json()["detail"]["reason_code"] == "content_does_not_match_media_type"
    palette = client.get(f"/api/design/assets/{made['generation_id']}/palette", headers=h).json()
    assert palette["colors"][0] == {"color": "#1144aa", "share": 1.0}
    assert client.get("/api/design/assets/img_nope/palette", headers=h).status_code == 404


def test_a_palette_ignores_transparent_pixels() -> None:
    image = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    for x in range(5):
        image.putpixel((x, 0), (255, 0, 0, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    assert extract_palette(buffer.getvalue()) == [{"color": "#ff0000", "share": 1.0}]


def test_tokens_from_css_and_json_are_placed_or_skipped_with_a_reason() -> None:
    css = parse_tokens("tokens.css", """
        :root { --color-primary: #14a; --ink: #111111; --font-body: "Inter", sans-serif;
                --space-md: 16px; --radius-lg: 1rem; --shadow: 0 1px 2px black; --alias: var(--ink); }
    """)
    assert css["variables"]["colors"] == {"primary": "#1144aa", "ink": "#111111"}
    assert css["variables"]["fonts"] == {"body": "Inter"}
    assert css["variables"]["spacing"] == {"md": 16.0, "radius-lg": 16.0}
    assert {item["name"]: item["reason"] for item in css["skipped"]} == {
        "shadow": "not a colour, font or size", "alias": "refers to another variable",
    }
    dtcg = parse_tokens("tokens.json", json.dumps({
        "color": {"brand": {"$value": "#FF6600", "$type": "color"}, "bad": {"$value": "orange", "$type": "color"}},
        "font": {"heading": {"$value": "Georgia", "$type": "fontFamily"}},
    }))
    assert dtcg["format"] == "json" and dtcg["variables"]["colors"] == {"brand": "#ff6600"}
    assert dtcg["variables"]["fonts"] == {"heading": "Georgia"}
    assert dtcg["skipped"] == [{"name": "color-bad", "reason": "colour is not #rgb, #rrggbb or #rrggbbaa"}]
    assert parse_tokens("x.json", "{nope")["skipped"][0]["reason"] == "not valid JSON"


def test_reading_tokens_writes_no_system(api: Any) -> None:
    client, h, _ws = api
    read = client.post("/api/design/systems/tokens",
                       json={"filename": "brand.css", "text": ":root{--brand:#1144aa}"}, headers=h).json()
    assert read["found"] == 1 and len(read["sha256"]) == 64
    assert client.get("/api/design/systems", headers=h).json()["systems"] == []


# ── Vector PDF ──────────────────────────────────────────────────────────


def test_a_vector_pdf_keeps_text_as_text_and_counts_what_it_could_not_encode(api: Any) -> None:
    doc, _t, _s = apply_operations(blank_document("document_a4"), [
        *_card(),
        {"op": "add_node", "frame_id": "frame-1", "node": {"id": "t", "type": "text", "x": 50, "y": 400, "w": 600,
                                                           "h": 60, "text": "Café — ✓", "font_size": 24}},
    ], actor="owner")
    data, settings = render_pdf(doc, "frame-1", lambda _a: None)
    reader = PdfReader(io.BytesIO(data))
    page = reader.pages[0]
    assert [round(float(v)) for v in page.mediabox[2:]] == [596, 842]
    assert "Café —" in page.extract_text() and "Buy" in page.extract_text()
    assert settings["characters_replaced"] == 1 and settings["text_encoding"] == "windows-1252"

    client, h, _ws = api
    made = client.post("/api/design/documents", json={"title": "PDF"}, headers=h).json()
    client.post(f"/api/design/documents/{made['document_id']}/operations",
                json={"base_version": 1, "operations": _card()}, headers=h)
    exported = client.post(f"/api/design/documents/{made['document_id']}/exports",
                           json={"frame_id": "frame-1", "format": "vector_pdf"}, headers=h).json()
    assert exported["media_type"] == "application/pdf" and exported["settings"]["pdf_pages"] == "vector"
    download = client.get(f"/api/design/exports/{exported['export_id']}/bytes", headers=h)
    assert download.content.startswith(b"%PDF-1.4") and ".pdf\"" in download.headers["content-disposition"]


# ── Receipts ────────────────────────────────────────────────────────────


CHOICE = {"model_profile": "anthropic-hosted", "model": "claude-haiku-5-5"}


def test_a_failed_call_is_recorded_and_an_interrupted_one_reads_as_outcome_unknown(api: Any, monkeypatch: Any) -> None:
    from raiker.models.router import ModelRouter

    client, h, ws = api
    doc = client.post("/api/design/documents", json={"title": "Receipts"}, headers=h).json()

    async def unreadable(self: Any, *args: Any, **kwargs: Any) -> ModelResponse:
        return ModelResponse(text="no json here")

    monkeypatch.setattr(ModelRouter, "achat", unreadable)
    response = client.post(f"/api/design/documents/{doc['document_id']}/proposals",
                           json={"frame_id": "frame-1", "brief": "Nicer", **CHOICE}, headers=h)
    assert response.status_code == 502
    listed = client.get(f"/api/design/documents/{doc['document_id']}/proposals", headers=h).json()["proposals"]
    assert listed[0]["status"] == "failed" and listed[0]["result"] == {"reason_code": "design_proposal_unreadable"}

    owner = SQLiteStore(ws)
    interrupted = design_store.start_proposal(
        owner, owner="principal_owner", document_id=doc["document_id"], base_version=1, frame_id="frame-1",
        brief="Lost", provider="anthropic-hosted", model="claude-haiku-5-5",
    )
    assert design_store.get_proposal(owner, owner="principal_owner", proposal_id=interrupted)["status"] == "requesting"  # type: ignore[index]
    monkeypatch.setattr(design_store, "HOST_RUN", "a-later-host-run")
    seen = design_store.get_proposal(owner, owner="principal_owner", proposal_id=interrupted)
    assert seen is not None and seen["status"] == "outcome_unknown"
    # Never decidable: nothing is known about what the provider answered.
    decided = client.post(f"/api/design/proposals/{interrupted}/decision", json={"decision": "accept"}, headers=h)
    assert decided.status_code == 409
