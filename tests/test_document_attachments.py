"""Web-app task 3 (uploaded-documents slice) — governed text-document attachments.

Uploaded bytes are untrusted data behind fail-closed validation: media-type
allowlist (text/plain, text/markdown, text/csv), a hard size cap, and a
UTF-8/NUL sniff that the bytes really are clean text (a binary file mislabelled
as text fails closed). A stored document's extracted text reaches a model as a
bounded, ``untrusted_external`` context item — document content is data, never
instructions. PDF/office binaries are intentionally out of scope for this slice.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.context.gatherer import ContextGatherer
from raiker.runtime.attachments import (
    MAX_DOCUMENT_BYTES,
    MAX_DOCUMENT_TEXT_CHARS,
    AttachmentValidationError,
    extract_document_text,
    load_document,
    store_document,
    validate_document,
)
from raiker.storage.sqlite import SQLiteStore

TXT_BYTES = b"hello raiker\nthis is a plain text document.\n"
CSV_BYTES = b"name,role\nrahul,owner\nclaude,builder\n"
MD_BYTES = b"# Title\n\nSome **markdown** body text.\n"


# ── validation ──────────────────────────────────────────────────────────────


class TestDocumentValidation:
    def test_valid_plain_text_passes(self) -> None:
        validate_document("text/plain", TXT_BYTES)

    def test_valid_csv_passes(self) -> None:
        validate_document("text/csv", CSV_BYTES)

    def test_valid_markdown_passes(self) -> None:
        validate_document("text/markdown", MD_BYTES)

    def test_unsupported_media_type_fails_closed(self) -> None:
        with pytest.raises(AttachmentValidationError, match="unsupported_media_type"):
            validate_document("application/pdf", TXT_BYTES)

    def test_image_media_type_not_accepted_as_document(self) -> None:
        with pytest.raises(AttachmentValidationError, match="unsupported_media_type"):
            validate_document("image/png", TXT_BYTES)

    def test_empty_fails_closed(self) -> None:
        with pytest.raises(AttachmentValidationError, match="empty_attachment"):
            validate_document("text/plain", b"")

    def test_oversize_fails_closed(self) -> None:
        oversized = b"a" * (MAX_DOCUMENT_BYTES + 1)
        with pytest.raises(AttachmentValidationError, match="attachment_too_large"):
            validate_document("text/plain", oversized)

    def test_nul_byte_fails_closed(self) -> None:
        # A binary file mislabelled as text/plain must fail closed.
        with pytest.raises(AttachmentValidationError, match="content_does_not_match_media_type"):
            validate_document("text/plain", b"text\x00binary")

    def test_invalid_utf8_fails_closed(self) -> None:
        with pytest.raises(AttachmentValidationError, match="content_does_not_match_media_type"):
            validate_document("text/plain", b"\xff\xfe not utf-8")


# ── extraction bounds ───────────────────────────────────────────────────────


class TestDocumentExtraction:
    def test_extract_returns_text(self) -> None:
        assert extract_document_text("text/plain", TXT_BYTES) == TXT_BYTES.decode()

    def test_extract_is_bounded(self) -> None:
        big = ("x" * (MAX_DOCUMENT_TEXT_CHARS + 5000)).encode()
        extracted = extract_document_text("text/plain", big)
        assert len(extracted) == MAX_DOCUMENT_TEXT_CHARS


# ── store / load round-trip ─────────────────────────────────────────────────


class TestDocumentStore:
    def test_store_and_load_roundtrip(self, tmp_path: Path) -> None:
        store = SQLiteStore(tmp_path)
        stored = store_document(
            store, filename="notes.txt", media_type="text/plain", data=TXT_BYTES
        )
        assert stored.attachment_id.startswith("att_")
        assert stored.kind == "document"
        assert stored.byte_size == len(TXT_BYTES)
        record = load_document(store, stored.attachment_id)
        assert record is not None
        assert record["extracted_text"] == TXT_BYTES.decode()
        assert record["extract_truncated"] is False

    def test_metadata_load_never_carries_bytes(self, tmp_path: Path) -> None:
        store = SQLiteStore(tmp_path)
        stored = store_document(
            store, filename="notes.txt", media_type="text/plain", data=TXT_BYTES
        )
        metadata = store.load_attachment_metadata(stored.attachment_id)
        assert metadata is not None
        assert "data" not in metadata
        assert metadata["kind"] == "document"

    def test_unknown_document_loads_none(self, tmp_path: Path) -> None:
        assert load_document(SQLiteStore(tmp_path), "att_missing") is None

    def test_image_record_not_loaded_as_document(self, tmp_path: Path) -> None:
        # A record stored under a different kind must not resolve as a document.
        store = SQLiteStore(tmp_path)
        store.save_attachment(
            attachment_id="att_img",
            kind="image",
            filename="a.png",
            media_type="image/png",
            sha256="x",
            data=b"\x89PNG\r\n\x1a\n",
        )
        assert load_document(store, "att_img") is None

    def test_invalid_upload_never_stored(self, tmp_path: Path) -> None:
        store = SQLiteStore(tmp_path)
        with pytest.raises(AttachmentValidationError):
            store_document(store, filename="x.txt", media_type="text/plain", data=b"a\x00b")


# ── context gathering (bounded, untrusted text) ─────────────────────────────


class TestDocumentAttachmentGathering:
    def test_uploaded_document_becomes_untrusted_text_item(self, tmp_path: Path) -> None:
        store = SQLiteStore(tmp_path)
        stored = store_document(
            store, filename="notes.txt", media_type="text/plain", data=TXT_BYTES
        )
        bundle = ContextGatherer().gather(
            workspace_root=tmp_path, session_id="s", turn_id="t", prompt_text="hi",
            attachments=[{"type": "document", "attachment_id": stored.attachment_id}],
        )
        items = [i for i in bundle.items if i.source.source_type == "attachment"]
        assert len(items) == 1
        item = items[0]
        assert item.source.trust_level == "untrusted_external"
        assert item.metadata["attachment_status"] == "document_uploaded"
        assert item.metadata["kind"] == "document"
        assert "plain text document" in item.content
        # The item announces the content as untrusted data, never instructions.
        assert "untrusted document content" in item.content

    def test_unknown_document_reported_honestly(self, tmp_path: Path) -> None:
        bundle = ContextGatherer().gather(
            workspace_root=tmp_path, session_id="s", turn_id="t", prompt_text="hi",
            attachments=[{"type": "document", "attachment_id": "att_missing"}],
        )
        item = [i for i in bundle.items if i.source.source_type == "attachment"][0]
        assert item.metadata["attachment_status"] == "not_found"

    def test_missing_attachment_id_reported_honestly(self, tmp_path: Path) -> None:
        bundle = ContextGatherer().gather(
            workspace_root=tmp_path, session_id="s", turn_id="t", prompt_text="hi",
            attachments=[{"type": "document"}],
        )
        item = [i for i in bundle.items if i.source.source_type == "attachment"][0]
        assert item.metadata["attachment_status"] == "missing_attachment_id"


# ── upload API ──────────────────────────────────────────────────────────────


class TestUploadApi:
    @pytest.fixture
    def workspace(self, tmp_path: Path) -> Path:
        ws = tmp_path / "ws"
        ws.mkdir()
        return ws

    @pytest.fixture
    def client(self, workspace: Path) -> TestClient:
        bootstrap_owner("rahul", "Rahul", workspace_root=workspace)
        app: FastAPI = create_app(workspace)
        return TestClient(app)

    @pytest.fixture
    def owner_token(self, workspace: Path) -> str:
        raw, _ = ApiSessionStore(workspace).create_session("principal_rahul")
        return raw

    def _upload(self, client: TestClient, token: str, **overrides: str) -> Any:
        body = {
            "filename": "notes.txt",
            "media_type": "text/plain",
            "data_base64": base64.b64encode(TXT_BYTES).decode(),
            **overrides,
        }
        return client.post(
            "/api/attachments", json=body, headers={"Authorization": f"Bearer {token}"}
        )

    def test_upload_document_returns_metadata_only(
        self, client: TestClient, owner_token: str, workspace: Path
    ) -> None:
        resp = self._upload(client, owner_token)
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["kind"] == "document"
        assert body["attachment_id"].startswith("att_")
        assert "data" not in body and "data_base64" not in body
        assert load_document(SQLiteStore(workspace), body["attachment_id"]) is not None

    def test_upload_rejects_unsupported_media_type(
        self, client: TestClient, owner_token: str
    ) -> None:
        resp = self._upload(client, owner_token, media_type="application/pdf")
        assert resp.status_code == 400
        assert "unsupported_media_type" in json.dumps(resp.json())

    def test_upload_rejects_binary_mislabelled_as_text(
        self, client: TestClient, owner_token: str
    ) -> None:
        resp = self._upload(
            client, owner_token, data_base64=base64.b64encode(b"a\x00b").decode()
        )
        assert resp.status_code == 400
        assert "content_does_not_match_media_type" in json.dumps(resp.json())

    def test_prompt_accepts_document_attachment_reference(
        self, client: TestClient, owner_token: str
    ) -> None:
        upload = self._upload(client, owner_token)
        attachment_id = upload.json()["attachment_id"]
        resp = client.post(
            "/api/prompts",
            json={
                "text": "summarize",
                "attachments": [{"type": "document", "attachment_id": attachment_id}],
            },
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert resp.status_code == 200
        assert "Invalid prompt" not in resp.json().get("message", "")
