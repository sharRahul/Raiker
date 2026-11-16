"""An attached document is said to be inline, not a workspace file (regular use, 2026-11-16)."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

from raiker.context.gatherer import ContextGatherer


def test_the_document_header_says_it_is_not_a_workspace_file(tmp_path: Path) -> None:
    gatherer = ContextGatherer()
    record = {"filename": "budget.csv", "media_type": "text/csv", "byte_size": 10, "extracted_text": "a,b"}
    with mock.patch("raiker.runtime.attachments.load_document", return_value=record), \
            mock.patch("raiker.context.gatherer.SQLiteStore"):
        item = gatherer._document_attachment_item(tmp_path, {"attachment_id": "att_1"}, "principal_owner")
    assert "not a file in the workspace" in item.content
    assert item.content.endswith("a,b")
