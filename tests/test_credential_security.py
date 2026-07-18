from __future__ import annotations

from pathlib import Path

import pytest

from raiker.security.credentials import CredentialLifecycle
from raiker.storage.sqlite import SQLiteStore


def _store(tmp_path: Path) -> SQLiteStore:
    workspace = tmp_path / "credential-security"
    workspace.mkdir()
    return SQLiteStore(workspace)


def test_lifecycle_marks_warning_and_overdue_without_a_secret(tmp_path: Path) -> None:
    store = _store(tmp_path)
    lifecycle = CredentialLifecycle(store, clock=lambda: "2026-07-01T00:00:00Z")

    lifecycle.record_verified("principal_owner", "github", "2026-04-17T00:00:00Z")
    lifecycle.record_verified("principal_owner", "slack", "2026-04-01T00:00:00Z")

    rows = {row.provider: row for row in lifecycle.list("principal_owner")}
    assert rows["github"].status == "warning"
    assert rows["slack"].status == "overdue"
    assert "secret" not in repr(rows).lower()


def test_verified_replacement_requires_stored_credential_metadata(tmp_path: Path) -> None:
    store = _store(tmp_path)
    lifecycle = CredentialLifecycle(store, clock=lambda: "2026-07-01T00:00:00Z")

    with pytest.raises(ValueError, match="credential_not_configured"):
        lifecycle.verify_replacement("principal_owner", "github")

    with store.connect() as connection:
        connection.execute(
            "INSERT INTO connector_credentials "
            "(principal_id, connector_id, encrypted_payload, expires_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("principal_owner", "github", b"ciphertext-only", None, "2026-06-30T00:00:00Z"),
        )
    row = lifecycle.verify_replacement("principal_owner", "github")

    assert row.status == "current"
    assert row.verified_at == "2026-07-01T00:00:00Z"
    assert store.list_credential_lifecycle("principal_other") == []
