"""ADD-27 GH-18, GH-20, GH-21, GH-22 — credentials by method, each used only when selected.

Fakes stand in for GitHub's ``/user`` endpoint and for the ``gh``, ``git`` and
``ssh`` programs; nothing here reaches the network or the host's own keychain.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from raiker.github.credentials import (
    METHOD_ENVIRONMENT,
    METHOD_GH_CLI,
    METHOD_OS_HELPER,
    METHOD_PAT,
    METHOD_SSH,
    CredentialMethodError,
    reset_verification_cache,
)
from raiker.github.http import GitHubHttp
from raiker.github.local_methods import GITHUB_HOST_KEYS, GhCli, OsCredentialHelper, SshKeys
from raiker.runtime.git_credential import RUNTIME_TOKEN_VAR, GitCredentialBroker, GitCredentialError
from raiker.storage.sqlite import SQLiteStore

OWNER = "principal_owner"
TOKENS = {
    "ghp_patToken000000000000000000000000000": (101, "octo"),
    "gho_ghCliTokenForOcto0000000000000000000": (101, "octo"),
    "gho_ghCliTokenForHubot000000000000000000": (202, "hubot"),
    "ghp_helperToken0000000000000000000000000": (101, "octo"),
}


class FakeGitHub:
    """``GET /user`` for the tokens above; 401 for anything else."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(
        self, method: str, url: str, headers: Mapping[str, str], body: bytes | None
    ) -> tuple[int, Mapping[str, str], bytes]:
        self.calls.append(url)
        token = headers.get("Authorization", "").removeprefix("Bearer ")
        if url == "https://api.github.com/user" and token in TOKENS:
            account_id, login = TOKENS[token]
            return 200, {"X-OAuth-Scopes": "repo"}, json.dumps({"id": account_id, "login": login}).encode()
        return 401, {}, b'{"message":"Bad credentials"}'


class FakePrograms:
    """`gh`, `git credential fill`, `ssh-keygen` and `ssh`, as the tests set them."""

    def __init__(self) -> None:
        self.gh_active = "octo"
        self.gh_tokens = {"octo": "gho_ghCliTokenForOcto0000000000000000000"}
        self.helper_answer = ("octo", "ghp_helperToken0000000000000000000000000")
        self.ssh_login = "octo"
        self.argv: list[list[str]] = []
        self.stdin: list[str | None] = []

    def __call__(
        self, argv: Sequence[str], stdin: str | None, env: dict[str, str], timeout: float
    ) -> tuple[int, str, str]:
        argv = list(argv)
        self.argv.append(argv)
        self.stdin.append(stdin)
        assert env.get("GIT_TERMINAL_PROMPT") == "0"
        assert not any(name.endswith("_TOKEN") for name in env)
        if argv[1:3] == ["auth", "status"]:
            lines = []
            for login in self.gh_tokens:
                lines.append(f"  ✓ Logged in to github.com account {login} (keyring)")
                lines.append(f"  - Active account: {'true' if login == self.gh_active else 'false'}")
            return 0, "github.com\n" + "\n".join(lines), ""
        if argv[1:3] == ["auth", "token"]:
            login = argv[argv.index("--user") + 1]
            token = self.gh_tokens.get(login)
            return (0, token + "\n", "") if token else (1, "", "no account")
        if "credential" in argv and argv[-1] == "fill":
            username, password = self.helper_answer
            return 0, f"protocol=https\nhost=github.com\nusername={username}\npassword={password}\n", ""
        if argv[:2] == ["ssh-keygen", "-lf"]:
            return 0, "256 SHA256:abcDEF123ghiJKL456mnoPQR789stuVWX012yzAB34 owner@host (ED25519)\n", ""
        if argv[0] == "ssh":
            return 1, "", f"Hi {self.ssh_login}! You've successfully authenticated, but GitHub does not provide shell access.\n"
        return 127, "", "not installed"


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RAIKER_GITHUB_TOKEN", raising=False)
    reset_verification_cache()


@pytest.fixture
def github() -> FakeGitHub:
    return FakeGitHub()


@pytest.fixture
def programs() -> FakePrograms:
    return FakePrograms()


def _broker(tmp_path: Path, github: FakeGitHub, programs: FakePrograms) -> GitCredentialBroker:
    return GitCredentialBroker(
        SQLiteStore(tmp_path), OWNER,
        http=GitHubHttp(github), gh=GhCli(programs, "gh"), helper=OsCredentialHelper(programs),
        ssh=SshKeys(programs, home=tmp_path),
    )


def test_a_token_stored_before_records_existed_becomes_a_selected_pat(
    tmp_path: Path, github: FakeGitHub, programs: FakePrograms
) -> None:
    store = SQLiteStore(tmp_path)
    from raiker.runtime.connector_ecosystem import ConnectorVault

    ConnectorVault(store).put(OWNER, "github_token", {"token": "ghp_patToken000000000000000000000000000"})
    broker = _broker(tmp_path, github, programs)
    selected = broker.selected_credential()
    assert selected is not None and selected["method"] == METHOD_PAT
    assert selected["status"] == "unverified" and selected["secret_ref"] == "github_token"
    assert broker.token_source() == "vault"


def test_checking_a_pat_records_its_account(
    tmp_path: Path, github: FakeGitHub, programs: FakePrograms
) -> None:
    broker = _broker(tmp_path, github, programs)
    broker.store_token("ghp_patToken000000000000000000000000000")
    row = broker.methods.check(broker.status()["credential_id"] or "")
    assert row["account_id"] == "101" and row["account_login"] == "octo"
    assert row["status"] == "active" and row["permissions_json"] == {"scopes": ["repo"]}


def test_a_rejected_token_is_marked_revoked(
    tmp_path: Path, github: FakeGitHub, programs: FakePrograms
) -> None:
    broker = _broker(tmp_path, github, programs)
    broker.store_token("ghp_revokedAtGitHub00000000000000000000")
    with pytest.raises(CredentialMethodError) as caught:
        broker.methods.check(broker.status()["credential_id"] or "")
    assert caught.value.reason == "github_credential_rejected"
    assert broker.token_configured() is False


def test_the_environment_token_can_be_switched_off(
    tmp_path: Path, github: FakeGitHub, programs: FakePrograms, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAIKER_GITHUB_TOKEN", "ghp_patToken000000000000000000000000000")
    broker = _broker(tmp_path, github, programs)
    selected = broker.selected_credential()
    assert selected is not None and selected["method"] == METHOD_ENVIRONMENT
    broker.methods.remove(selected["credential_id"])
    # The variable is still set; Raiker no longer uses it.
    assert broker.token_configured() is False


def test_gh_discovery_reads_no_token(tmp_path: Path, programs: FakePrograms) -> None:
    accounts = GhCli(programs, "gh").accounts()
    assert [(a.login, a.active) for a in accounts] == [("octo", True)]
    assert all(argv[1:3] != ["auth", "token"] for argv in programs.argv)


def test_gh_cli_sign_in_is_used_only_after_selection_and_checked_every_lend(
    tmp_path: Path, github: FakeGitHub, programs: FakePrograms
) -> None:
    broker = _broker(tmp_path, github, programs)
    assert broker.token_configured() is False  # detected is not selected
    row = broker.methods.add_gh_cli("octo")
    assert row["method"] == METHOD_GH_CLI and row["account_id"] == "101" and row["selected"]
    # Nothing of the token is stored.
    assert "gho_" not in json.dumps(row)
    broker.grant("once")
    with broker.lend(operation="push") as environment:
        assert environment[RUNTIME_TOKEN_VAR] == "gho_ghCliTokenForOcto0000000000000000000"


def test_gh_answering_for_another_account_is_refused(
    tmp_path: Path, github: FakeGitHub, programs: FakePrograms
) -> None:
    broker = _broker(tmp_path, github, programs)
    broker.methods.add_gh_cli("octo")
    broker.grant("once")
    # gh now holds a token for someone else under the same login name.
    programs.gh_tokens["octo"] = "gho_ghCliTokenForHubot000000000000000000"
    reset_verification_cache()
    with pytest.raises(GitCredentialError) as caught, broker.lend(operation="push"):
        pass
    assert caught.value.reason == "git_account_mismatch"


def test_a_credential_manager_entry_for_another_user_is_refused(
    tmp_path: Path, github: FakeGitHub, programs: FakePrograms
) -> None:
    broker = _broker(tmp_path, github, programs)
    programs.helper_answer = ("hubot", "ghp_helperToken0000000000000000000000000")
    with pytest.raises(CredentialMethodError) as caught:
        broker.methods.add_os_helper("octo")
    assert caught.value.reason == "git_account_mismatch"
    programs.helper_answer = ("octo", "ghp_helperToken0000000000000000000000000")
    row = broker.methods.add_os_helper("octo")
    assert row["method"] == METHOD_OS_HELPER
    # The helper is asked for exactly the selected user.
    assert any(text and "username=octo" in text for text in programs.stdin)


def test_an_ssh_key_lends_a_pinned_identity_and_no_token(
    tmp_path: Path, github: FakeGitHub, programs: FakePrograms
) -> None:
    key = tmp_path / "id_ed25519"
    key.write_text("PRIVATE KEY MATERIAL", encoding="utf-8")
    broker = _broker(tmp_path, github, programs)
    row = broker.methods.add_ssh(str(key))
    assert row["method"] == METHOD_SSH and row["account_login"] == "octo"
    assert row["selector"].startswith("SHA256:")
    broker.grant("once")
    with broker.lend(operation="push") as environment:
        command = environment["GIT_SSH_COMMAND"]
        assert RUNTIME_TOKEN_VAR not in environment
    for part in ("IdentitiesOnly=yes", "IdentityAgent=none", "StrictHostKeyChecking=yes", "BatchMode=yes"):
        assert part in command
    assert str(key) in command
    known = (tmp_path / ".raiker" / "github_known_hosts").read_text(encoding="utf-8")
    assert all(host_key in known for host_key in GITHUB_HOST_KEYS)
    # The key's content never left the file.
    assert "PRIVATE KEY MATERIAL" not in json.dumps(row) + command


def test_a_grant_made_for_one_credential_does_not_lend_another(
    tmp_path: Path, github: FakeGitHub, programs: FakePrograms
) -> None:
    broker = _broker(tmp_path, github, programs)
    broker.store_token("ghp_patToken000000000000000000000000000")
    pat = broker.methods.selected() or {}
    broker.methods.check(str(pat["credential_id"]))  # the same account as the CLI's: octo
    broker.grant("once")
    broker.methods.add_gh_cli("octo")  # now selected
    with pytest.raises(GitCredentialError) as caught, broker.lend(operation="push"):
        pass
    assert caught.value.reason == "git_grant_other_credential"


def test_switching_to_another_account_withdraws_every_grant(
    tmp_path: Path, github: FakeGitHub, programs: FakePrograms
) -> None:
    """§6.4 — nothing lent for one account may run as another, even unasked."""
    broker = _broker(tmp_path, github, programs)
    broker.store_token("ghp_patToken000000000000000000000000000")  # never checked: no account yet
    broker.grant("once")
    broker.methods.add_gh_cli("octo")
    assert broker.live_grant() is None


def test_removing_a_credential_withdraws_every_grant(
    tmp_path: Path, github: FakeGitHub, programs: FakePrograms
) -> None:
    broker = _broker(tmp_path, github, programs)
    row = broker.methods.add_gh_cli("octo")
    broker.grant("once")
    broker.methods.remove(row["credential_id"])
    assert broker.live_grant() is None
    assert broker.token_configured() is False


def test_status_names_the_method_and_account_never_the_secret(
    tmp_path: Path, github: FakeGitHub, programs: FakePrograms
) -> None:
    broker = _broker(tmp_path, github, programs)
    broker.methods.add_gh_cli("octo")
    status: dict[str, Any] = dict(broker.status())
    assert status["credential_method"] == METHOD_GH_CLI and status["account_login"] == "octo"
    assert "gho_" not in json.dumps(status)
