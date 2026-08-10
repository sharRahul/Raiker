"""Identity binding for delegated subagent results (BUG-78)."""
from __future__ import annotations

from pathlib import Path

import pytest

from raiker.agents.delegation import (
    DelegationError,
    result_digest,
    sign_delegation,
    verify_delegation,
)
from raiker.runtime.identity.lifecycle import TurnMachineIdentityLifecycle
from raiker.storage.sqlite import SQLiteStore

OWNER = "local_user"
SESSION = "sess_delegation"
PARENT_TURN = "turn_parent"
CONTENT = "[UNTRUSTED SUBAGENT FINDINGS]\nfound three call sites"


def _spawn(tmp_path: Path) -> tuple[SQLiteStore, dict[str, str]]:
    """Mint a parent and a child identity the way `SubagentRunner` does."""
    store = SQLiteStore(tmp_path)
    lifecycle = TurnMachineIdentityLifecycle(tmp_path, store)
    parent = lifecycle.start(
        owner_principal_id=OWNER, session_id=SESSION, turn_id=PARENT_TURN,
        role_ids=("assistant",),
    )
    child_turn = f"{PARENT_TURN}:subagent:sba_1"
    child = lifecycle.start(
        owner_principal_id=OWNER, session_id=SESSION, turn_id=child_turn,
        role_ids=("assistant",), principal_id="sba_1",
        parent_principal_id=parent.claims.principal_id,
    )
    # The runner deactivates the child as it finishes; verification must still
    # accept the result, because otherwise it would reject every result.
    lifecycle.finish(child)
    return store, {
        "spawn_principal_id": child.claims.principal_id,
        "parent_principal_id": parent.claims.principal_id,
        "spawn_turn_id": child_turn,
        "subject": child.claims.subject,
    }


def _sign(tmp_path: Path, store: SQLiteStore, spawn: dict[str, str], content: str) -> str:
    return sign_delegation(
        tmp_path, store, subagent_id="sba_1",
        spawn_principal_id=spawn["spawn_principal_id"],
        parent_principal_id=spawn["parent_principal_id"],
        owner_principal_id=OWNER, session_id=SESSION, turn_id=PARENT_TURN,
        spawn_turn_id=spawn["spawn_turn_id"], subject=spawn["subject"], content=content,
    )


def test_a_delegated_result_verifies_against_the_spawn_that_produced_it(
    tmp_path: Path,
) -> None:
    store, spawn = _spawn(tmp_path)
    token = _sign(tmp_path, store, spawn, CONTENT)

    claims = verify_delegation(
        store, token,
        expected_owner_principal_id=OWNER, expected_session_id=SESSION,
        expected_turn_id=PARENT_TURN, expected_content=CONTENT,
    )

    assert claims.subagent_id == "sba_1"
    assert claims.spawn_principal_id == spawn["spawn_principal_id"]
    assert claims.result_digest == result_digest(CONTENT)


def test_a_result_swapped_for_another_fails_verification(tmp_path: Path) -> None:
    """The digest is what binds the attestation to *this* result."""
    store, spawn = _spawn(tmp_path)
    token = _sign(tmp_path, store, spawn, CONTENT)

    with pytest.raises(DelegationError) as raised:
        verify_delegation(
            store, token,
            expected_owner_principal_id=OWNER, expected_session_id=SESSION,
            expected_turn_id=PARENT_TURN,
            expected_content="[UNTRUSTED SUBAGENT FINDINGS]\nsomething else entirely",
        )
    assert raised.value.reason_code == "delegation_result_mismatch"


def test_a_tampered_attestation_fails_closed(tmp_path: Path) -> None:
    store, spawn = _spawn(tmp_path)
    token = _sign(tmp_path, store, spawn, CONTENT)
    payload, signature = token.split(".")
    forged = f"{payload}.{'A' * len(signature)}"

    with pytest.raises(DelegationError) as raised:
        verify_delegation(
            store, forged,
            expected_owner_principal_id=OWNER, expected_session_id=SESSION,
            expected_turn_id=PARENT_TURN, expected_content=CONTENT,
        )
    assert raised.value.reason_code in {
        "delegation_invalid_signature",
        "delegation_attestation_malformed",
    }


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("expected_owner_principal_id", "someone-else", "delegation_owner_mismatch"),
        ("expected_session_id", "sess_other", "delegation_session_mismatch"),
        ("expected_turn_id", "turn_other", "delegation_turn_mismatch"),
    ],
)
def test_a_result_from_another_turn_is_refused(
    tmp_path: Path, field: str, value: str, expected: str
) -> None:
    store, spawn = _spawn(tmp_path)
    token = _sign(tmp_path, store, spawn, CONTENT)
    kwargs = {
        "expected_owner_principal_id": OWNER,
        "expected_session_id": SESSION,
        "expected_turn_id": PARENT_TURN,
        "expected_content": CONTENT,
        field: value,
    }

    with pytest.raises(DelegationError) as raised:
        verify_delegation(store, token, **kwargs)  # type: ignore[arg-type]
    assert raised.value.reason_code == expected


def test_a_malformed_token_is_refused_rather_than_parsed(tmp_path: Path) -> None:
    store, _spawn_identity = _spawn(tmp_path)
    for bad in ("", "not-a-token", "a.b.c", "eyJ9.???"):
        with pytest.raises(DelegationError):
            verify_delegation(
                store, bad,
                expected_owner_principal_id=OWNER, expected_session_id=SESSION,
                expected_turn_id=PARENT_TURN, expected_content=CONTENT,
            )


def test_the_attestation_carries_no_findings(tmp_path: Path) -> None:
    """Metadata and a digest only — the digest is one-way."""
    store, spawn = _spawn(tmp_path)
    token = _sign(tmp_path, store, spawn, CONTENT)

    assert "found three call sites" not in token
    claims = verify_delegation(
        store, token,
        expected_owner_principal_id=OWNER, expected_session_id=SESSION,
        expected_turn_id=PARENT_TURN, expected_content=CONTENT,
    )
    assert "found three call sites" not in str(claims.to_dict())
