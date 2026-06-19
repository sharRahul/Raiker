from __future__ import annotations

import json
import subprocess
from pathlib import Path

from raiker.cli.commands import handle_slash_command


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    (root / ".gitignore").write_text(".raiker/\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", ".gitignore"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-m", "init", "--allow-empty"],
        check=True, capture_output=True,
    )


def _stage(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", rel], check=True)


def _modify(root: Path, rel: str, content: str) -> None:
    (root / rel).write_text(content, encoding="utf-8")


def _repo_with_secret_change(root: Path) -> None:
    _init_repo(root)
    _stage(root, "config/app.yaml", "name: app\n")
    _modify(root, "config/app.yaml", 'name: app\npassword = "hunter2hunter2hunter2"\n')


def _repo_with_varied_severity(root: Path) -> None:
    _init_repo(root)
    _stage(root, "src/app.py", "def f():\n    return 1\n")
    _modify(
        root, "src/app.py",
        'def f():\n    return 1\nimport subprocess\nsubprocess.run(["ls"])\n'
        'shell_execution_enabled: true\n',
    )


def test_review_propose_fixes_text_runs(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    out = handle_slash_command("/review --propose-fixes", workspace_root=tmp_path)
    assert "Code review summary" in out
    assert "Proposed actions:" in out
    assert "secret_removal_proposal" in out
    assert "Proposal only. No files were modified." in out


def test_review_propose_fixes_json_is_parseable(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    out = handle_slash_command("/review --propose-fixes --json", workspace_root=tmp_path)
    payload = json.loads(out)
    assert "action_proposals" in payload
    assert payload["summary"]["proposal_count"] == len(payload["action_proposals"])
    assert payload["summary"]["proposal_count"] >= 1
    proposal = payload["action_proposals"][0]
    for key in (
        "proposal_id", "finding_id", "title", "action_type", "risk_level",
        "requires_approval", "would_modify_files", "files", "summary",
        "rationale", "safety_notes",
    ):
        assert key in proposal
    assert proposal["proposal_id"].startswith("rap_")


def test_review_propose_fixes_summary_omits_detail(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    out = handle_slash_command("/review --propose-fixes --summary", workspace_root=tmp_path)
    assert "Proposed actions:" in out
    assert "secret_removal_proposal" not in out
    assert "Action type:" not in out
    assert "Would modify files:" not in out


def test_review_propose_fixes_severity_high_filters_proposals(tmp_path: Path) -> None:
    _repo_with_varied_severity(tmp_path)
    out = handle_slash_command(
        "/review --propose-fixes --severity high --json", workspace_root=tmp_path
    )
    payload = json.loads(out)
    for finding in payload["findings"]:
        assert finding["severity"] == "high"
    proposal_finding_ids = {p["finding_id"] for p in payload["action_proposals"]}
    assert proposal_finding_ids <= {"scope-expansion", "unsafe-runtime"}
    assert "missing-tests" not in proposal_finding_ids
    assert payload["summary"]["proposal_count"] == len(payload["action_proposals"])


def test_review_propose_fixes_limit_filters_proposals(tmp_path: Path) -> None:
    _repo_with_varied_severity(tmp_path)
    out = handle_slash_command(
        "/review --propose-fixes --limit 1 --json", workspace_root=tmp_path
    )
    payload = json.loads(out)
    assert len(payload["findings"]) <= 1
    assert len(payload["action_proposals"]) == len(payload["findings"])
    assert payload["summary"]["proposal_count"] == len(payload["action_proposals"])


def test_help_lists_propose_fixes(tmp_path: Path) -> None:
    out = handle_slash_command("/help", workspace_root=tmp_path)
    assert "--propose-fixes" in out
    assert "--proposals-only" in out


def test_unknown_proposal_flag_fails_safely(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    out = handle_slash_command("/review --apply-fixes", workspace_root=tmp_path)
    assert out.startswith("Usage: /review")


def test_review_without_propose_fixes_has_no_proposals(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    out = handle_slash_command("/review --json", workspace_root=tmp_path)
    payload = json.loads(out)
    assert payload["action_proposals"] == []
    assert payload["summary"]["proposal_count"] == 0


def test_review_proposals_only_shows_proposals_with_finding_reference(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    out = handle_slash_command("/review --proposals-only", workspace_root=tmp_path)
    assert "Proposed actions:" in out
    assert "finding: secret-introduced" in out
    assert "Evidence:" not in out
    assert "Recommendation:" not in out


def test_review_propose_fixes_clean_repo_has_zero_proposals(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    out = handle_slash_command("/review --propose-fixes --json", workspace_root=tmp_path)
    payload = json.loads(out)
    assert payload["action_proposals"] == []
    assert payload["summary"]["proposal_count"] == 0
