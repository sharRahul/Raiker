"""Web-app task 3 (paths-first slice) — chat attachments as governed context.

A prompt may carry workspace **path** attachments. Each is resolved through the
same workspace-scoped filesystem layer the read tools use, so a path outside
the workspace fails closed (honest denial item, no content). Files become
bounded text context items, directories become listings, and every attachment
item is labelled ``untrusted_external`` — data, never instructions. Invalid
attachment shapes reject the prompt before a turn starts.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.routes_prompts import _validated_attachments
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.context.gatherer import ContextGatherer
from raiker.context.models import ContextBundle
from raiker.contracts.models import ContractValidationError


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "attach"
    ws.mkdir()
    (ws / "notes.md").write_text("attachment payload ALPHA", encoding="utf-8")
    (ws / "docs").mkdir()
    (ws / "docs" / "a.txt").write_text("aaa", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("OUTSIDE-SECRET", encoding="utf-8")
    return ws


def _gather(workspace: Path, attachments: list[dict[str, object]]) -> ContextBundle:
    return ContextGatherer().gather(
        workspace_root=workspace,
        session_id="sess_t",
        turn_id="turn_t",
        prompt_text="hello",
        attachments=attachments,
    )


def _attachment_items(bundle):  # type: ignore[no-untyped-def]
    return [i for i in bundle.items if i.source.source_type == "attachment"]


class TestPathAttachmentGathering:
    def test_file_attachment_included_and_trust_labelled(self, workspace: Path) -> None:
        bundle = _gather(workspace, [{"type": "path", "path": "notes.md"}])
        items = _attachment_items(bundle)
        assert len(items) == 1
        item = items[0]
        assert item.included is True
        assert "attachment payload ALPHA" in item.content
        assert item.source.trust_level == "untrusted_external"
        assert item.source.provenance["origin"] == "user_attachment"
        assert item.metadata["attachment_status"] == "included"
        assert item.metadata["kind"] == "file"

    def test_directory_attachment_becomes_listing(self, workspace: Path) -> None:
        bundle = _gather(workspace, [{"type": "path", "path": "docs"}])
        item = _attachment_items(bundle)[0]
        assert item.metadata["kind"] == "directory"
        assert "a.txt" in item.content

    def test_path_outside_workspace_fails_closed(self, workspace: Path) -> None:
        bundle = _gather(workspace, [{"type": "path", "path": "../outside.txt"}])
        item = _attachment_items(bundle)[0]
        assert item.metadata["attachment_status"] == "denied_outside_workspace"
        # Fail closed: no file content may leak into the item.
        assert "OUTSIDE-SECRET" not in item.content

    def test_absolute_path_outside_workspace_fails_closed(self, workspace: Path) -> None:
        bundle = _gather(workspace, [{"type": "path", "path": "/etc/hostname"}])
        item = _attachment_items(bundle)[0]
        assert item.metadata["attachment_status"] == "denied_outside_workspace"

    def test_missing_path_is_reported_honestly(self, workspace: Path) -> None:
        bundle = _gather(workspace, [{"type": "path", "path": "no-such-file.txt"}])
        item = _attachment_items(bundle)[0]
        assert item.metadata["attachment_status"] == "not_found"

    def test_unsupported_type_is_reported_honestly(self, workspace: Path) -> None:
        bundle = _gather(workspace, [{"type": "image", "path": "notes.md"}])
        item = _attachment_items(bundle)[0]
        assert str(item.metadata["attachment_status"]).startswith("unsupported_type")
        assert "attachment payload ALPHA" not in item.content

    def test_over_limit_attachments_dropped_with_note(self, workspace: Path) -> None:
        many: list[dict[str, object]] = [
            {"type": "path", "path": "notes.md"} for _ in range(10)
        ]
        bundle = _gather(workspace, many)
        items = _attachment_items(bundle)
        # 8 honoured + 1 honest drop note.
        assert len(items) == ContextGatherer.MAX_ATTACHMENTS + 1
        assert items[-1].metadata["attachment_status"] == "dropped_over_limit"

    def test_no_attachments_changes_nothing(self, workspace: Path) -> None:
        bundle = _gather(workspace, [])
        assert _attachment_items(bundle) == []

    def test_attachment_content_is_bounded(self, workspace: Path) -> None:
        (workspace / "big.txt").write_text("z" * 50_000, encoding="utf-8")
        bundle = _gather(workspace, [{"type": "path", "path": "big.txt"}])
        item = _attachment_items(bundle)[0]
        assert len(item.content) <= ContextGatherer().config.max_item_chars


class TestAttachmentValidation:
    def test_valid_path_attachments_pass(self) -> None:
        cleaned = _validated_attachments([{"type": "path", "path": " notes.md "}])
        assert cleaned == [{"type": "path", "path": "notes.md"}]

    def test_none_is_empty(self) -> None:
        assert _validated_attachments(None) == []

    def test_unknown_type_rejected(self) -> None:
        with pytest.raises(ContractValidationError):
            _validated_attachments([{"type": "image", "path": "x.png"}])

    def test_missing_path_rejected(self) -> None:
        with pytest.raises(ContractValidationError):
            _validated_attachments([{"type": "path", "path": "  "}])

    def test_too_many_rejected(self) -> None:
        with pytest.raises(ContractValidationError):
            _validated_attachments([{"type": "path", "path": f"f{i}"} for i in range(9)])


class TestPromptApiFailsClosed:
    @pytest.fixture
    def client(self, workspace: Path) -> TestClient:
        bootstrap_owner("rahul", "Rahul", workspace_root=workspace)
        app: FastAPI = create_app(workspace)
        return TestClient(app)

    @pytest.fixture
    def owner_token(self, workspace: Path) -> str:
        raw, _ = ApiSessionStore(workspace).create_session("principal_rahul")
        return raw

    def test_invalid_attachment_rejects_the_prompt(
        self, client: TestClient, owner_token: str
    ) -> None:
        resp = client.post(
            "/api/prompts",
            json={"text": "hi", "attachments": [{"type": "upload", "data": "…"}]},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "failed"
        assert "Invalid prompt" in body["message"]
        assert "invalid_attachment_type" in body["message"]
