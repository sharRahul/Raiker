"""RAIKER-2022 — the git credential is lent, not held.

The token used to live in the host's environment, which meant every child
process inherited it and the only way to withdraw it was a restart. These cover
the three properties that replace that: a push needs a grant, a grant expires,
and the value never reaches anything that gets written down.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from raiker.context.redaction import redact_text, registered_secret_count
from raiker.runtime.git_credential import (
    GRANT_SECONDS,
    RUNTIME_TOKEN_VAR,
    GitCredentialBroker,
    GitCredentialError,
    grant_expiry,
)
from raiker.storage.sqlite import SQLiteStore

TOKEN = "ghp_A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"


@pytest.fixture()
def broker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> GitCredentialBroker:
    monkeypatch.delenv("RAIKER_GITHUB_TOKEN", raising=False)
    return GitCredentialBroker(SQLiteStore(tmp_path), "principal_owner")


# ── Storage ──────────────────────────────────────────────────────────────────


def test_a_fresh_workspace_holds_no_credential(broker: GitCredentialBroker) -> None:
    status = broker.status()
    assert status["credential_configured"] is False
    assert status["credential_source"] == "none"


def test_a_stored_token_is_reported_but_never_returned(broker: GitCredentialBroker) -> None:
    broker.store_token(TOKEN)
    status = broker.status()
    assert status["credential_configured"] is True
    assert status["credential_source"] == "vault"
    assert TOKEN not in str(status)


def test_an_empty_token_is_refused(broker: GitCredentialBroker) -> None:
    with pytest.raises(GitCredentialError):
        broker.store_token("   ")


def test_forgetting_the_token_revokes_what_depended_on_it(
    broker: GitCredentialBroker,
) -> None:
    broker.store_token(TOKEN)
    broker.grant("session")
    broker.forget_token()
    assert broker.active_grant() is None
    assert broker.status()["credential_configured"] is False


def test_the_environment_still_works_for_a_host_configured_the_old_way(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """This change must not take a working deployment away."""
    monkeypatch.setenv("RAIKER_GITHUB_TOKEN", TOKEN)
    status = GitCredentialBroker(SQLiteStore(tmp_path), "principal_owner").status()
    assert status["credential_configured"] is True
    assert status["credential_source"] == "environment"


# ── Grants ───────────────────────────────────────────────────────────────────


def test_a_grant_needs_a_stored_token(broker: GitCredentialBroker) -> None:
    with pytest.raises(GitCredentialError) as caught:
        broker.grant("once")
    assert caught.value.reason == "git_token_not_configured"


def test_an_unknown_scope_is_refused(broker: GitCredentialBroker) -> None:
    broker.store_token(TOKEN)
    with pytest.raises(GitCredentialError) as caught:
        broker.grant("forever")
    assert caught.value.reason == "git_grant_scope_invalid"


@pytest.mark.parametrize("scope", ["once", "session"])
def test_each_scope_can_be_granted(broker: GitCredentialBroker, scope: str) -> None:
    broker.store_token(TOKEN)
    grant = broker.grant(scope)
    assert grant.scope == scope
    assert broker.active_grant() is not None


def test_a_session_grant_does_not_carry_into_another_chat(
    broker: GitCredentialBroker,
) -> None:
    broker.store_token(TOKEN)
    broker.grant("session", session_id="sess_a")
    assert broker.active_grant(session_id="sess_a") is not None
    assert broker.active_grant(session_id="sess_b") is None


def test_a_new_grant_supersedes_the_last_one(broker: GitCredentialBroker) -> None:
    """Two live grants would mean the owner cannot tell which is in force."""
    broker.store_token(TOKEN)
    first = broker.grant("once")
    second = broker.grant("session")
    active = broker.active_grant()
    assert active is not None
    assert active.grant_id == second.grant_id != first.grant_id


def test_an_expired_grant_authorises_nothing(
    broker: GitCredentialBroker, tmp_path: Path
) -> None:
    """Expiry is evaluated on read, so it lapses whether or not anything ran."""
    broker.store_token(TOKEN)
    past = (
        (datetime.now(UTC) - timedelta(hours=2)).replace(microsecond=0)
        .isoformat().replace("+00:00", "Z")
    )
    broker._store.create_git_credential_grant(  # noqa: SLF001 — the clock is the subject
        principal_id="principal_owner", scope="session", expires_at=past
    )
    assert broker.active_grant() is None


def test_revoking_withdraws_the_approval_but_keeps_the_token(
    broker: GitCredentialBroker,
) -> None:
    broker.store_token(TOKEN)
    broker.grant("session")
    broker.revoke()
    assert broker.active_grant() is None
    assert broker.status()["credential_configured"] is True


def test_a_session_grant_lasts_longer_than_a_single_use_one() -> None:
    assert GRANT_SECONDS["session"] > GRANT_SECONDS["once"]
    assert grant_expiry("once") < grant_expiry("session")


# ── Lending ──────────────────────────────────────────────────────────────────


def test_lending_without_a_grant_is_refused(broker: GitCredentialBroker) -> None:
    broker.store_token(TOKEN)
    with pytest.raises(GitCredentialError) as caught, broker.lend():
        pass
    assert caught.value.reason == "git_grant_required"


def test_the_loan_carries_the_token_only_inside_the_block(
    broker: GitCredentialBroker,
) -> None:
    broker.store_token(TOKEN)
    broker.grant("session")
    with broker.lend() as environment:
        assert environment[RUNTIME_TOKEN_VAR] == TOKEN
        # Registered while it is out, so nothing captured now can carry it.
        assert registered_secret_count() >= 1
        assert TOKEN not in redact_text(f"remote: rejected {TOKEN}")[0]
    assert registered_secret_count() == 0


def test_a_one_shot_grant_is_spent_by_its_use(broker: GitCredentialBroker) -> None:
    broker.store_token(TOKEN)
    broker.grant("once")
    with broker.lend():
        pass
    assert broker.active_grant() is None


def test_a_session_grant_survives_a_use(broker: GitCredentialBroker) -> None:
    broker.store_token(TOKEN)
    broker.grant("session")
    with broker.lend():
        pass
    active = broker.active_grant()
    assert active is not None
    assert active.uses == 1


def test_the_loan_ends_even_when_the_command_fails(broker: GitCredentialBroker) -> None:
    """A push that raises must not leave the credential registered."""
    broker.store_token(TOKEN)
    broker.grant("once")
    with pytest.raises(RuntimeError), broker.lend():
        raise RuntimeError("git exploded")
    assert registered_secret_count() == 0
    assert broker.active_grant() is None
