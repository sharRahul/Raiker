"""ADD-27 GH-24 — a local git command inherits no credential and runs no fsmonitor."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from raiker.tools.git import local_git_environment, run_git


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for key in [name for name in os.environ if name.startswith("GIT_CONFIG")]:
        monkeypatch.delenv(key, raising=False)
    _git(tmp_path, "init", "--initial-branch=main", ".")
    _git(tmp_path, "config", "user.name", "T")
    _git(tmp_path, "config", "user.email", "t@example.com")
    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    _git(tmp_path, "add", "a.txt")
    _git(tmp_path, "commit", "-m", "a")
    return tmp_path


def test_credentials_are_dropped_and_home_is_kept() -> None:
    env = local_git_environment({
        "HOME": "/home/owner", "PATH": "/usr/bin", "RAIKER_GITHUB_TOKEN": "ghp_x",
        "GITHUB_TOKEN": "x", "AWS_SECRET_ACCESS_KEY": "x", "SSH_AUTH_SOCK": "/tmp/agent",
        "OPENAI_API_KEY": "x", "GIT_ASKPASS": "/bin/askpass", "LANG": "C.UTF-8",
    })
    assert env["HOME"] == "/home/owner" and env["PATH"] == "/usr/bin" and env["LANG"] == "C.UTF-8"
    for name in ("RAIKER_GITHUB_TOKEN", "GITHUB_TOKEN", "AWS_SECRET_ACCESS_KEY",
                 "SSH_AUTH_SOCK", "OPENAI_API_KEY", "GIT_ASKPASS"):
        assert name not in env
    assert env["GIT_TERMINAL_PROMPT"] == "0"


def test_a_repository_fsmonitor_does_not_run_on_status(repo: Path) -> None:
    marker = repo.parent / "fsmonitor-ran"
    script = repo.parent / "monitor.py"
    script.write_text(
        f"import pathlib; pathlib.Path({str(marker)!r}).write_text('ran')\n", encoding="utf-8"
    )
    _git(repo, "config", "core.fsmonitor", f"{sys.executable} {script}")
    result = run_git(repo, "status")
    assert result["status"] == "success"
    assert not marker.exists()


def test_status_does_not_see_the_hosts_token(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A git child (here an external diff driver) reads the environment it was given."""
    seen = repo.parent / "seen-env"
    driver = repo.parent / "driver.py"
    driver.write_text(
        "import os, pathlib, sys\n"
        f"pathlib.Path({str(seen)!r}).write_text(os.environ.get('RAIKER_GITHUB_TOKEN', 'absent'))\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("RAIKER_GITHUB_TOKEN", "ghp_hostTokenThatMustNotLeak000000000000")
    # Git runs the driver through `sh`, which eats unquoted Windows backslashes.
    monkeypatch.setenv(
        "GIT_EXTERNAL_DIFF", f'"{Path(sys.executable).as_posix()}" "{driver.as_posix()}"'
    )
    (repo / "a.txt").write_text("b\n", encoding="utf-8")
    run_git(repo, "diff")
    assert seen.read_text(encoding="utf-8") == "absent"
