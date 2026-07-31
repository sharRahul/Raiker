"""BUG-22 — conversation transcript export.

An export is the one governed read whose output leaves the machine as a file, so
the tests hold it to the two claims the manifest makes: the scope is the
session, and secrets are redacted before anything is rendered. The rest checks
that each format is actually the format it says it is.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id
from raiker.sessions.transcript import (
    REDACTION_POLICY,
    build_transcript,
    render_html,
    render_markdown,
    render_pdf,
    safe_filename,
)
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


def _session(client: TestClient) -> tuple[dict[str, str], str]:
    """Bearer headers plus the owner principal the session was minted for."""
    body = client.post("/api/auth/session", json={"as_principal": None}).json()
    return {"Authorization": f"Bearer {body['token']}"}, str(body["principal_id"])


def _seed_conversation(workspace: Path, principal_id: str, prompt: str, answer: str) -> str:
    """Write one session with one completed turn straight into the store."""
    store = SQLiteStore(workspace)
    session_id = new_id("sess_")
    turn_id = new_id("turn_")
    store.create_session(
        session_id,
        str(workspace),
        title="Quarterly plan",
        user_id=store.principal_user_id(principal_id),
    )
    store.insert_turn(session_id, turn_id, prompt)
    store.complete_turn(turn_id, "completed", answer)
    return session_id


class TestRendering:
    def test_a_secret_shaped_value_never_reaches_a_rendered_transcript(self) -> None:
        transcript = build_transcript(
            session_id="ses_1",
            title="Keys",
            created_at=None,
            turns=[
                {
                    "prompt_text": "my key is sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                    "summary": "Understood.",
                    "status": "completed",
                    "created_at": "2026-07-30T10:00:00Z",
                    "completed_at": "2026-07-30T10:00:01Z",
                }
            ],
        )
        for rendered in (
            render_markdown(transcript),
            render_html(transcript),
            render_pdf(transcript).decode("latin-1"),
        ):
            assert "sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" not in rendered

    def test_html_is_self_contained_and_inert(self) -> None:
        transcript = build_transcript(
            session_id="ses_1",
            title="Plan",
            created_at=None,
            turns=[{"prompt_text": "hi", "summary": "hello", "status": "completed"}],
        )
        html = render_html(transcript)
        assert html.startswith("<!doctype html>")
        assert "<script" not in html
        # No remote asset of any kind: the document must render offline.
        assert "http://" not in html and "https://" not in html
        assert REDACTION_POLICY in html

    def test_html_escapes_message_text_rather_than_rendering_it(self) -> None:
        transcript = build_transcript(
            session_id="ses_1",
            title="<img src=x onerror=alert(1)>",
            created_at=None,
            turns=[{"prompt_text": "<script>alert(1)</script>", "summary": "ok"}],
        )
        html = render_html(transcript)
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html
        assert "onerror=alert(1)>" not in html

    def test_pdf_is_a_valid_document_with_a_page_per_overflow(self) -> None:
        long_answer = "\n".join(f"line {index}" for index in range(200))
        transcript = build_transcript(
            session_id="ses_1",
            title="Long",
            created_at=None,
            turns=[{"prompt_text": "go", "summary": long_answer}],
        )
        pdf = render_pdf(transcript)
        assert pdf.startswith(b"%PDF-1.4")
        assert pdf.rstrip().endswith(b"%%EOF")
        assert b"/Type /Catalog" in pdf and b"startxref" in pdf
        # More than one page: 200 lines cannot fit on a single A4 page.
        assert pdf.count(b"/Type /Page\n") == 0  # pages are inline dictionaries
        assert pdf.count(b"/Type /Page ") >= 2

    def test_an_empty_conversation_still_produces_a_document(self) -> None:
        transcript = build_transcript(
            session_id="ses_1", title="Empty", created_at=None, turns=[]
        )
        assert render_pdf(transcript).startswith(b"%PDF")
        assert "Empty" in render_markdown(transcript)

    def test_files_are_listed_rather_than_embedded(self) -> None:
        transcript = build_transcript(
            session_id="ses_1",
            title="With files",
            created_at=None,
            turns=[{"prompt_text": "look", "summary": "done"}],
            files=[
                {
                    "filename": "budget.xlsx",
                    "media_type": "application/vnd.ms-excel",
                    "byte_size": 20480,
                    "source": "uploaded",
                }
            ],
        )
        markdown = render_markdown(transcript)
        assert "budget.xlsx" in markdown and "20480 bytes" in markdown
        assert transcript.manifest()["file_count"] == 1

    def test_the_download_name_is_reduced_to_a_safe_slug(self) -> None:
        assert safe_filename('../../etc/pa"sswd', "sess_abc", "html") == "etc-pa-sswd.html"
        assert safe_filename("", "sess_abcdefghijkl", "pdf") == "conversation-sess_abcdefg.pdf"


class TestExportApi:
    def test_the_manifest_states_counts_files_and_the_redaction_policy(
        self, client: TestClient, workspace: Path
    ) -> None:
        headers, principal = _session(client)
        session_id = _seed_conversation(workspace, principal, "Draft the plan", "Here it is.")
        body = client.get(
            f"/api/sessions/{session_id}/export/manifest", headers=headers
        ).json()
        assert body["message_count"] == 2
        assert body["redaction_policy"] == REDACTION_POLICY
        assert body["formats"] == ["html", "markdown", "pdf"]
        assert [m["role"] for m in body["messages"]] == ["you", "raiker"]

    @pytest.mark.parametrize(
        ("fmt", "media_type", "prefix"),
        [
            ("html", "text/html", b"<!doctype html>"),
            ("markdown", "text/markdown", b"# Quarterly plan"),
            ("pdf", "application/pdf", b"%PDF"),
        ],
    )
    def test_each_format_downloads_as_itself(
        self,
        client: TestClient,
        workspace: Path,
        fmt: str,
        media_type: str,
        prefix: bytes,
    ) -> None:
        headers, principal = _session(client)
        session_id = _seed_conversation(workspace, principal, "Draft the plan", "Here it is.")
        response = client.post(
            f"/api/sessions/{session_id}/export", headers=headers, json={"format": fmt}
        )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith(media_type)
        assert response.headers["content-disposition"].startswith("attachment;")
        assert response.content.startswith(prefix)

    def test_an_unknown_format_is_refused(self, client: TestClient, workspace: Path) -> None:
        headers, principal = _session(client)
        session_id = _seed_conversation(workspace, principal, "a", "b")
        response = client.post(
            f"/api/sessions/{session_id}/export", headers=headers, json={"format": "docx"}
        )
        assert response.status_code == 400
        assert response.json()["detail"]["reason_code"] == "export_format_unsupported"

    def test_an_unknown_session_cannot_be_exported(self, client: TestClient) -> None:
        headers, _principal = _session(client)
        assert (
            client.post(
                "/api/sessions/sess_missing/export", headers=headers, json={"format": "html"}
            ).status_code
            == 404
        )
        assert (
            client.get("/api/sessions/sess_missing/export/manifest", headers=headers).status_code
            == 404
        )

    def test_export_requires_a_bearer_token(self, client: TestClient, workspace: Path) -> None:
        _headers, principal = _session(client)
        session_id = _seed_conversation(workspace, principal, "a", "b")
        assert client.post(f"/api/sessions/{session_id}/export").status_code in (401, 403)
        assert client.get(f"/api/sessions/{session_id}/export/manifest").status_code in (401, 403)

    def test_a_successful_export_is_audited_without_the_transcript(
        self, client: TestClient, workspace: Path
    ) -> None:
        headers, principal = _session(client)
        store = SQLiteStore(workspace)
        session_id = _seed_conversation(workspace, principal, "Secret plan text", "Answered.")
        client.post(
            f"/api/sessions/{session_id}/export", headers=headers, json={"format": "markdown"}
        )
        events = store.list_event_index(session_id=session_id, limit=50)
        exported = [e for e in events if e["event_type"] == "session_transcript_exported"]
        assert exported, "an export must be recorded in the governed event log"
        raw = (workspace / ".raiker" / "events" / f"{session_id}.jsonl").read_text("utf-8")
        assert "session_transcript_exported" in raw
        assert "Secret plan text" not in raw
