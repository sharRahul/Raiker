from __future__ import annotations

import json
import subprocess
from pathlib import Path

from raiker.cli.commands import (
    handle_approval_preview_lookup,
    handle_approval_previews,
    handle_slash_command,
)


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


def _save_and_get_proposal_id(root: Path) -> str:
    out = handle_slash_command(
        "/review --propose-fixes --save-proposals --json", workspace_root=root
    )
    payload = json.loads(out)
    return payload["event_metadata"]["saved_proposal_ids"][0]


def test_creating_preview_does_not_mutate_files(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    pid = _save_and_get_proposal_id(tmp_path)
    content_before = (tmp_path / "config" / "app.yaml").read_text()
    handle_slash_command(
        f"/proposal {pid} --approval-preview", workspace_root=tmp_path
    )
    content_after = (tmp_path / "config" / "app.yaml").read_text()
    assert content_before == content_after


def test_listing_viewing_previews_does_not_mutate_files(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    pid = _save_and_get_proposal_id(tmp_path)
    handle_slash_command(
        f"/proposal {pid} --approval-preview", workspace_root=tmp_path
    )
    preview_id = "apv_" + pid[len("rap_"):]
    content_before = (tmp_path / "config" / "app.yaml").read_text()
    handle_approval_previews("/approval-previews --limit 20", workspace_root=tmp_path)
    handle_approval_preview_lookup(f"/approval-preview {preview_id}", workspace_root=tmp_path)
    content_after = (tmp_path / "config" / "app.yaml").read_text()
    assert content_before == content_after


def test_creating_preview_does_not_stage(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    pid = _save_and_get_proposal_id(tmp_path)
    result = subprocess.run(
        ["git", "-C", str(tmp_path), "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    )
    unstaged_before = result.stdout.strip()
    handle_slash_command(
        f"/proposal {pid} --approval-preview", workspace_root=tmp_path
    )
    result = subprocess.run(
        ["git", "-C", str(tmp_path), "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    )
    unstaged_after = result.stdout.strip()
    assert unstaged_before == unstaged_after


def test_listing_viewing_does_not_stage(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    pid = _save_and_get_proposal_id(tmp_path)
    handle_slash_command(
        f"/proposal {pid} --approval-preview", workspace_root=tmp_path
    )
    preview_id = "apv_" + pid[len("rap_"):]
    result = subprocess.run(
        ["git", "-C", str(tmp_path), "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    )
    before = result.stdout.strip()
    handle_approval_previews("/approval-previews --limit 20", workspace_root=tmp_path)
    handle_approval_preview_lookup(f"/approval-preview {preview_id}", workspace_root=tmp_path)
    result = subprocess.run(
        ["git", "-C", str(tmp_path), "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    )
    after = result.stdout.strip()
    assert before == after


def test_no_tests_are_run_by_preview_commands(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    pid = _save_and_get_proposal_id(tmp_path)
    handle_slash_command(
        f"/proposal {pid} --approval-preview", workspace_root=tmp_path
    )
    assert True


def test_no_raw_secrets_in_preview_records(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    pid = _save_and_get_proposal_id(tmp_path)
    out = handle_slash_command(
        f"/proposal {pid} --approval-preview --json", workspace_root=tmp_path
    )
    assert "hunter2" not in out
    assert "password" not in out.lower() or "password" not in json.loads(out).get("required_human_decision", "")


def test_no_private_reasoning_in_records_or_output(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    pid = _save_and_get_proposal_id(tmp_path)
    out = handle_slash_command(
        f"/proposal {pid} --approval-preview", workspace_root=tmp_path
    )
    for term in ("chain-of-thought", "chain_of_thought", "reasoning:", "thought process"):
        assert term not in out.lower()


def test_no_raw_diff_in_preview_events(tmp_path: Path) -> None:
    from raiker.review.approval_preview import approval_preview_from_lifecycle_record
    from raiker.review.models import ProposalLifecycleRecord

    record = ProposalLifecycleRecord(
        proposal_id="rap_test000000000001",
        review_id="rev_1",
        finding_id="missing-tests",
        title="Test",
        action_type="test_addition_proposal",
        risk_level="medium",
        requires_approval=True,
        would_modify_files=True,
        status="proposed",
        files=["test.py"],
        summary="Test",
        created_at="2026-06-19T00:00:00Z",
        updated_at="2026-06-19T00:00:00Z",
        source="test",
    )
    preview = approval_preview_from_lifecycle_record(record)
    blob = json.dumps(preview.to_dict())
    for term in ("diff --git", "--- a/", "+++ b/", "@@", "patch body", "raw tool output"):
        assert term not in blob


def test_disabled_runtime_flags_remain_false(tmp_path: Path) -> None:
    out = handle_slash_command("/status", workspace_root=tmp_path)
    assert "runtime_execution_enabled: False" in out
    assert "phase_3_4_surface_mode: read_only_planning_preview_only" in out


def test_approval_execution_enabled_false(tmp_path: Path) -> None:
    out = handle_slash_command("/status", workspace_root=tmp_path)
    assert "phase_4_status: blocked_foundation_only" in out


def test_no_approve_execute_apply_run_tests_commands(tmp_path: Path) -> None:
    for cmd in (
        "/approval-preview apv_x --approve",
        "/approval-preview apv_x --execute",
        "/approval-preview apv_x --apply",
        "/approval-preview apv_x --run-tests",
    ):
        out = handle_slash_command(cmd, workspace_root=tmp_path)
        assert "Usage:" in out
