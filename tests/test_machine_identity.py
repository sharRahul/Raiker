from __future__ import annotations

import base64
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from raiker.runtime.identity import (
    MachineAttestation,
    MachineIdentityError,
    MachineIdentityVerifier,
    VerifiedMachineIdentity,
    WorkspaceIdentityIssuer,
)
from raiker.storage.sqlite import SQLiteStore

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)


def _owner(store: SQLiteStore) -> None:
    store.insert_principal(
        principal_id="principal_owner",
        principal_type="human",
        display_name="Owner",
        delegated_by_user_id="user_owner",
        role_ids=("owner", "runtime_gate_manager"),
    )


def _mint(tmp_path: Path) -> tuple[SQLiteStore, MachineAttestation]:
    store = SQLiteStore(tmp_path)
    _owner(store)
    issued = WorkspaceIdentityIssuer(tmp_path, store).mint(
        owner_principal_id="principal_owner",
        session_id="sess_1",
        turn_id="turn_1",
        role_ids=("assistant",),
        ttl_seconds=300,
        now=NOW,
    )
    return store, issued


def _verify(
    tmp_path: Path,
    store: SQLiteStore,
    token: str,
    *,
    expected_owner_principal_id: str = "principal_owner",
    expected_session_id: str = "sess_1",
    expected_turn_id: str = "turn_1",
    expected_audience: str = "tool_broker",
    now: datetime = NOW + timedelta(seconds=1),
) -> VerifiedMachineIdentity:
    return MachineIdentityVerifier(tmp_path, store).verify(
        token,
        expected_owner_principal_id=expected_owner_principal_id,
        expected_session_id=expected_session_id,
        expected_turn_id=expected_turn_id,
        expected_audience=expected_audience,
        now=now,
    )


def test_minted_identity_is_bound_to_workspace_owner_session_turn_and_audience(
    tmp_path: Path,
) -> None:
    store, issued = _mint(tmp_path)

    verified = _verify(tmp_path, store, issued.token)

    assert verified.claims.principal_type == "ai_agent"
    assert verified.claims.owner_principal_id == "principal_owner"
    assert verified.claims.session_id == "sess_1"
    assert verified.claims.turn_id == "turn_1"
    assert verified.claims.audience == "tool_broker"
    assert verified.claims.subject == (
        f"spiffe://raiker/{verified.claims.workspace_id}/agent/turn/turn_1"
    )
    assert verified.token_fingerprint != issued.token
    assert len(verified.token_fingerprint) == 64


def test_tampered_payload_is_rejected_with_stable_reason(tmp_path: Path) -> None:
    store, issued = _mint(tmp_path)
    payload, signature = issued.token.split(".")
    decoded = json.loads(base64.urlsafe_b64decode(payload + "=="))
    decoded["turn_id"] = "turn_other"
    changed = base64.urlsafe_b64encode(
        json.dumps(decoded, sort_keys=True, separators=(",", ":")).encode()
    ).decode().rstrip("=")

    with pytest.raises(MachineIdentityError, match="machine_identity_invalid_signature"):
        _verify(tmp_path, store, f"{changed}.{signature}")


@pytest.mark.parametrize(
    ("override", "value", "reason"),
    [
        ("expected_owner_principal_id", "principal_other", "machine_identity_delegation_mismatch"),
        ("expected_session_id", "sess_other", "machine_identity_session_mismatch"),
        ("expected_turn_id", "turn_other", "machine_identity_turn_mismatch"),
        ("expected_audience", "connector", "machine_identity_wrong_audience"),
    ],
)
def test_cross_context_use_is_rejected(
    tmp_path: Path, override: str, value: str, reason: str
) -> None:
    store, issued = _mint(tmp_path)

    with pytest.raises(MachineIdentityError, match=reason):
        _verify(
            tmp_path,
            store,
            issued.token,
            expected_owner_principal_id=(
                value if override == "expected_owner_principal_id" else "principal_owner"
            ),
            expected_session_id=(value if override == "expected_session_id" else "sess_1"),
            expected_turn_id=(value if override == "expected_turn_id" else "turn_1"),
            expected_audience=(value if override == "expected_audience" else "tool_broker"),
        )


def test_expired_identity_is_rejected(tmp_path: Path) -> None:
    store, issued = _mint(tmp_path)

    with pytest.raises(MachineIdentityError, match="machine_identity_expired"):
        _verify(tmp_path, store, issued.token, now=NOW + timedelta(seconds=301))


def test_inactive_machine_principal_is_rejected(tmp_path: Path) -> None:
    store, issued = _mint(tmp_path)
    store.deactivate_principal(issued.claims.principal_id)

    with pytest.raises(MachineIdentityError, match="machine_identity_inactive_principal"):
        _verify(tmp_path, store, issued.token)


def test_same_live_turn_can_verify_the_same_identity_more_than_once(tmp_path: Path) -> None:
    store, issued = _mint(tmp_path)

    first = _verify(tmp_path, store, issued.token)
    second = _verify(tmp_path, store, issued.token)

    assert first.token_fingerprint == second.token_fingerprint


def test_private_seed_is_encrypted_and_never_returned_by_storage(tmp_path: Path) -> None:
    store, issued = _mint(tmp_path)
    row = store.get_machine_issuer_key(issued.claims.key_id)

    assert row is not None
    assert row["public_key"]
    assert row["private_key_encrypted"]
    assert row["private_key_encrypted"] != row["public_key"]
    identity = store.get_turn_machine_identity(issued.claims.principal_id)
    assert identity is not None
    assert "private_key_encrypted" not in identity


def test_concurrent_first_use_creates_one_active_workspace_issuer(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    _owner(store)

    def issue(index: int) -> str:
        local_store = SQLiteStore(tmp_path)
        return WorkspaceIdentityIssuer(tmp_path, local_store).mint(
            owner_principal_id="principal_owner",
            session_id="sess_1",
            turn_id=f"turn_{index}",
            role_ids=("assistant",),
            ttl_seconds=300,
            now=NOW,
        ).claims.key_id

    with ThreadPoolExecutor(max_workers=2) as pool:
        key_ids = list(pool.map(issue, range(2)))

    assert key_ids[0] == key_ids[1]
    assert len(store.list_active_machine_issuer_keys()) == 1
