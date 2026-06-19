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


def test_save_proposals_persists_records(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    out = handle_slash_command(
        "/review --propose-fixes --save-proposals --json", workspace_root=tmp_path
    )
    payload = json.loads(out)
    assert payload["event_metadata"]["saved_proposal_count"] >= 1
    saved_ids = payload["event_metadata"]["saved_proposal_ids"]
    assert all(pid.startswith("rap_") for pid in saved_ids)


def test_proposals_lists_records(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    _save_and_get_proposal_id(tmp_path)
    out = handle_slash_command("/proposals", workspace_root=tmp_path)
    assert "Saved proposals:" in out
    assert "rap_" in out


def test_proposals_json_is_parseable(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    _save_and_get_proposal_id(tmp_path)
    out = handle_slash_command("/proposals --json", workspace_root=tmp_path)
    payload = json.loads(out)
    assert isinstance(payload, list)
    assert len(payload) >= 1
    assert payload[0]["proposal_id"].startswith("rap_")


def test_proposals_status_filter(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    pid = _save_and_get_proposal_id(tmp_path)
    handle_slash_command(
        f"/proposal {pid} --mark deferred", workspace_root=tmp_path
    )
    out = handle_slash_command("/proposals --status deferred --json", workspace_root=tmp_path)
    payload = json.loads(out)
    assert len(payload) == 1
    assert payload[0]["status"] == "deferred"


def test_proposals_limit(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    _save_and_get_proposal_id(tmp_path)
    out = handle_slash_command("/proposals --limit 1 --json", workspace_root=tmp_path)
    payload = json.loads(out)
    assert len(payload) <= 1


def test_proposal_detail_shows_one_record(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    pid = _save_and_get_proposal_id(tmp_path)
    out = handle_slash_command(f"/proposal {pid}", workspace_root=tmp_path)
    assert f"Proposal: {pid}" in out
    assert "Status: proposed" in out


def test_proposal_detail_json_is_parseable(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    pid = _save_and_get_proposal_id(tmp_path)
    out = handle_slash_command(f"/proposal {pid} --json", workspace_root=tmp_path)
    payload = json.loads(out)
    assert payload["proposal_id"] == pid
    assert payload["status"] == "proposed"


def test_proposal_mark_updates_status_only(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    pid = _save_and_get_proposal_id(tmp_path)
    out = handle_slash_command(
        f"/proposal {pid} --mark deferred", workspace_root=tmp_path
    )
    assert "Status: deferred" in out
    detail = json.loads(
        handle_slash_command(f"/proposal {pid} --json", workspace_root=tmp_path)
    )
    assert detail["status"] == "deferred"
    assert detail["proposal_id"] == pid


def test_invalid_proposal_id_fails_safely(tmp_path: Path) -> None:
    out = handle_slash_command("/proposal rap_unknown0000000000", workspace_root=tmp_path)
    assert "not found" in out.lower()


def test_invalid_status_fails_safely(tmp_path: Path) -> None:
    _repo_with_secret_change(tmp_path)
    pid = _save_and_get_proposal_id(tmp_path)
    out = handle_slash_command(
        f"/proposal {pid} --mark approved", workspace_root=tmp_path
    )
    assert out.startswith("Usage: /proposal")


def test_unknown_proposals_flag_fails_safely(tmp_path: Path) -> None:
    out = handle_slash_command("/proposals --bogus", workspace_root=tmp_path)
    assert out.startswith("Usage: /proposals")


def test_unknown_proposal_flag_fails_safely(tmp_path: Path) -> None:
    out = handle_slash_command("/proposal rap_x --bogus", workspace_root=tmp_path)
    assert out.startswith("Usage: /proposal")


def test_help_lists_new_commands(tmp_path: Path) -> None:
    out = handle_slash_command("/help", workspace_root=tmp_path)
    assert "/proposals" in out
    assert "/proposal <proposal_id>" in out
    assert "--save-proposals" in out
    assert "--mark" in out


def test_save_proposals_empty_creates_no_records(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    out = handle_slash_command(
        "/review --propose-fixes --save-proposals --json", workspace_root=tmp_path
    )
    payload = json.loads(out)
    assert payload["event_metadata"].get("saved_proposal_count", 0) == 0
    list_out = handle_slash_command("/proposals", workspace_root=tmp_path)
    assert "No saved proposals found." in list_out
