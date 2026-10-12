"""Credentials the owner already has on this machine, used only when selected.

Three sources (ADD-27 GH-20, GH-21, GH-22): the GitHub CLI's sign-in, an entry
in the operating system's credential manager, and an SSH key. Each has the same
two halves, kept apart on purpose:

* **Discovery** says what exists without reading a secret — the accounts
  ``gh`` reports, whether a credential helper is configured, which public keys
  are in ``~/.ssh`` and their fingerprints. Discovery is not consent.
* **Reading** happens only for a credential the owner selected, only when the
  broker is about to lend it, and the account it belongs to is checked against
  the one the owner selected every time.

Every command runs without a shell, without a terminal to prompt on, with a
timeout, and with an environment that carries no other credential. A command
that would prompt or is not installed is "not available here", never a hang.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

#: (argv, stdin, env, timeout) → (returncode, stdout, stderr). Tests pass their own.
Runner = Callable[[Sequence[str], str | None, dict[str, str], float], tuple[int, str, str]]

TIMEOUT = 15.0

#: The variables a local credential command may see. ``HOME`` and the config
#: directories are where gh and git keep their state; nothing else is needed.
_KEPT = (
    "PATH", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME",
    "XDG_DATA_HOME", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS", "GH_CONFIG_DIR",
    "SYSTEMROOT", "LANG", "LC_ALL", "TMPDIR", "TEMP", "TMP",
)


def credential_command_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {name: os.environ[name] for name in _KEPT if os.environ.get(name)}
    env.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "never",
            "GH_PROMPT_DISABLED": "1",
            "GH_NO_UPDATE_NOTIFIER": "1",
        }
    )
    env.update(extra or {})
    return env


def subprocess_runner(
    argv: Sequence[str], stdin: str | None, env: dict[str, str], timeout: float
) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(  # noqa: S603 — argv is built here, never by a model
            list(argv), input=stdin, capture_output=True, text=True, timeout=timeout,
            env=env, check=False,
        )
    except FileNotFoundError:
        return 127, "", "not installed"
    except subprocess.TimeoutExpired:
        return 124, "", "timed out"
    return proc.returncode, proc.stdout, proc.stderr


class LocalCredentialError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


# ── GitHub CLI ──────────────────────────────────────────────────────────

_GH_ACCOUNT = re.compile(r"Logged in to github\.com (?:account|as) ([A-Za-z0-9-]+)")
_GH_ACTIVE = re.compile(r"Active account:\s*(true|false)", re.IGNORECASE)


@dataclass(frozen=True)
class GhAccount:
    login: str
    active: bool


class GhCli:
    """The GitHub CLI's own sign-ins for github.com."""

    def __init__(self, runner: Runner | None = None, executable: str | None = None) -> None:
        self._run = runner or subprocess_runner
        self._gh = executable or shutil.which("gh") or "gh"

    def accounts(self) -> list[GhAccount]:
        """The accounts ``gh auth status`` reports. Reads no token."""
        code, out, err = self._run(
            [self._gh, "auth", "status", "--hostname", "github.com"], None,
            credential_command_environment(), TIMEOUT,
        )
        if code == 127:
            return []
        text = f"{out}\n{err}"
        found: list[GhAccount] = []
        lines = text.splitlines()
        for index, line in enumerate(lines):
            match = _GH_ACCOUNT.search(line)
            if not match:
                continue
            active = True
            for follow in lines[index + 1:index + 6]:
                state = _GH_ACTIVE.search(follow)
                if state:
                    active = state.group(1).lower() == "true"
                    break
                if _GH_ACCOUNT.search(follow):
                    break
            found.append(GhAccount(match.group(1), active))
        return found

    def token(self, login: str) -> str:
        """The token gh holds for *login* — read only for a selected credential."""
        if not re.fullmatch(r"[A-Za-z0-9-]{1,39}", login or ""):
            raise LocalCredentialError("gh_cli_login_invalid")
        code, out, _err = self._run(
            [self._gh, "auth", "token", "--hostname", "github.com", "--user", login], None,
            credential_command_environment(), TIMEOUT,
        )
        if code == 127:
            raise LocalCredentialError("gh_cli_not_installed")
        value = out.strip()
        if code != 0 or not value or "\n" in value:
            raise LocalCredentialError("gh_cli_account_not_signed_in")
        return value


# ── OS credential manager ───────────────────────────────────────────────


class OsCredentialHelper:
    """The credential helper git is configured with, asked for github.com only."""

    def __init__(self, runner: Runner | None = None, git: str = "git") -> None:
        self._run = runner or subprocess_runner
        self._git = git

    def helpers(self) -> list[str]:
        """The configured helper names. Reads no credential."""
        code, out, _err = self._run(
            [self._git, "config", "--get-all", "credential.helper"], None,
            credential_command_environment(), TIMEOUT,
        )
        if code != 0:
            return []
        return [line.strip() for line in out.splitlines() if line.strip()]

    def token(self, username: str) -> str:
        """The password the helper holds for ``https://<username>@github.com``.

        The helper is asked for exactly this username. One that answers for
        another — which is what a keychain does when the account signed in last
        is someone else — is refused, not used.
        """
        if not re.fullmatch(r"[A-Za-z0-9-]{1,39}", username or ""):
            raise LocalCredentialError("os_helper_username_invalid")
        request = f"protocol=https\nhost=github.com\nusername={username}\n\n"
        code, out, _err = self._run(
            [self._git, "-c", "credential.interactive=never", "credential", "fill"], request,
            credential_command_environment(), TIMEOUT,
        )
        if code == 127:
            raise LocalCredentialError("git_not_installed")
        fields = dict(
            line.split("=", 1) for line in out.splitlines() if "=" in line
        )
        if code != 0 or not fields.get("password"):
            raise LocalCredentialError("os_helper_no_credential")
        if fields.get("username", username) != username:
            raise LocalCredentialError("git_account_mismatch")
        return fields["password"]


# ── SSH ──────────────────────────────────────────────────────────────────

#: GitHub's published SSH host keys for github.com, pinned here rather than
#: learned on first connection. A connection whose host key is not one of these
#: is refused. `ssh.github.com` (port 443) presents the same keys.
GITHUB_HOST_KEYS = (
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl",
    "ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBEmKSENjQEezOmxkZMy7opKgwFB9nkt5YRrYMjNuG5N87uRgg6CLrbo5wAdT/y6v0mKV0U2w0WZ2YB/++Tpockg=",
    "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQCj7ndNxQowgcQnjshcLrqPEiiphnt+VTTvDP6mHBL9j1aNUkY4Ue1gvwnGLVlOhGeYrnZaMgRK6+PKCUXaDbC7qtbW8gIkhL7aGCsOr/C56SJMy/BCZfxd1nWzAOxSDPgVsmerOBYfNqltV9/hWCqBywINIR+5dIg6JTJ72pcEpEjcYgXkE2YEFXV1JHnsKgbLWNlhScqb2UmyRkQyytRLtL+38TGxkxCflmO+5Z8CSSNY7GidjMIZ7Q4zMjA2n1nGrlTDkzwDCsw+wqFPGQA179cnfGWOWRVruj16z6XyvxvjJwbz0wQZ75XK5tKSb7FNyeIEs4TT4jk+S4dhPeAUC5y+bDYirYgM4GC7uEnztnZyaVWQ7B381AK4Qdrwt51ZqExKbQpTUNn+EjqoTwvqNj4kqx5QUCI0ThS/YkOxJCXmPUWZbhjpCg56i+2aB6CmK2JGhn57K5mj0MNdBXA4/WnwH6XoPWJzK5Nyu2zB3nAZp+S5hpQs+p1vN1/wsjk=",
)


def known_hosts_text() -> str:
    lines = []
    for key in GITHUB_HOST_KEYS:
        lines.append(f"github.com {key}")
        lines.append(f"[ssh.github.com]:443 {key}")
    return "\n".join(lines) + "\n"


def write_known_hosts(workspace_root: str | Path) -> Path:
    """Raiker's own known_hosts for GitHub, beside the workspace's other state."""
    path = Path(workspace_root).resolve() / ".raiker" / "github_known_hosts"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = known_hosts_text()
    if not path.is_file() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")
    return path


_FINGERPRINT = re.compile(r"^\d+\s+(SHA256:[A-Za-z0-9+/=]+)\s")
_HI = re.compile(r"Hi ([A-Za-z0-9-]+)! You've successfully authenticated")


@dataclass(frozen=True)
class SshKey:
    path: str
    fingerprint: str


def ssh_argv(key_path: str, known_hosts: Path) -> list[str]:
    """``ssh`` for one selected key, and nothing else.

    No agent, no other identity file, no config file, the pinned host keys only,
    no proxy and no prompt.
    """
    null = "NUL" if os.name == "nt" else "/dev/null"
    return [
        "ssh", "-F", null,
        "-o", "IdentitiesOnly=yes", "-o", "IdentityAgent=none",
        "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
        "-o", f"UserKnownHostsFile={known_hosts}",
        "-o", f"GlobalKnownHostsFile={null}",
        "-o", "ProxyCommand=none", "-o", "ProxyJump=none",
        "-i", key_path,
    ]


def ssh_command(key_path: str, known_hosts: Path) -> str:
    """The same, as the ``GIT_SSH_COMMAND`` git runs through its shell."""
    import shlex

    return shlex.join(ssh_argv(key_path, known_hosts))


class SshKeys:
    def __init__(self, runner: Runner | None = None, home: str | Path | None = None) -> None:
        self._run = runner or subprocess_runner
        self._home = Path(home) if home else Path.home()

    def discover(self) -> list[SshKey]:
        """Private keys in ``~/.ssh`` that have a ``.pub`` beside them. Reads no private key."""
        folder = self._home / ".ssh"
        if not folder.is_dir():
            return []
        found: list[SshKey] = []
        for public in sorted(folder.glob("*.pub")):
            private = public.with_suffix("")
            if not private.is_file():
                continue
            fingerprint = self.fingerprint(str(public))
            if fingerprint:
                found.append(SshKey(str(private), fingerprint))
        return found

    def fingerprint(self, key_path: str) -> str:
        code, out, _err = self._run(
            ["ssh-keygen", "-lf", key_path], None, credential_command_environment(), TIMEOUT
        )
        match = _FINGERPRINT.match(out.strip()) if code == 0 else None
        return match.group(1) if match else ""

    def account(self, key_path: str, known_hosts: Path) -> str:
        """The GitHub login the key authenticates as, asked of github.com itself."""
        argv = [*ssh_argv(key_path, known_hosts), "-T", "git@github.com"]
        code, out, err = self._run(argv, None, credential_command_environment(), TIMEOUT)
        match = _HI.search(f"{out}\n{err}")
        if match:
            return match.group(1)
        if code == 127:
            raise LocalCredentialError("ssh_not_installed")
        if "Host key verification failed" in err:
            raise LocalCredentialError("ssh_host_key_mismatch")
        raise LocalCredentialError("ssh_key_not_accepted")
