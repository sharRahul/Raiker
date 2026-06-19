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


def _save_and_get_proposal_id(root: Path) -> str:
    out = handle_slash_command(
        "/review --propose-fixes --save-proposals --json", workspace_root=root
    )
    payload = json.loads(out)
    return payload["event_metadata"]["saved_proposal_ids"][0]


def test_proposal_approval_preview_creates_preview(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    pid = _save_and_get_proposal_id(tmp_path)
    out = handle_slash_command(
        f"/proposal {pid} --approval-preview", workspace_root=tmp_path
    )
    assert "Approval planning preview:" in out
    assert f"Proposal: {pid}" in out
    assert "Preview only" in out


def test_proposal_approval_preview_json_is_parseable(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    pid = _save_and_get_proposal_id(tmp_path)
    out = handle_slash_command(
        f"/proposal {pid} --approval-preview --json", workspace_root=tmp_path
    )
    payload = json.loads(out)
    assert payload["preview_id"].startswith("apv_")
    assert payload["proposal_id"] == pid
    assert "required_human_decision" in payload
    assert "required_safety_checks" in payload
    assert "blocking_conditions" in payload


def test_approval_previews_lists_previews(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    pid = _save_and_get_proposal_id(tmp_path)
    handle_slash_command(
        f"/proposal {pid} --approval-preview", workspace_root=tmp_path
    )
    out = handle_slash_command("/approval-previews --limit 20", workspace_root=tmp_path)
    assert "Approval planning previews:" in out
    assert "apv_" in out


def test_approval_previews_json_is_parseable(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    pid = _save_and_get_proposal_id(tmp_path)
    handle_slash_command(
        f"/proposal {pid} --approval-preview", workspace_root=tmp_path
    )
    out = handle_slash_command("/approval-previews --limit 20 --json", workspace_root=tmp_path)
    payload = json.loads(out)
    assert isinstance(payload, list)
    assert len(payload) >= 1


def test_approval_previews_status_filter(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    pid = _save_and_get_proposal_id(tmp_path)
    handle_slash_command(
        f"/proposal {pid} --approval-preview", workspace_root=tmp_path
    )
    out = handle_slash_command(
        "/approval-previews --status needs_human_review --json", workspace_root=tmp_path
    )
    payload = json.loads(out)
    assert all(p["status"] == "needs_human_review" for p in payload)


def test_approval_previews_limit(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    pid = _save_and_get_proposal_id(tmp_path)
    handle_slash_command(
        f"/proposal {pid} --approval-preview", workspace_root=tmp_path
    )
    out = handle_slash_command("/approval-previews --limit 1 --json", workspace_root=tmp_path)
    payload = json.loads(out)
    assert len(payload) <= 1


def test_approval_preview_detail_shows_one(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    pid = _save_and_get_proposal_id(tmp_path)
    out = handle_slash_command(
        f"/proposal {pid} --approval-preview", workspace_root=tmp_path
    )
    preview_id = "apv_" + pid[len("rap_"):]
    out = handle_slash_command(
        f"/approval-preview {preview_id}", workspace_root=tmp_path
    )
    assert f"Approval planning preview: {preview_id}" in out


def test_approval_preview_detail_json_is_parseable(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    pid = _save_and_get_proposal_id(tmp_path)
    handle_slash_command(
        f"/proposal {pid} --approval-preview", workspace_root=tmp_path
    )
    preview_id = "apv_" + pid[len("rap_"):]
    out = handle_slash_command(
        f"/approval-preview {preview_id} --json", workspace_root=tmp_path
    )
    payload = json.loads(out)
    assert payload["preview_id"] == preview_id


def test_invalid_proposal_id_fails_safely(tmp_path: Path) -> None:
    out = handle_slash_command(
        "/proposal rap_unknown0000000000 --approval-preview", workspace_root=tmp_path
    )
    assert "not found" in out.lower()


def test_invalid_preview_id_fails_safely(tmp_path: Path) -> None:
    out = handle_slash_command(
        "/approval-preview apv_unknown0000000000", workspace_root=tmp_path
    )
    assert "not found" in out.lower()


def test_invalid_status_fails_safely(tmp_path: Path) -> None:
    out = handle_slash_command(
        "/approval-previews --status approved", workspace_root=tmp_path
    )
    assert out.startswith("Usage:")


def test_unknown_approval_previews_flag_fails_safely(tmp_path: Path) -> None:
    out = handle_slash_command(
        "/approval-previews --bogus", workspace_root=tmp_path
    )
    assert out.startswith("Usage:")


def test_approval_preview_execution_flags_rejected(tmp_path: Path) -> None:
    for flag in ("--approve", "--execute", "--apply", "--run-tests"):
        out = handle_slash_command(
            f"/approval-preview apv_x {flag}", workspace_root=tmp_path
        )
        assert "Usage:" in out


def test_help_lists_new_commands(tmp_path: Path) -> None:
    out = handle_slash_command("/help", workspace_root=tmp_path)
    assert "--approval-preview" in out
    assert "/approval-preview" in out
    assert "/approval-previews" in out


def test_approval_preview_detail_unknown_flag_fails(tmp_path: Path) -> None:
    out = handle_slash_command(
        "/approval-preview apv_xxx --bogus", workspace_root=tmp_path
    )
    assert "Usage:" in out


def test_proposal_mark_and_approval_preview(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    pid = _save_and_get_proposal_id(tmp_path)
    handle_slash_command(f"/proposal {pid} --mark acknowledged", workspace_root=tmp_path)
    out = handle_slash_command(
        f"/proposal {pid} --approval-preview --json", workspace_root=tmp_path
    )
    payload = json.loads(out)
    assert payload["proposal_status"] == "acknowledged"
