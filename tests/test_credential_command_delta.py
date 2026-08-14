from __future__ import annotations

from pathlib import Path

import pytest

from raiker.execution.commands.credential_delta import CredentialDeltaScanner, DeltaState
from raiker.execution.commands.store import CommandStore, ReceiptImmutable
from raiker.storage.sqlite import SQLiteStore


def test_exact_and_pattern_secret_delta_is_quarantined_without_persisting_match(
    tmp_path: Path,
) -> None:
    delta = tmp_path / "delta"
    delta.mkdir()
    secret = "credential-value-123456789"
    (delta / "output.txt").write_text(f"before {secret} after", encoding="utf-8")
    result = CredentialDeltaScanner(registered=(secret,)).scan(delta)
    assert result.state is DeltaState.QUARANTINED
    assert result.match_count == 1
    assert secret not in result.safe_manifest_json

    (delta / "output.txt").write_text("sk-proj-aabbccddeeff00112233", encoding="utf-8")
    assert CredentialDeltaScanner().scan(delta).state is DeltaState.QUARANTINED


def test_clean_delta_manifest_contains_only_safe_metadata(tmp_path: Path) -> None:
    delta = tmp_path / "delta"
    delta.mkdir()
    (delta / "report.txt").write_text("safe report", encoding="utf-8")
    result = CredentialDeltaScanner().scan(delta)
    assert result.state is DeltaState.CLEAN
    assert "report.txt" in result.safe_manifest_json
    assert "safe report" not in result.safe_manifest_json


def test_delta_resolution_is_owner_scoped_compare_and_swap_and_immutable(tmp_path: Path) -> None:
    store = CommandStore(SQLiteStore(tmp_path))
    store.create_credential_delta(
        owner_principal_id="owner_a",
        run_id="cmd_delta",
        environment_profile_id="container_a",
        state="quarantined",
        snapshot_handle=b"snapshot",
        cleanup_scan_bundle=b"matcher",
        safe_manifest_json='{"files":[]}',
        delta_digest="a" * 64,
        scan_digest="b" * 64,
    )
    assert store.list_unresolved_deltas("owner_b", "container_a") == []
    assert store.resolve_credential_delta(
        "owner_a", "cmd_delta", decision_id="decision_1", resolution="discarded"
    )
    receipt = store.get_delta_receipt("owner_a", "cmd_delta")
    assert receipt is not None and receipt["resolution"] == "discarded"
    with pytest.raises(ReceiptImmutable):
        store.resolve_credential_delta(
            "owner_a", "cmd_delta", decision_id="decision_2", resolution="discarded"
        )


def test_unresolved_delta_survives_store_restart(tmp_path: Path) -> None:
    first = CommandStore(SQLiteStore(tmp_path))
    first.create_credential_delta(
        owner_principal_id="owner_a",
        run_id="cmd_delta",
        environment_profile_id="container_a",
        state="scanning",
        snapshot_handle=b"snapshot",
        cleanup_scan_bundle=b"matcher",
        safe_manifest_json='{"files":[]}',
        delta_digest="a" * 64,
        scan_digest="b" * 64,
    )
    second = CommandStore(SQLiteStore(tmp_path))
    assert second.list_unresolved_deltas("owner_a", "container_a")[0]["run_id"] == "cmd_delta"
