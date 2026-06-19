from __future__ import annotations

import json
import subprocess
from pathlib import Path

from raiker.cli.commands import handle_slash_command


def _repo_with_change(root: Path) -> None:
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    (root / ".gitignore").write_text(".raiker/\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", ".gitignore"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-m", "init", "--allow-empty"], check=True, capture_output=True)
    (root / "raiker").mkdir()
    (root / "raiker" / "example.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "raiker/example.py"], check=True)
    (root / "raiker" / "example.py").write_text("def f():\n    return 2\n", encoding="utf-8")


def test_review_command_runs(tmp_path: Path) -> None:
    _repo_with_change(tmp_path)
    out = handle_slash_command("/review", workspace_root=tmp_path)
    assert "Code review summary" in out
    assert "Files reviewed: 1" in out


def test_review_summary_omits_finding_detail(tmp_path: Path) -> None:
    _repo_with_change(tmp_path)
    out = handle_slash_command("/review --summary", workspace_root=tmp_path)
    assert "Code review summary" in out
    assert "Evidence:" not in out
    assert "Recommendation:" not in out


def test_review_staged_runs(tmp_path: Path) -> None:
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    (tmp_path / ".gitignore").write_text(".raiker/\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", ".gitignore"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init", "--allow-empty"], check=True, capture_output=True)
    (tmp_path / "a.py").write_text("a = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "a.py"], check=True)
    out = handle_slash_command("/review --staged", workspace_root=tmp_path)
    assert "Code review summary" in out
    assert "staged changes" in out


def test_review_path_runs(tmp_path: Path) -> None:
    _repo_with_change(tmp_path)
    out = handle_slash_command("/review --path raiker/example.py", workspace_root=tmp_path)
    assert "Files reviewed: 1" in out


def test_review_json_is_parseable(tmp_path: Path) -> None:
    _repo_with_change(tmp_path)
    out = handle_slash_command("/review --json", workspace_root=tmp_path)
    payload = json.loads(out)
    assert set(payload.keys()) >= {"review_id", "scope", "summary", "findings", "safety_notes"}
    assert payload["review_id"].startswith("rev_")


def test_review_unknown_flag_fails_safely(tmp_path: Path) -> None:
    _repo_with_change(tmp_path)
    out = handle_slash_command("/review --bogus", workspace_root=tmp_path)
    assert out.startswith("Usage: /review")


def test_review_invalid_path_fails_safely(tmp_path: Path) -> None:
    _repo_with_change(tmp_path)
    out = handle_slash_command("/review --path ../outside", workspace_root=tmp_path)
    assert "outside the workspace" in out


def test_help_lists_review_commands(tmp_path: Path) -> None:
    out = handle_slash_command("/help", workspace_root=tmp_path)
    assert "/review" in out
    assert "--staged" in out
    assert "--json" in out


def test_empty_workspace_does_not_crash(tmp_path: Path) -> None:
    out = handle_slash_command("/review", workspace_root=tmp_path)
    assert "Code review summary" in out
    assert "No local changes found." in out


def test_review_severity_filter(tmp_path: Path) -> None:
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    (tmp_path / ".gitignore").write_text(".raiker/\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", ".gitignore"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init", "--allow-empty"], check=True, capture_output=True)
    (tmp_path / "flags.yaml").write_text("feature: off\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "flags.yaml"], check=True)
    (tmp_path / "flags.yaml").write_text(
        "feature: off\nshell_execution_enabled: true\n", encoding="utf-8"
    )
    out = handle_slash_command("/review --severity high --json", workspace_root=tmp_path)
    payload = json.loads(out)
    severities = {finding["severity"] for finding in payload["findings"]}
    assert severities <= {"high"}
