from __future__ import annotations

from pathlib import Path

import pytest

from raiker.auth.accounts import AccountService, AuthError
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.control.dashboard import DashboardService
from raiker.runtime.attachments import store_document
from raiker.storage.sqlite import SQLiteStore


def test_cli_bootstrap_reserves_the_only_web_account_slot(tmp_path: Path) -> None:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    with pytest.raises(AuthError, match="separate Raiker instance"):
        AccountService(tmp_path).register("other", "safe-password")


def test_cli_bootstrap_backfills_legacy_project_session_and_active_selection(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    store.create_project("legacy", "Legacy", "projects/legacy")
    store.save_project_context("legacy", instructions="legacy", attachment_ids=[])
    store.save_active_project("legacy")
    store.create_session("legacy-session", str(tmp_path))

    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)

    session = store.load_session("legacy-session")
    assert session is not None
    assert session["user_id"] == "owner"
    assert store.load_project("legacy", user_id="owner") is not None
    assert store.get_active_project("owner") == "legacy"


def test_web_first_registration_backfills_legacy_attachment_to_its_principal(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    attachment = store_document(
        store, filename="legacy.txt", media_type="text/plain", data=b"legacy",
    )

    principal_id = AccountService(tmp_path).register("owner", "safe-password")

    stored = store.load_attachment(attachment.attachment_id)
    assert stored is not None
    assert stored["owner_principal_id"] == principal_id


def test_project_context_rejects_a_foreign_attachment(tmp_path: Path) -> None:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    store = SQLiteStore(tmp_path)
    service = DashboardService(tmp_path)
    project_id = service.create_project("Owned", "principal_owner").data["project_id"]
    foreign = store_document(
        store, filename="foreign.txt", media_type="text/plain", data=b"foreign",
        owner_principal_id="principal_other",
    )

    result = service.save_project_context(
        project_id, instructions="", attachment_ids=[foreign.attachment_id],
        acting_principal_id="principal_owner",
    )

    assert not result.ok
    assert result.reason_code == "unknown_project_attachment"


def test_task_project_selection_is_limited_to_the_calling_user(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    store.create_project("foreign", "Foreign", "projects/foreign")
    with pytest.raises(ValueError, match="unknown_project:foreign"):
        DashboardService(tmp_path).create_task(
            title="task", objective="test", user_id="owner", principal_id="principal_owner",
            project_id="foreign",
        )
