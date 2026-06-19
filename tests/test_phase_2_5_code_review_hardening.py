from __future__ import annotations

import json
import subprocess
from pathlib import Path

from raiker.cli.commands import handle_slash_command
from raiker.review.models import SEVERITY_RANK
from raiker.review.render import rebuild_review_result_with_findings, render_json
from raiker.review.workflow import CodeReviewWorkflow


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


# ---------------------------------------------------------------------------
# Issue 1 — filtered summary consistency
# ---------------------------------------------------------------------------


def _findings_with_varied_severity(root: Path) -> None:
    """Create a repo with findings at different severity levels."""
    _stage(root, "src/app.py", "def f():\n    return 1\n")
    _modify(
        root, "src/app.py",
        'def f():\n    return 1\nimport subprocess\nsubprocess.run(["ls"])\n'
        'shell_execution_enabled: true\n',
    )


def test_severity_filter_rebuilds_summary(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _findings_with_varied_severity(tmp_path)
    result = CodeReviewWorkflow(emit_events=False).review(workspace_root=tmp_path)
    threshold = SEVERITY_RANK["high"]
    filtered = [f for f in result.findings if SEVERITY_RANK[f.severity] >= threshold]
    rebuilt = rebuild_review_result_with_findings(result, filtered)
    assert len(rebuilt.findings) == rebuilt.summary.findings_count
    assert rebuilt.summary.findings_count == len(filtered)
    for f in rebuilt.findings:
        assert SEVERITY_RANK[f.severity] >= threshold
    for sev, count in rebuilt.summary.severity_counts.items():
        if SEVERITY_RANK[sev] >= threshold:
            assert count >= 0
        else:
            assert count == 0


def test_limit_filter_rebuilds_summary(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _findings_with_varied_severity(tmp_path)
    result = CodeReviewWorkflow(emit_events=False).review(workspace_root=tmp_path)
    limit = 1
    filtered = result.findings[:limit]
    rebuilt = rebuild_review_result_with_findings(result, filtered)
    assert len(rebuilt.findings) == rebuilt.summary.findings_count
    assert rebuilt.summary.findings_count == limit
    assert len(rebuilt.findings) == 1


def test_severity_and_limit_rebuild_summary(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _findings_with_varied_severity(tmp_path)
    result = CodeReviewWorkflow(emit_events=False).review(workspace_root=tmp_path)
    threshold = SEVERITY_RANK["medium"]
    filtered = [f for f in result.findings if SEVERITY_RANK[f.severity] >= threshold]
    filtered = filtered[:1]
    rebuilt = rebuild_review_result_with_findings(result, filtered)
    assert rebuilt.summary.findings_count == len(filtered)
    assert rebuilt.summary.findings_count == 1
    for sev, count in rebuilt.summary.severity_counts.items():
        if SEVERITY_RANK[sev] < threshold:
            assert count == 0


def test_severity_filter_via_cli_json(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _findings_with_varied_severity(tmp_path)
    out = handle_slash_command("/review --severity high --json", workspace_root=tmp_path)
    payload = json.loads(out)
    for finding in payload["findings"]:
        assert finding["severity"] == "high"
    assert payload["summary"]["findings_count"] == len(payload["findings"])
    for sev, count in payload["summary"]["severity_counts"].items():
        if sev != "high":
            assert count == 0


def test_limit_filter_via_cli_json(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _findings_with_varied_severity(tmp_path)
    out = handle_slash_command("/review --limit 1 --json", workspace_root=tmp_path)
    payload = json.loads(out)
    assert len(payload["findings"]) == 1
    assert payload["summary"]["findings_count"] == 1


def test_severity_and_limit_via_cli_json(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _findings_with_varied_severity(tmp_path)
    out = handle_slash_command("/review --severity medium --limit 1 --json", workspace_root=tmp_path)
    payload = json.loads(out)
    findings = payload["findings"]
    assert len(findings) <= 1
    for f in findings:
        assert SEVERITY_RANK[f["severity"]] >= SEVERITY_RANK["medium"]
    assert payload["summary"]["findings_count"] == len(findings)


def test_summary_severity_output_does_not_show_filtered_out(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _findings_with_varied_severity(tmp_path)
    out = handle_slash_command("/review --summary --severity high", workspace_root=tmp_path)
    assert "untracked" not in out.lower() or "info" not in out.lower()


# ---------------------------------------------------------------------------
# Issue 2 — untracked file detection
# ---------------------------------------------------------------------------


def test_untracked_files_are_detected(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "new_file.py").write_text("x = 1\n", encoding="utf-8")
    result = CodeReviewWorkflow(emit_events=False).review(workspace_root=tmp_path)
    assert result.summary.findings_count > 0
    ids = [f.finding_id for f in result.findings]
    assert "untracked-files" in ids


def test_untracked_only_does_not_say_no_local_changes(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "untracked.py").write_text("y = 2\n", encoding="utf-8")
    out = handle_slash_command("/review", workspace_root=tmp_path)
    assert "No local changes found" not in out
    assert "Untracked files present" in out or "untracked" in out.lower()


def test_untracked_contents_not_read_or_leaked(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "secret_untracked.py").write_text(
        'api_key = "sk-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"\n', encoding="utf-8"
    )
    result = CodeReviewWorkflow(emit_events=False).review(workspace_root=tmp_path)
    blob = render_json(result)
    assert "sk-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" not in blob
    assert "api_key" not in blob


def test_untracked_count_in_safe_metadata(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "a.py").write_text("a = 1\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("b = 2\n", encoding="utf-8")
    result = CodeReviewWorkflow(emit_events=False).review(workspace_root=tmp_path)
    assert result.event_metadata.get("untracked_count") == 2


def test_untracked_event_payload_is_metadata_only(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "untracked.py").write_text("content\n", encoding="utf-8")
    CodeReviewWorkflow(emit_events=True).review(workspace_root=tmp_path)
    events_dir = tmp_path / ".raiker" / "events"
    payloads: list[dict[str, object]] = []
    for events_file in events_dir.glob("*.jsonl"):
        for line in events_file.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            if event["event_type"].startswith("review_"):
                payloads.append(event["payload"])
    assert payloads, "expected review events"
    for payload in payloads:
        if "untracked_count" in payload:
            assert isinstance(payload["untracked_count"], int)
        serialised = json.dumps(payload)
        assert "diff --git" not in serialised
        assert "content" not in serialised


def test_tracked_diff_plus_untracked_file(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _stage(tmp_path, "tracked.py", "a = 1\n")
    _modify(tmp_path, "tracked.py", "a = 2\n")
    (tmp_path / "untracked.py").write_text("b = 2\n", encoding="utf-8")
    result = CodeReviewWorkflow(emit_events=False).review(workspace_root=tmp_path)
    ids = [f.finding_id for f in result.findings]
    assert "untracked-files" in ids
    assert result.summary.files_reviewed == 1


def test_untracked_path_filter_detects_untracked(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "untracked.py").write_text("x = 1\n", encoding="utf-8")
    out = handle_slash_command(
        "/review --path sub/untracked.py", workspace_root=tmp_path
    )
    assert "Untracked files present" in out or "untracked" in out.lower()


def test_review_does_not_mutate_files(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "untracked.py").write_text("original\n", encoding="utf-8")
    before = (tmp_path / "untracked.py").read_text(encoding="utf-8")
    CodeReviewWorkflow().review(workspace_root=tmp_path)
    assert (tmp_path / "untracked.py").read_text(encoding="utf-8") == before


def test_review_does_not_stage_unstaged(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "untracked.py").write_text("x = 1\n", encoding="utf-8")
    CodeReviewWorkflow().review(workspace_root=tmp_path)
    status = subprocess.run(
        ["git", "-C", str(tmp_path), "status", "--short"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "?? untracked.py" in status


def test_review_event_has_untracked_count_and_no_contents(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "secret.py").write_text("SECRET=42\n", encoding="utf-8")
    CodeReviewWorkflow(emit_events=True).review(workspace_root=tmp_path)
    events_dir = tmp_path / ".raiker" / "events"
    for events_file in events_dir.glob("*.jsonl"):
        text = events_file.read_text(encoding="utf-8")
        assert "SECRET" not in text
        assert "untracked_count" in text or "review_" in text
