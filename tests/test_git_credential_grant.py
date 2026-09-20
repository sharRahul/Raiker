"""RAIKER-2022 — the git credential is lent, not held.

The token used to live in the host's environment, which meant every child
process inherited it and the only way to withdraw it was a restart. These cover
the three properties that replace that: a push needs a grant, a grant expires,
and the value never reaches anything that gets written down.
"""
from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from raiker.context.redaction import redact_text, registered_secret_count
from raiker.runtime.git_credential import (
    CREDENTIAL_HOSTS,
    GRANT_SECONDS,
    RUNTIME_TOKEN_VAR,
    GitCredentialBroker,
    GitCredentialError,
    credential_config,
    credential_helper,
    grant_expiry,
)
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.git import GIT_PUSH_CREDENTIAL_HOSTS

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


# ── Which host the credential answers ────────────────────────────────────────
#
# The helper git used to run was three words long: it echoed the username and
# the token for whatever git asked about. Git asks about the URL it is
# *currently* contacting, which is not always the URL the remote names — a
# redirect, an `insteadOf` rewrite or a submodule sends it elsewhere. These run
# the real `git credential fill` against the real helper, because a shell
# function is only correct in the shell that runs it.


def _fill(args: list[str], host: str) -> tuple[int, str]:
    """Ask git for the credential it would use for *host*."""
    environment = dict(
        os.environ,
        RAIKER_GIT_PUSH_TOKEN=TOKEN,
        GIT_TERMINAL_PROMPT="0",
        GIT_ASKPASS="",
        SSH_ASKPASS="",
    )
    proc = subprocess.run(
        ["git", *args, "credential", "fill"],
        input=f"protocol=https\nhost={host}\n\n",
        text=True, capture_output=True, env=environment, timeout=30, check=False,
    )
    return proc.returncode, proc.stdout


def test_the_helper_answers_the_host_the_credential_belongs_to() -> None:
    args = [item for value in credential_config("RAIKER_GIT_PUSH_TOKEN") for item in ("-c", value)]
    code, output = _fill(args, "github.com")
    assert code == 0
    assert f"password={TOKEN}" in output


@pytest.mark.parametrize("host", ["evil.example.com", "github.com.evil.example.com"])
def test_the_helper_says_nothing_to_any_other_host(host: str) -> None:
    args = [item for value in credential_config("RAIKER_GIT_PUSH_TOKEN") for item in ("-c", value)]
    code, output = _fill(args, host)
    assert TOKEN not in output
    assert code != 0


def test_the_host_check_holds_even_when_the_helper_is_installed_unscoped() -> None:
    """The URL scoping and the in-helper check are two answers, not one.

    A caller that installs the helper as a plain `credential.helper` loses the
    first; the second is inside the child and cannot be lost by a caller at all.
    """
    helper = credential_helper("RAIKER_GIT_PUSH_TOKEN")
    args = ["-c", "credential.helper=", "-c", f"credential.helper={helper}"]
    assert _fill(args, "github.com")[0] == 0
    code, output = _fill(args, "evil.example.com")
    assert TOKEN not in output
    assert code != 0


def test_the_helper_refuses_to_write_anything_back() -> None:
    """Only `get` is answered, so nothing git caches can write through it."""
    helper = credential_helper("RAIKER_GIT_PUSH_TOKEN")
    assert '[ "$1" = get ] || exit 0' in helper


def test_the_loan_installs_the_helper_against_the_credentials_hosts_only(
    broker: GitCredentialBroker,
) -> None:
    broker.store_token(TOKEN)
    broker.grant("session")
    with broker.lend() as environment:
        count = int(environment["GIT_CONFIG_COUNT"])
        keys = [environment[f"GIT_CONFIG_KEY_{index}"] for index in range(count)]
    # The first entry is what drops this machine's own helpers; every other one
    # names a host rather than applying to all of them.
    assert keys[0] == "credential.helper"
    assert keys[1:] == [f"credential.https://{host}.helper" for host in CREDENTIAL_HOSTS]


def test_the_push_path_and_the_helper_agree_on_the_hosts() -> None:
    assert frozenset(CREDENTIAL_HOSTS) == GIT_PUSH_CREDENTIAL_HOSTS


def test_the_loans_own_environment_answers_github_and_nothing_else(
    broker: GitCredentialBroker,
) -> None:
    """The mapping a caller passes to a child, driven through real git.

    The two tests above prove the helper and the config separately. This proves
    the thing a caller actually holds: `lend()` yields an environment, and a
    child given exactly that environment gets the credential for GitHub and
    nothing at all for anywhere else.
    """
    broker.store_token(TOKEN)
    broker.grant("session")
    with broker.lend() as loan:
        environment = dict(
            os.environ,
            **loan,
            GIT_TERMINAL_PROMPT="0",
            GIT_ASKPASS="",
            SSH_ASKPASS="",
        )
        answers = {}
        for host in ("github.com", "evil.example.com"):
            proc = subprocess.run(
                ["git", "credential", "fill"],
                input=f"protocol=https\nhost={host}\n\n",
                text=True, capture_output=True, env=environment, timeout=30, check=False,
            )
            answers[host] = proc.stdout
    assert f"password={TOKEN}" in answers["github.com"]
    assert TOKEN not in answers["evil.example.com"]
