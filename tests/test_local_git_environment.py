"""ADD-27 GH-24 — a local git command inherits no credential and runs no fsmonitor."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from raiker.control.build_worktrees import create_worktree
from raiker.tools.git import (
    create_branch,
    create_commit,
    local_git_environment,
    proposed_commit_snapshot,
    run_git,
    working_tree_changes,
    working_tree_diff,
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for key in [name for name in os.environ if name.startswith("GIT_CONFIG")]:
        monkeypatch.delenv(key, raising=False)
    _git(tmp_path, "init", "--initial-branch=main", ".")
    _git(tmp_path, "config", "user.name", "T")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "commit.gpgsign", "false")
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


def test_git_diff_does_not_invoke_external_driver_with_host_token(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An external diff driver cannot observe credentials because it is not run."""
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
    assert not seen.exists()


def test_agent_git_diff_does_not_run_external_diff_driver(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = repo.parent / "external-driver-ran"
    driver = repo.parent / "external-driver.py"
    driver.write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n", encoding="utf-8")
    monkeypatch.setenv(
        "GIT_EXTERNAL_DIFF", f'"{Path(sys.executable).as_posix()}" "{driver.as_posix()}"'
    )
    (repo / "a.txt").write_text("modified\n", encoding="utf-8")
    _git(repo, "add", "a.txt")
    result = run_git(repo, "diff", ["--cached"])
    assert result["status"] == "success"
    assert not marker.exists()


@pytest.mark.parametrize("arg", ["--ext-diff", "--textconv", "--output=outside", "--ext-d"])
def test_git_diff_refuses_arguments_that_can_launch_or_write(repo: Path, arg: str) -> None:
    result = run_git(repo, "diff", [arg])
    assert result["status"] == "denied"
    assert result["error"]["type"] == "git_diff_argument_denied"


@pytest.mark.parametrize("path", ["../outside", ":(top)outside"])
def test_git_diff_refuses_pathspec_escape(repo: Path, path: str) -> None:
    result = run_git(repo, "diff", ["--", path])
    assert result["status"] == "denied"
    assert result["error"]["type"] == "git_diff_path_denied"


def test_git_diff_does_not_run_workspace_filter(repo: Path) -> None:
    marker = repo.parent / "filter-ran"
    driver = repo.parent / "filter.py"
    driver.write_text(
        "import pathlib,sys\n"
        f"pathlib.Path({str(marker)!r}).touch()\n"
        "sys.stdout.buffer.write(sys.stdin.buffer.read())\n",
        encoding="utf-8",
    )
    _git(repo, "config", "filter.raiker-test.clean", f'"{Path(sys.executable).as_posix()}" "{driver.as_posix()}"')
    (repo / ".gitattributes").write_text("a.txt filter=raiker-test\n", encoding="utf-8")
    (repo / "a.txt").write_text("staged change\n", encoding="utf-8")
    _git(repo, "add", ".gitattributes", "a.txt")
    assert marker.exists(), "control: Git must be able to start the filter"
    marker.unlink()
    (repo / "a.txt").write_text("modified\n", encoding="utf-8")
    result = run_git(repo, "diff")
    assert result["status"] == "success"
    assert "+modified" in result["output"]
    assert not marker.exists()
    staged = run_git(repo, "diff", ["--cached"])
    assert staged["status"] == "success"
    assert not marker.exists()


def test_artifact_diff_shows_staged_files_without_running_filter(repo: Path) -> None:
    marker = repo.parent / "artifact-filter-ran"
    driver = repo.parent / "artifact-filter.py"
    driver.write_text(
        "import pathlib,sys\n"
        f"pathlib.Path({str(marker)!r}).touch()\n"
        "sys.stdout.buffer.write(sys.stdin.buffer.read())\n",
        encoding="utf-8",
    )
    _git(repo, "config", "filter.raiker-test.clean", f'"{Path(sys.executable).as_posix()}" "{driver.as_posix()}"')
    (repo / ".gitattributes").write_text("a.txt filter=raiker-test\n", encoding="utf-8")
    (repo / "a.txt").write_text("staged change\n", encoding="utf-8")
    _git(repo, "add", ".gitattributes", "a.txt")
    (repo / ".raiker").mkdir()
    (repo / ".raiker" / "secret.txt").write_text("do-not-expose\n", encoding="utf-8")
    _git(repo, "add", ".raiker/secret.txt")
    assert marker.exists(), "control: Git must be able to start the filter"
    marker.unlink()
    entries = [{"path": "a.txt", "previous_path": "", "state": "modified", "unstaged": ""}]
    diff = working_tree_diff(repo, entries)
    assert "+staged change" in diff
    assert "do-not-expose" not in diff
    assert not marker.exists()
    all_staged = run_git(repo, "diff", ["--cached"])
    assert all_staged["status"] == "success"
    assert "do-not-expose" not in all_staged["output"]
    requested_secret = run_git(repo, "diff", ["--cached", "--", ".raiker"])
    assert requested_secret["status"] == "success"
    assert "do-not-expose" not in requested_secret["output"]


def test_git_status_does_not_run_workspace_filter(repo: Path) -> None:
    marker = repo.parent / "status-filter-ran"
    driver = repo.parent / "status-filter.py"
    driver.write_text(
        "import pathlib,sys\n"
        f"pathlib.Path({str(marker)!r}).touch()\n"
        "sys.stdout.buffer.write(sys.stdin.buffer.read())\n",
        encoding="utf-8",
    )
    _git(repo, "config", "filter.raiker-test.clean", f'"{Path(sys.executable).as_posix()}" "{driver.as_posix()}"')
    (repo / ".gitattributes").write_text("a.txt filter=raiker-test\n", encoding="utf-8")
    (repo / "a.txt").write_text("staged change\n", encoding="utf-8")
    _git(repo, "add", ".gitattributes", "a.txt")
    assert marker.exists(), "control: Git must be able to start the filter"
    marker.unlink()
    (repo / "a.txt").write_text("modified\n", encoding="utf-8")
    result = run_git(repo, "status", ["--short"])
    assert result["status"] == "success"
    assert not marker.exists()


def test_commit_preview_and_commit_never_run_a_configured_filter(repo: Path) -> None:
    marker = repo.parent / "commit-filter-ran"
    driver = repo.parent / "commit-filter.py"
    driver.write_text(
        "import pathlib,sys\n"
        f"pathlib.Path({str(marker)!r}).touch()\n"
        "sys.stdout.buffer.write(sys.stdin.buffer.read())\n",
        encoding="utf-8",
    )
    _git(repo, "config", "filter.raiker-test.clean", f'"{Path(sys.executable).as_posix()}" "{driver.as_posix()}"')
    (repo / ".gitattributes").write_text("a.txt filter=raiker-test\n", encoding="utf-8")
    (repo / "a.txt").write_text("staged change\n", encoding="utf-8")
    _git(repo, "add", ".gitattributes", "a.txt")
    assert marker.exists(), "control: Git must be able to start the filter"
    marker.unlink()
    (repo / "a.txt").write_text("modified\n", encoding="utf-8")
    entries = working_tree_changes(repo)
    assert "+modified" in working_tree_diff(repo, entries)
    assert not marker.exists()
    result = proposed_commit_snapshot(repo, "test")
    assert result["status"] == "success", result
    assert not marker.exists()
    committed = create_commit(repo, "test")
    assert committed["status"] == "success", committed
    assert not marker.exists()


def test_task_worktree_does_not_run_repository_smudge_filter(repo: Path) -> None:
    marker = repo.parent / "smudge-filter-ran"
    driver = repo.parent / "smudge-filter.py"
    driver.write_text(
        "import pathlib,sys\n"
        f"pathlib.Path({str(marker)!r}).touch()\n"
        "sys.stdout.buffer.write(sys.stdin.buffer.read())\n",
        encoding="utf-8",
    )
    _git(repo, "config", "filter.raiker-test.smudge", f'"{Path(sys.executable).as_posix()}" "{driver.as_posix()}"')
    (repo / ".gitattributes").write_text("a.txt filter=raiker-test\n", encoding="utf-8")
    _git(repo, "add", ".gitattributes")
    _git(repo, "commit", "-m", "add attributes")
    (repo / "a.txt").unlink()
    _git(repo, "checkout", "--force", "HEAD", "--", "a.txt")
    assert marker.exists(), "control: Git must be able to start the smudge filter"
    marker.unlink()
    result = create_worktree(repo.parent, repo.name, "sandbox-task")
    assert result["status"] == "success", result
    assert not marker.exists()


def test_branch_checkout_does_not_run_repository_smudge_filter(repo: Path) -> None:
    marker = repo.parent / "branch-smudge-ran"
    driver = repo.parent / "branch-smudge.py"
    driver.write_text(
        "import pathlib,sys\n"
        f"pathlib.Path({str(marker)!r}).touch()\n"
        "sys.stdout.buffer.write(sys.stdin.buffer.read())\n",
        encoding="utf-8",
    )
    _git(repo, "config", "filter.raiker-test.smudge", f'"{Path(sys.executable).as_posix()}" "{driver.as_posix()}"')
    (repo / ".gitattributes").write_text("a.txt filter=raiker-test\n", encoding="utf-8")
    _git(repo, "add", ".gitattributes")
    _git(repo, "commit", "-m", "attributes")
    base = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    (repo / "a.txt").write_text("new version\n", encoding="utf-8")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-m", "new version")
    (repo / "a.txt").unlink()
    _git(repo, "checkout", "--force", "HEAD", "--", "a.txt")
    assert marker.exists(), "control: Git must be able to start the smudge filter"
    marker.unlink()
    result = create_branch(repo, "sandbox-branch", base)
    assert result["status"] == "success", result
    assert not marker.exists()
    at_head = create_branch(repo, "branch-at-head")
    assert at_head["status"] == "success"
    assert not marker.exists()
