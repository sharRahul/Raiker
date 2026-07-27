"""BUG-07 — session-authorized, view-only file previews.

Two claims are under test. The first is authorization: an attachment is
previewable only by the account that uploaded it, and only from the conversation
it was actually attached to — a valid id from another chat, or another account,
is a 404 that leaks nothing. The second is safety: a preview is inert. Markdown
arrives as source text (never server-rendered HTML), .docx/.xlsx are parsed with
bounded stdlib zip+XML into text and cell values, PDFs are served as PDF bytes
with an explicit type and ``nosniff``, and anything unsupported or unreadable
becomes an honest ``unavailable`` preview rather than a blank pane.
"""

from __future__ import annotations

import base64
import io
import zipfile
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.routes_prompts import _record_generated_file_attachments
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import utc_now
from raiker.contracts.models import PromptEnvelope
from raiker.runtime.attachment_preview import (
    KIND_IMAGE,
    KIND_MARKDOWN,
    KIND_PDF,
    KIND_TABLE,
    KIND_TEXT,
    KIND_UNAVAILABLE,
    MAX_PREVIEW_TEXT_CHARS,
    AttachmentPreviewService,
)
from raiker.runtime.attachments import (
    DOCX_MEDIA_TYPE,
    PDF_MEDIA_TYPE,
    XLSX_MEDIA_TYPE,
    store_document,
    store_image,
)
from raiker.storage.sqlite import SQLiteStore
from tests.test_document_attachments import DOCX_BYTES, PDF_BYTES, make_docx

OWNER_PRINCIPAL = "principal_owner"
SESSION_ID = "sess_preview"

MD_SOURCE = "# Title\n\n<script>alert(1)</script>\n\nSome **markdown** body.\n"

# A real 1x1 PNG: the image validator sniffs magic bytes, so a placeholder
# string would be rejected before any preview is built.
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def make_xlsx(rows: list[list[str]], *, shared: bool = True) -> bytes:
    """A minimal .xlsx (OOXML zip) whose first sheet holds ``rows``."""
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    strings: list[str] = []
    if shared:
        for row in rows:
            for cell in row:
                if cell not in strings:
                    strings.append(cell)
    sheet_rows = []
    for r, row in enumerate(rows, start=1):
        cells = []
        for c, value in enumerate(row):
            ref = f"{chr(ord('A') + c)}{r}"
            if shared:
                cells.append(f'<c r="{ref}" t="s"><v>{strings.index(value)}</v></c>')
            else:
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{value}</t></is></c>')
        sheet_rows.append(f'<row r="{r}">' + "".join(cells) + "</row>")
    sheet = f'<worksheet {ns}><sheetData>' + "".join(sheet_rows) + "</sheetData></worksheet>"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("xl/workbook.xml", f'<workbook {ns}><sheets/></workbook>'.encode())
        archive.writestr("xl/worksheets/sheet1.xml", sheet.encode())
        if shared:
            items = "".join(f"<si><t>{value}</t></si>" for value in strings)
            archive.writestr(
                "xl/sharedStrings.xml", f'<sst {ns}>{items}</sst>'.encode()
            )
    return buf.getvalue()


XLSX_BYTES = make_xlsx([["Quarterly report", "Owner"], ["Revenue", "42"]])


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture()
def store(workspace: Path) -> SQLiteStore:
    return SQLiteStore(workspace)


@pytest.fixture()
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


@pytest.fixture()
def owner_token(workspace: Path) -> str:
    raw, _ = ApiSessionStore(workspace).create_session(OWNER_PRINCIPAL)
    return raw


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _attach(
    store: SQLiteStore,
    *,
    filename: str,
    media_type: str,
    data: bytes,
    session_id: str = SESSION_ID,
    owner: str = OWNER_PRINCIPAL,
) -> str:
    """Store a document and bind it to a session, as a prompt turn would."""
    stored = store_document(
        store, filename=filename, media_type=media_type, data=data, owner_principal_id=owner
    )
    store.save_session_attachment_ref(
        session_id=session_id,
        attachment_id=stored.attachment_id,
        owner_principal_id=owner,
        turn_id="turn_1",
    )
    return stored.attachment_id


def _attach_image(
    store: SQLiteStore,
    *,
    filename: str = "shot.png",
    media_type: str = "image/png",
    data: bytes = PNG_BYTES,
    session_id: str = SESSION_ID,
    owner: str = OWNER_PRINCIPAL,
) -> str:
    """Store an image and bind it to a session, as a prompt turn would."""
    stored = store_image(
        store, filename=filename, media_type=media_type, data=data, owner_principal_id=owner
    )
    store.save_session_attachment_ref(
        session_id=session_id,
        attachment_id=stored.attachment_id,
        owner_principal_id=owner,
        turn_id="turn_1",
    )
    return stored.attachment_id


def _preview_url(attachment_id: str, session_id: str = SESSION_ID) -> str:
    return f"/api/sessions/{session_id}/attachments/{attachment_id}/preview"


# ── authorization ───────────────────────────────────────────────────────────


class TestPreviewAuthorization:
    def test_preview_is_limited_to_the_attachment_owner_and_session(
        self, client: TestClient, store: SQLiteStore, owner_token: str, workspace: Path, seed_account: Any
    ) -> None:
        attachment_id = _attach(
            store, filename="notes.md", media_type="text/markdown", data=MD_SOURCE.encode()
        )
        _, other_token = seed_account(workspace, "bob")
        assert client.get(_preview_url(attachment_id), headers=_auth(owner_token)).status_code == 200
        assert client.get(_preview_url(attachment_id), headers=_auth(other_token)).status_code == 404

    def test_preview_requires_authentication(
        self, client: TestClient, store: SQLiteStore
    ) -> None:
        attachment_id = _attach(
            store, filename="notes.md", media_type="text/markdown", data=MD_SOURCE.encode()
        )
        assert client.get(_preview_url(attachment_id)).status_code == 401

    def test_attachment_from_another_conversation_is_not_previewable(
        self, client: TestClient, store: SQLiteStore, owner_token: str
    ) -> None:
        attachment_id = _attach(
            store, filename="notes.md", media_type="text/markdown", data=MD_SOURCE.encode()
        )
        resp = client.get(
            _preview_url(attachment_id, session_id="sess_other"), headers=_auth(owner_token)
        )
        assert resp.status_code == 404

    def test_unreferenced_attachment_is_not_previewable(
        self, client: TestClient, store: SQLiteStore, owner_token: str
    ) -> None:
        # Uploaded but never carried by a prompt: ownership alone is not a grant.
        stored = store_document(
            store,
            filename="notes.md",
            media_type="text/markdown",
            data=MD_SOURCE.encode(),
            owner_principal_id=OWNER_PRINCIPAL,
        )
        resp = client.get(_preview_url(stored.attachment_id), headers=_auth(owner_token))
        assert resp.status_code == 404

    def test_unknown_attachment_is_a_404(self, client: TestClient, owner_token: str) -> None:
        assert client.get(_preview_url("att_missing"), headers=_auth(owner_token)).status_code == 404

    def test_service_refuses_an_empty_owner(self, store: SQLiteStore) -> None:
        attachment_id = _attach(
            store, filename="notes.md", media_type="text/markdown", data=MD_SOURCE.encode()
        )
        assert AttachmentPreviewService(store).get(SESSION_ID, attachment_id, "") is None


# ── safe representations ────────────────────────────────────────────────────


class TestPreviewRepresentations:
    def test_markdown_preview_carries_source_text_and_no_html(
        self, store: SQLiteStore
    ) -> None:
        attachment_id = _attach(
            store, filename="notes.md", media_type="text/markdown", data=MD_SOURCE.encode()
        )
        preview = AttachmentPreviewService(store).get(SESSION_ID, attachment_id, OWNER_PRINCIPAL)
        assert preview is not None
        assert preview.kind == KIND_MARKDOWN
        # The server renders no HTML at all: the client's escape-first renderer
        # turns this into visible text, so there is no markup to sanitise here.
        assert "html" not in preview.to_dict()
        assert preview.text == MD_SOURCE

    def test_plain_text_preview(self, store: SQLiteStore) -> None:
        attachment_id = _attach(
            store, filename="notes.txt", media_type="text/plain", data=b"hello raiker"
        )
        preview = AttachmentPreviewService(store).get(SESSION_ID, attachment_id, OWNER_PRINCIPAL)
        assert preview is not None
        assert preview.kind == KIND_TEXT
        assert preview.text == "hello raiker"
        assert preview.truncated is False

    def test_docx_preview_extracts_text(self, store: SQLiteStore) -> None:
        attachment_id = _attach(
            store,
            filename="report.docx",
            media_type=DOCX_MEDIA_TYPE,
            data=make_docx("Quarterly report"),
        )
        preview = AttachmentPreviewService(store).get(SESSION_ID, attachment_id, OWNER_PRINCIPAL)
        assert preview is not None
        assert preview.kind == KIND_TEXT
        assert "Quarterly report" in preview.text

    def test_xlsx_preview_returns_table_rows(self, store: SQLiteStore) -> None:
        attachment_id = _attach(
            store, filename="report.xlsx", media_type=XLSX_MEDIA_TYPE, data=XLSX_BYTES
        )
        preview = AttachmentPreviewService(store).get(SESSION_ID, attachment_id, OWNER_PRINCIPAL)
        assert preview is not None
        assert preview.kind == KIND_TABLE
        assert preview.rows[0] == ("Quarterly report", "Owner")
        assert preview.rows[1] == ("Revenue", "42")

    def test_xlsx_preview_is_bounded(self, store: SQLiteStore) -> None:
        from raiker.runtime.attachment_preview import MAX_PREVIEW_ROWS

        rows = [[f"row-{i}"] for i in range(MAX_PREVIEW_ROWS + 25)]
        attachment_id = _attach(
            store, filename="big.xlsx", media_type=XLSX_MEDIA_TYPE, data=make_xlsx(rows)
        )
        preview = AttachmentPreviewService(store).get(SESSION_ID, attachment_id, OWNER_PRINCIPAL)
        assert preview is not None
        assert len(preview.rows) == MAX_PREVIEW_ROWS
        assert preview.truncated is True

    def test_text_preview_is_bounded(self, store: SQLiteStore) -> None:
        data = ("x" * (MAX_PREVIEW_TEXT_CHARS + 500)).encode()
        attachment_id = _attach(
            store, filename="big.txt", media_type="text/plain", data=data
        )
        preview = AttachmentPreviewService(store).get(SESSION_ID, attachment_id, OWNER_PRINCIPAL)
        assert preview is not None
        assert len(preview.text) == MAX_PREVIEW_TEXT_CHARS
        assert preview.truncated is True

    def test_pdf_preview_names_a_session_scoped_url(self, store: SQLiteStore) -> None:
        attachment_id = _attach(
            store, filename="doc.pdf", media_type=PDF_MEDIA_TYPE, data=PDF_BYTES
        )
        preview = AttachmentPreviewService(store).get(SESSION_ID, attachment_id, OWNER_PRINCIPAL)
        assert preview is not None
        assert preview.kind == KIND_PDF
        assert preview.pdf_url == (
            f"/api/sessions/{SESSION_ID}/attachments/{attachment_id}/preview/pdf"
        )
        # The bytes never ride the JSON preview.
        assert preview.text == ""
        assert "data" not in preview.to_dict()

    def test_image_preview_names_a_session_scoped_url(self, store: SQLiteStore) -> None:
        attachment_id = _attach_image(store)
        preview = AttachmentPreviewService(store).get(SESSION_ID, attachment_id, OWNER_PRINCIPAL)
        assert preview is not None
        assert preview.kind == KIND_IMAGE
        assert preview.image_url == (
            f"/api/sessions/{SESSION_ID}/attachments/{attachment_id}/preview/image"
        )
        # The picture rides its own byte route; the JSON carries no pixels.
        assert preview.text == ""
        assert "data" not in preview.to_dict()

    def test_an_image_whose_bytes_do_not_match_its_type_is_unavailable(
        self, store: SQLiteStore
    ) -> None:
        # Stored straight to the database, bypassing upload validation: a file
        # claiming to be a PNG must not be handed to an <img> on that word.
        store.save_attachment(
            attachment_id="att_fake_png",
            kind="image",
            filename="shot.png",
            media_type="image/png",
            sha256="x",
            data=b"GIF89a not really a png",
            owner_principal_id=OWNER_PRINCIPAL,
        )
        store.save_session_attachment_ref(
            session_id=SESSION_ID,
            attachment_id="att_fake_png",
            owner_principal_id=OWNER_PRINCIPAL,
            turn_id="turn_1",
        )
        preview = AttachmentPreviewService(store).get(SESSION_ID, "att_fake_png", OWNER_PRINCIPAL)
        assert preview is not None
        assert preview.kind == KIND_UNAVAILABLE
        assert preview.unavailable_reason == "content_does_not_match_media_type"

    def test_an_unknown_type_is_still_unsupported(self, store: SQLiteStore) -> None:
        store.save_attachment(
            attachment_id="att_zip",
            kind="document",
            filename="archive.zip",
            media_type="application/zip",
            sha256="x",
            data=b"PK\x03\x04",
            owner_principal_id=OWNER_PRINCIPAL,
        )
        store.save_session_attachment_ref(
            session_id=SESSION_ID,
            attachment_id="att_zip",
            owner_principal_id=OWNER_PRINCIPAL,
            turn_id="turn_1",
        )
        preview = AttachmentPreviewService(store).get(SESSION_ID, "att_zip", OWNER_PRINCIPAL)
        assert preview is not None
        assert preview.kind == KIND_UNAVAILABLE
        assert preview.unavailable_reason == "unsupported_for_preview"

    def test_record_that_no_longer_validates_is_unavailable(self, store: SQLiteStore) -> None:
        # Written straight to the store, bypassing upload validation: the
        # preview must refuse to parse it rather than render half a document.
        store.save_attachment(
            attachment_id="att_bad",
            kind="document",
            filename="broken.docx",
            media_type=DOCX_MEDIA_TYPE,
            sha256="x",
            data=b"not a zip package at all",
            owner_principal_id=OWNER_PRINCIPAL,
        )
        store.save_session_attachment_ref(
            session_id=SESSION_ID,
            attachment_id="att_bad",
            owner_principal_id=OWNER_PRINCIPAL,
            turn_id="turn_1",
        )
        preview = AttachmentPreviewService(store).get(SESSION_ID, "att_bad", OWNER_PRINCIPAL)
        assert preview is not None
        assert preview.kind == KIND_UNAVAILABLE
        assert preview.unavailable_reason == "content_does_not_match_media_type"


# ── the PDF byte route ──────────────────────────────────────────────────────


class TestPdfPreviewRoute:
    def _pdf_url(self, attachment_id: str, session_id: str = SESSION_ID) -> str:
        return _preview_url(attachment_id, session_id) + "/pdf"

    def test_pdf_is_served_inline_with_a_pinned_content_type(
        self, client: TestClient, store: SQLiteStore, owner_token: str
    ) -> None:
        attachment_id = _attach(
            store, filename="doc.pdf", media_type=PDF_MEDIA_TYPE, data=PDF_BYTES
        )
        resp = client.get(self._pdf_url(attachment_id), headers=_auth(owner_token))
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/pdf")
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert resp.headers["content-disposition"].startswith("inline;")
        assert resp.content == PDF_BYTES

    def test_pdf_route_refuses_another_account(
        self, client: TestClient, store: SQLiteStore, workspace: Path, seed_account: Any
    ) -> None:
        attachment_id = _attach(
            store, filename="doc.pdf", media_type=PDF_MEDIA_TYPE, data=PDF_BYTES
        )
        _, other_token = seed_account(workspace, "bob")
        assert client.get(self._pdf_url(attachment_id), headers=_auth(other_token)).status_code == 404

    def test_pdf_route_refuses_a_non_pdf_attachment(
        self, client: TestClient, store: SQLiteStore, owner_token: str
    ) -> None:
        attachment_id = _attach(
            store, filename="notes.txt", media_type="text/plain", data=b"hello"
        )
        assert client.get(self._pdf_url(attachment_id), headers=_auth(owner_token)).status_code == 404

    def test_disposition_filename_cannot_inject_header_parameters(
        self, client: TestClient, store: SQLiteStore, owner_token: str
    ) -> None:
        attachment_id = _attach(
            store,
            filename='evil"; download; x="',
            media_type=PDF_MEDIA_TYPE,
            data=PDF_BYTES,
        )
        resp = client.get(self._pdf_url(attachment_id), headers=_auth(owner_token))
        assert resp.status_code == 200
        disposition = resp.headers["content-disposition"]
        # The name survives as inert text: the quote and the semicolons that
        # would have closed the value and appended a second parameter are gone,
        # so the header still carries exactly one quoted filename.
        assert disposition.count('"') == 2
        assert disposition.count(";") == 1
        assert disposition.startswith('inline; filename="')


# ── the image byte route ────────────────────────────────────────────────────


class TestImagePreviewRoute:
    def _image_url(self, attachment_id: str, session_id: str = SESSION_ID) -> str:
        return _preview_url(attachment_id, session_id) + "/image"

    def test_image_is_served_inline_with_its_validated_content_type(
        self, client: TestClient, store: SQLiteStore, owner_token: str
    ) -> None:
        attachment_id = _attach_image(store)
        resp = client.get(self._image_url(attachment_id), headers=_auth(owner_token))
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("image/png")
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert resp.headers["content-disposition"].startswith("inline;")
        assert resp.headers["cache-control"] == "no-store"
        assert resp.content == PNG_BYTES

    def test_image_route_refuses_another_account(
        self, client: TestClient, store: SQLiteStore, workspace: Path, seed_account: Any
    ) -> None:
        attachment_id = _attach_image(store)
        _, other_token = seed_account(workspace, "bob")
        assert client.get(self._image_url(attachment_id), headers=_auth(other_token)).status_code == 404

    def test_image_route_refuses_another_conversation(
        self, client: TestClient, store: SQLiteStore, owner_token: str
    ) -> None:
        attachment_id = _attach_image(store)
        resp = client.get(
            self._image_url(attachment_id, session_id="sess_other"), headers=_auth(owner_token)
        )
        assert resp.status_code == 404

    def test_image_route_refuses_a_document(
        self, client: TestClient, store: SQLiteStore, owner_token: str
    ) -> None:
        # The routes are not interchangeable: a PDF is never served as an image
        # (nor an image as a PDF), so the pinned content type cannot be chosen
        # by picking a URL.
        attachment_id = _attach(
            store, filename="doc.pdf", media_type=PDF_MEDIA_TYPE, data=PDF_BYTES
        )
        assert client.get(self._image_url(attachment_id), headers=_auth(owner_token)).status_code == 404
        image_id = _attach_image(store)
        pdf_route = _preview_url(image_id) + "/pdf"
        assert client.get(pdf_route, headers=_auth(owner_token)).status_code == 404

    def test_image_route_refuses_bytes_that_do_not_match_the_type(
        self, client: TestClient, store: SQLiteStore, owner_token: str
    ) -> None:
        store.save_attachment(
            attachment_id="att_fake",
            kind="image",
            filename="shot.png",
            media_type="image/png",
            sha256="x",
            data=b"GIF89a not really a png",
            owner_principal_id=OWNER_PRINCIPAL,
        )
        store.save_session_attachment_ref(
            session_id=SESSION_ID,
            attachment_id="att_fake",
            owner_principal_id=OWNER_PRINCIPAL,
            turn_id="turn_1",
        )
        assert client.get(self._image_url("att_fake"), headers=_auth(owner_token)).status_code == 404


# ── the JSON preview route + session file list ──────────────────────────────


class TestPreviewRoutes:
    def test_preview_route_returns_the_safe_representation(
        self, client: TestClient, store: SQLiteStore, owner_token: str
    ) -> None:
        attachment_id = _attach(
            store, filename="report.xlsx", media_type=XLSX_MEDIA_TYPE, data=XLSX_BYTES
        )
        body = client.get(_preview_url(attachment_id), headers=_auth(owner_token)).json()
        assert body["kind"] == KIND_TABLE
        assert body["filename"] == "report.xlsx"
        assert body["rows"][0] == ["Quarterly report", "Owner"]

    def test_session_file_list_is_owner_scoped(
        self, client: TestClient, store: SQLiteStore, owner_token: str, workspace: Path, seed_account: Any
    ) -> None:
        attachment_id = _attach(
            store, filename="notes.md", media_type="text/markdown", data=MD_SOURCE.encode()
        )
        listing = client.get(f"/api/sessions/{SESSION_ID}/attachments", headers=_auth(owner_token))
        assert listing.status_code == 200
        files = listing.json()["files"]
        assert [f["attachment_id"] for f in files] == [attachment_id]
        assert files[0]["turn_id"] == "turn_1"
        assert files[0]["previewable"] is True
        assert "data" not in files[0]
        _, other_token = seed_account(workspace, "bob")
        other = client.get(f"/api/sessions/{SESSION_ID}/attachments", headers=_auth(other_token))
        assert other.json()["files"] == []


# ── the reference is written by the prompt route ────────────────────────────


class TestPromptRecordsReferences:
    def _upload(self, client: TestClient, token: str, data: bytes) -> str:
        resp = client.post(
            "/api/attachments",
            json={
                "filename": "notes.md",
                "media_type": "text/markdown",
                "data_base64": base64.b64encode(data).decode(),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        return str(resp.json()["attachment_id"])

    def test_prompting_with_a_document_makes_it_previewable(
        self, client: TestClient, owner_token: str
    ) -> None:
        attachment_id = self._upload(client, owner_token, MD_SOURCE.encode())
        # Before the turn there is no reference, so nothing is previewable.
        assert client.get(_preview_url(attachment_id), headers=_auth(owner_token)).status_code == 404
        resp = client.post(
            "/api/prompts",
            json={
                "text": "what is in this file?",
                "attachments": [{"type": "document", "attachment_id": attachment_id}],
            },
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        session_id = str(resp.json()["session_id"])
        preview = client.get(
            _preview_url(attachment_id, session_id=session_id), headers=_auth(owner_token)
        )
        assert preview.status_code == 200
        assert preview.json()["kind"] == KIND_MARKDOWN

    def test_an_unowned_attachment_id_records_nothing(
        self, client: TestClient, store: SQLiteStore, owner_token: str, workspace: Path, seed_account: Any
    ) -> None:
        other_principal, _ = seed_account(workspace, "bob")
        stolen = store_document(
            store,
            filename="secret.md",
            media_type="text/markdown",
            data=b"# secret",
            owner_principal_id=other_principal,
        )
        resp = client.post(
            "/api/prompts",
            json={
                "text": "show me",
                "attachments": [{"type": "document", "attachment_id": stolen.attachment_id}],
            },
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        session_id = str(resp.json()["session_id"])
        assert (
            client.get(
                _preview_url(stolen.attachment_id, session_id=session_id),
                headers=_auth(owner_token),
            ).status_code
            == 404
        )

    def test_chat_generated_markdown_is_stored_and_previewable(
        self, client: TestClient, store: SQLiteStore, owner_token: str, workspace: Path
    ) -> None:
        from types import SimpleNamespace

        (workspace / "draft.md").write_text("# Generated draft", encoding="utf-8")
        store.insert_checkpoint_capture_entry(
            manifest_id="ckcap_generated",
            session_id=SESSION_ID,
            turn_id="turn_generated",
            action_id="act_generated",
            capability="file_write_execution",
            principal_id=OWNER_PRINCIPAL,
            workspace_path="draft.md",
            pre_image_sha256=None,
            pre_image_size=0,
            existed_before=False,
            capture_status="absent",
            created_at=utc_now(),
        )

        _record_generated_file_attachments(
            workspace,
            cast(
                PromptEnvelope,
                SimpleNamespace(session_id=SESSION_ID, turn_id="turn_generated"),
            ),
            OWNER_PRINCIPAL,
        )

        files = client.get(f"/api/sessions/{SESSION_ID}/attachments", headers=_auth(owner_token)).json()["files"]
        assert len(files) == 1
        assert files[0]["filename"] == "draft.md"
        assert files[0]["turn_id"] == "turn_generated"
        preview = client.get(_preview_url(files[0]["attachment_id"]), headers=_auth(owner_token))
        assert preview.status_code == 200
        assert preview.json()["text"] == "# Generated draft"


def test_docx_fixture_is_shared_with_the_document_suite() -> None:
    # Guards the cross-suite import above: a rename there must fail here, not
    # silently reduce this file's coverage.
    assert DOCX_BYTES.startswith(b"PK\x03\x04")
