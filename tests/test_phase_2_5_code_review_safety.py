from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path

from raiker.context.gatherer import CAPABILITY_FLAGS, ContextGatherer
from raiker.review.render import render_json, render_text
from raiker.review.workflow import CodeReviewWorkflow

_ALLOWED_EVENT_KEYS = {
    "review_id",
    "mode",
    "files_reviewed",
    "findings_count",
    "severity_counts",
    "truncated",
    "redaction_applied",
    "client",
}
_FORBIDDEN_IMPORTS = {"subprocess", "socket", "requests", "httpx", "urllib", "asyncio"}


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    (root / ".gitignore").write_text(".raiker/\n", encoding="utf-8")


def _stage(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", rel], check=True)


def _modify(root: Path, rel: str, content: str) -> None:
    (root / rel).write_text(content, encoding="utf-8")


def test_review_does_not_mutate_files(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _stage(tmp_path, "a.py", "a = 1\n")
    _modify(tmp_path, "a.py", "a = 2\n")
    before = (tmp_path / "a.py").read_text(encoding="utf-8")
    CodeReviewWorkflow().review(workspace_root=tmp_path)
    assert (tmp_path / "a.py").read_text(encoding="utf-8") == before


def test_review_does_not_stage_or_unstage(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _stage(tmp_path, "a.py", "a = 1\n")
    _modify(tmp_path, "a.py", "a = 2\n")
    staged_before = subprocess.run(
        ["git", "-C", str(tmp_path), "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    CodeReviewWorkflow().review(workspace_root=tmp_path)
    staged_after = subprocess.run(
        ["git", "-C", str(tmp_path), "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert staged_before == staged_after


def test_review_event_payload_is_metadata_only(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _stage(tmp_path, "config/app.yaml", "name: app\n")
    _modify(tmp_path, "config/app.yaml", 'name: app\npassword = "hunter2hunter2hunter2"\n')
    CodeReviewWorkflow(emit_events=True).review(workspace_root=tmp_path)
    events_dir = tmp_path / ".raiker" / "events"
    payloads: list[dict[str, object]] = []
    for events_file in events_dir.glob("*.jsonl"):
        for line in events_file.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            if event["event_type"].startswith("review_"):
                payloads.append(event["payload"])
    assert payloads, "expected review events to be written"
    for payload in payloads:
        assert set(payload.keys()) <= _ALLOWED_EVENT_KEYS
        serialised = json.dumps(payload)
        assert "hunter2hunter2hunter2" not in serialised
        assert "diff --git" not in serialised


def test_review_output_has_no_private_reasoning(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _stage(tmp_path, "a.py", "a = 1\n")
    _modify(tmp_path, "a.py", "a = 2\n")
    result = CodeReviewWorkflow(emit_events=False).review(workspace_root=tmp_path)
    blob = (render_text(result) + render_json(result)).lower()
    for banned in ("chain-of-thought", "chain of thought", "scratchpad", "reasoning_trace"):
        assert banned not in blob


def test_review_output_has_no_raw_secret(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _stage(tmp_path, "config/app.yaml", "name: app\n")
    _modify(tmp_path, "config/app.yaml", 'name: app\napi_key = "AKIAIOSFODNN7EXAMPLE"\n')
    result = CodeReviewWorkflow(emit_events=False).review(workspace_root=tmp_path)
    blob = render_text(result) + render_json(result)
    assert "AKIAIOSFODNN7EXAMPLE" not in blob


def test_disabled_runtime_flags_remain_false(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    CodeReviewWorkflow().review(workspace_root=tmp_path)
    item = ContextGatherer()._capability_status(tmp_path)
    for flag in CAPABILITY_FLAGS:
        assert item.metadata[flag] is False


def test_review_package_introduces_no_unsafe_runtime_imports() -> None:
    review_dir = Path("raiker/review")
    for source_file in review_dir.glob("*.py"):
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in _FORBIDDEN_IMPORTS, source_file
            elif isinstance(node, ast.ImportFrom):
                module = (node.module or "").split(".")[0]
                assert module not in _FORBIDDEN_IMPORTS, source_file
