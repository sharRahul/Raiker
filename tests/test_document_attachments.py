"""Web-app task 3 (uploaded-documents slice) — governed document attachments.

Uploaded bytes are untrusted data behind fail-closed, per-type validation:
media-type allowlist, a hard size cap (32 MB, matching Claude's document limit),
and a type-specific sniff — clean UTF-8 (no NUL) for text, a ``%PDF-`` header
pypdf can parse for PDF, a well-formed OOXML zip for .docx and .xlsx. Extraction
is local-only (decode / pypdf / stdlib zip+XML), and the bounded extracted text
reaches a model as an ``untrusted_external`` context item — document content is
data, never instructions.
"""

from __future__ import annotations

import base64
import io
import json
import zipfile
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
    DOCX_MEDIA_TYPE,
    MAX_DOCUMENT_BYTES,
    MAX_DOCUMENT_TEXT_CHARS,
    PDF_MEDIA_TYPE,
    XLSX_MEDIA_TYPE,
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


def make_pdf(text: str) -> bytes:
    """A minimal, valid single-page PDF whose content stream draws ``text``."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    ]
    stream = b"BT /F1 24 Tf 72 720 Td (" + text.encode("latin-1") + b") Tj ET"
    objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    pdf = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += str(i).encode() + b" 0 obj\n" + obj + b"\nendobj\n"
    xref_pos = len(pdf)
    pdf += b"xref\n0 " + str(len(objects) + 1).encode() + b"\n0000000000 65535 f \n"
    for off in offsets:
        pdf += f"{off:010d} 00000 n \n".encode()
    pdf += b"trailer\n<< /Size " + str(len(objects) + 1).encode() + b" /Root 1 0 R >>\n"
    pdf += b"startxref\n" + str(xref_pos).encode() + b"\n%%EOF"
    return bytes(pdf)


def make_docx(text: str) -> bytes:
    """A minimal .docx (OOXML zip) whose body contains ``text``."""
    doc_xml = (
        '<?xml version="1.0"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>" + text + "</w:t></w:r></w:p></w:body>"
        "</w:document>"
    ).encode()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("word/document.xml", doc_xml)
    return buf.getvalue()


PDF_BYTES = make_pdf("Hello Raiker PDF")
DOCX_BYTES = make_docx("Hello Raiker DOCX")


# ── validation ──────────────────────────────────────────────────────────────


class TestDocumentValidation:
    def test_valid_plain_text_passes(self) -> None:
        validate_document("text/plain", TXT_BYTES)

    def test_valid_csv_passes(self) -> None:
        validate_document("text/csv", CSV_BYTES)

    def test_valid_markdown_passes(self) -> None:
        validate_document("text/markdown", MD_BYTES)

    def test_valid_pdf_passes(self) -> None:
        validate_document(PDF_MEDIA_TYPE, PDF_BYTES)

    def test_valid_docx_passes(self) -> None:
        validate_document(DOCX_MEDIA_TYPE, DOCX_BYTES)

    def test_unsupported_media_type_fails_closed(self) -> None:
        with pytest.raises(AttachmentValidationError, match="unsupported_media_type"):
            validate_document("application/x-msdownload", TXT_BYTES)

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

    def test_non_pdf_labelled_pdf_fails_closed(self) -> None:
        with pytest.raises(AttachmentValidationError, match="content_does_not_match_media_type"):
            validate_document(PDF_MEDIA_TYPE, b"not a pdf at all")

    def test_corrupt_pdf_fails_closed(self) -> None:
        # Right magic header, but the body is garbage — must fail closed, not
        # silently extract nothing.
        with pytest.raises(AttachmentValidationError):
            validate_document(PDF_MEDIA_TYPE, b"%PDF-1.4\ngarbage not a real pdf body")

    def test_non_zip_labelled_docx_fails_closed(self) -> None:
        with pytest.raises(AttachmentValidationError, match="content_does_not_match_media_type"):
            validate_document(DOCX_MEDIA_TYPE, b"not a zip package")

    def test_zip_without_document_xml_fails_closed(self) -> None:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as archive:
            archive.writestr("some/other.xml", b"<x/>")
        with pytest.raises(AttachmentValidationError, match="content_does_not_match_media_type"):
            validate_document(DOCX_MEDIA_TYPE, buf.getvalue())

    def test_docx_with_doctype_fails_closed(self) -> None:
        # A DOCTYPE is the only way to define the internal entities behind a
        # billion-laughs expansion; a real .docx never carries one.
        doc_xml = (
            b'<?xml version="1.0"?>'
            b'<!DOCTYPE w:document [<!ENTITY a "boom">]>'
            b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            b"<w:body><w:p><w:r><w:t>&a;</w:t></w:r></w:p></w:body></w:document>"
        )
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as archive:
            archive.writestr("word/document.xml", doc_xml)
        with pytest.raises(AttachmentValidationError, match="content_does_not_match_media_type"):
            validate_document(DOCX_MEDIA_TYPE, buf.getvalue())

    def test_docx_zip_bomb_fails_closed(self) -> None:
        # A small archive whose document.xml inflates past the decompressed cap
        # must be rejected instead of buffered whole (memory-exhaustion DoS).
        from raiker.runtime.attachments import MAX_DOCX_XML_BYTES

        bomb = b"<w:document>" + b" " * (MAX_DOCX_XML_BYTES + 1) + b"</w:document>"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("word/document.xml", bomb)
        payload = buf.getvalue()
        assert len(payload) <= MAX_DOCUMENT_BYTES  # compresses tiny; would inflate hugely
        with pytest.raises(AttachmentValidationError, match="docx_too_large"):
            validate_document(DOCX_MEDIA_TYPE, payload)

    def test_valid_xlsx_passes(self) -> None:
        from tests.test_attachment_preview import XLSX_BYTES

        validate_document(XLSX_MEDIA_TYPE, XLSX_BYTES)

    def test_non_zip_labelled_xlsx_fails_closed(self) -> None:
        with pytest.raises(AttachmentValidationError, match="content_does_not_match_media_type"):
            validate_document(XLSX_MEDIA_TYPE, b"not a zip package")

    def test_xlsx_without_a_worksheet_fails_closed(self) -> None:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as archive:
            archive.writestr("xl/workbook.xml", b"<workbook/>")
        with pytest.raises(AttachmentValidationError, match="content_does_not_match_media_type"):
            validate_document(XLSX_MEDIA_TYPE, buf.getvalue())

    def test_xlsx_with_doctype_fails_closed(self) -> None:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as archive:
            archive.writestr(
                "xl/workbook.xml",
                b'<!DOCTYPE workbook [<!ENTITY a "boom">]><workbook/>',
            )
            archive.writestr("xl/worksheets/sheet1.xml", b"<worksheet/>")
        with pytest.raises(AttachmentValidationError, match="content_does_not_match_media_type"):
            validate_document(XLSX_MEDIA_TYPE, buf.getvalue())

    def test_xlsx_zip_bomb_fails_closed(self) -> None:
        from raiker.runtime.attachments import MAX_XLSX_XML_BYTES

        bomb = b"<workbook>" + b" " * (MAX_XLSX_XML_BYTES + 1) + b"</workbook>"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("xl/workbook.xml", bomb)
            archive.writestr("xl/worksheets/sheet1.xml", b"<worksheet/>")
        with pytest.raises(AttachmentValidationError, match="xlsx_too_large"):
            validate_document(XLSX_MEDIA_TYPE, buf.getvalue())


# ── extraction bounds ───────────────────────────────────────────────────────


class TestDocumentExtraction:
    def test_extract_returns_text(self) -> None:
        assert extract_document_text("text/plain", TXT_BYTES) == TXT_BYTES.decode()

    def test_extract_is_bounded(self) -> None:
        big = ("x" * (MAX_DOCUMENT_TEXT_CHARS + 5000)).encode()
        extracted = extract_document_text("text/plain", big)
        assert len(extracted) == MAX_DOCUMENT_TEXT_CHARS

    def test_extract_pdf_text(self) -> None:
        assert "Hello Raiker PDF" in extract_document_text(PDF_MEDIA_TYPE, PDF_BYTES)

    def test_extract_docx_text(self) -> None:
        assert "Hello Raiker DOCX" in extract_document_text(DOCX_MEDIA_TYPE, DOCX_BYTES)

    def test_extract_xlsx_text(self) -> None:
        # Cell values become tab-separated lines, so a spreadsheet reaches
        # context as the same bounded untrusted text as every other document.
        from tests.test_attachment_preview import XLSX_BYTES

        text = extract_document_text(XLSX_MEDIA_TYPE, XLSX_BYTES)
        assert "Quarterly report\tOwner" in text
        assert "Revenue\t42" in text


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

    def test_store_and_load_pdf(self, tmp_path: Path) -> None:
        store = SQLiteStore(tmp_path)
        stored = store_document(
            store, filename="doc.pdf", media_type=PDF_MEDIA_TYPE, data=PDF_BYTES
        )
        assert stored.kind == "document"
        record = load_document(store, stored.attachment_id)
        assert record is not None
        assert "Hello Raiker PDF" in record["extracted_text"]

    def test_store_and_load_docx(self, tmp_path: Path) -> None:
        store = SQLiteStore(tmp_path)
        stored = store_document(
            store, filename="doc.docx", media_type=DOCX_MEDIA_TYPE, data=DOCX_BYTES
        )
        record = load_document(store, stored.attachment_id)
        assert record is not None
        assert "Hello Raiker DOCX" in record["extracted_text"]


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

    def test_uploaded_pdf_extracted_text_enters_context(self, tmp_path: Path) -> None:
        store = SQLiteStore(tmp_path)
        stored = store_document(
            store, filename="doc.pdf", media_type=PDF_MEDIA_TYPE, data=PDF_BYTES
        )
        bundle = ContextGatherer().gather(
            workspace_root=tmp_path, session_id="s", turn_id="t", prompt_text="hi",
            attachments=[{"type": "document", "attachment_id": stored.attachment_id}],
        )
        item = [i for i in bundle.items if i.source.source_type == "attachment"][0]
        assert item.source.trust_level == "untrusted_external"
        assert item.metadata["attachment_status"] == "document_uploaded"
        assert "Hello Raiker PDF" in item.content
        assert "untrusted document content" in item.content


# ── upload API ──────────────────────────────────────────────────────────────


class TestUploadApi:
    @pytest.fixture
    def workspace(self, tmp_path: Path) -> Path:
        ws = tmp_path / "ws"
        ws.mkdir()
        return ws

    @pytest.fixture
    def client(self, workspace: Path) -> TestClient:
        bootstrap_owner("owner", "Owner", workspace_root=workspace)
        app: FastAPI = create_app(workspace)
        return TestClient(app)

    @pytest.fixture
    def owner_token(self, workspace: Path) -> str:
        raw, _ = ApiSessionStore(workspace).create_session("principal_owner")
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

    def test_upload_pdf_returns_metadata_only(
        self, client: TestClient, owner_token: str, workspace: Path
    ) -> None:
        resp = self._upload(
            client, owner_token, filename="doc.pdf", media_type=PDF_MEDIA_TYPE,
            data_base64=base64.b64encode(PDF_BYTES).decode(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True and body["kind"] == "document"
        record = load_document(SQLiteStore(workspace), body["attachment_id"])
        assert record is not None and "Hello Raiker PDF" in record["extracted_text"]

    def test_upload_rejects_unsupported_media_type(
        self, client: TestClient, owner_token: str
    ) -> None:
        resp = self._upload(client, owner_token, media_type="application/x-msdownload")
        assert resp.status_code == 400
        assert "unsupported_media_type" in json.dumps(resp.json())

    def test_upload_rejects_corrupt_pdf(
        self, client: TestClient, owner_token: str
    ) -> None:
        resp = self._upload(
            client, owner_token, filename="bad.pdf", media_type=PDF_MEDIA_TYPE,
            data_base64=base64.b64encode(b"not a pdf").decode(),
        )
        assert resp.status_code == 400
        assert "content_does_not_match_media_type" in json.dumps(resp.json())

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
