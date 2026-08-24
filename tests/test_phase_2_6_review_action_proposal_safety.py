from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path

from raiker.context.gatherer import CAPABILITY_GATE_TOOLS, ContextGatherer
from raiker.review.proposals import generate_action_proposals
from raiker.review.render import render_json, render_text
from raiker.review.workflow import CodeReviewWorkflow
from raiker.storage.sqlite import SQLiteStore

_FORBIDDEN_IMPORTS = {"subprocess", "socket", "requests", "httpx", "urllib", "asyncio"}

_ALLOWED_PROPOSAL_EVENT_KEYS = {
    "review_id",
    "proposal_count",
    "requires_approval_count",
    "would_modify_files_count",
    "risk_counts",
    "client",
}


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


def test_proposal_generation_does_not_mutate_files(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _stage(tmp_path, "config/app.yaml", "name: app\n")
    _modify(tmp_path, "config/app.yaml", 'name: app\npassword = "hunter2hunter2hunter2"\n')
    before = (tmp_path / "config/app.yaml").read_text(encoding="utf-8")
    CodeReviewWorkflow(emit_events=False).review(workspace_root=tmp_path, propose_fixes=True)
    assert (tmp_path / "config/app.yaml").read_text(encoding="utf-8") == before


def test_proposal_generation_does_not_stage_or_unstage(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _stage(tmp_path, "config/app.yaml", "name: app\n")
    _modify(tmp_path, "config/app.yaml", 'name: app\npassword = "hunter2hunter2hunter2"\n')
    staged_before = subprocess.run(
        ["git", "-C", str(tmp_path), "diff", "--cached", "--name-only"],
        capture_output=True, text=True, check=True,
    ).stdout
    CodeReviewWorkflow(emit_events=False).review(workspace_root=tmp_path, propose_fixes=True)
    staged_after = subprocess.run(
        ["git", "-C", str(tmp_path), "diff", "--cached", "--name-only"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert staged_before == staged_after


def test_proposal_output_has_no_raw_secret(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _stage(tmp_path, "config/app.yaml", "name: app\n")
    _modify(tmp_path, "config/app.yaml", 'name: app\napi_key = "AKIAIOSFODNN7EXAMPLE"\n')
    result = CodeReviewWorkflow(emit_events=False).review(
        workspace_root=tmp_path, propose_fixes=True
    )
    blob = render_text(result, proposals_only=True) + render_json(result)
    assert "AKIAIOSFODNN7EXAMPLE" not in blob


def test_proposal_output_has_no_private_reasoning(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _stage(tmp_path, "a.py", "a = 1\n")
    _modify(tmp_path, "a.py", "a = 2\n")
    result = CodeReviewWorkflow(emit_events=False).review(
        workspace_root=tmp_path, propose_fixes=True
    )
    blob = (render_text(result) + render_json(result)).lower()
    for banned in ("chain-of-thought", "chain of thought", "scratchpad", "reasoning_trace"):
        assert banned not in blob


def test_proposal_event_payload_is_metadata_only(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _stage(tmp_path, "config/app.yaml", "name: app\n")
    _modify(tmp_path, "config/app.yaml", 'name: app\npassword = "hunter2hunter2hunter2"\n')
    CodeReviewWorkflow(emit_events=True).review(
        workspace_root=tmp_path, propose_fixes=True
    )
    events_dir = tmp_path / ".raiker" / "events"
    proposal_payloads: list[dict[str, object]] = []
    review_payloads: list[dict[str, object]] = []
    for events_file in events_dir.glob("*.jsonl"):
        for line in events_file.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            if event["event_type"] == "review_proposals_created":
                proposal_payloads.append(event["payload"])
            elif event["event_type"].startswith("review_"):
                review_payloads.append(event["payload"])
    assert proposal_payloads, "expected review_proposals_created event"
    for payload in proposal_payloads:
        assert set(payload.keys()) <= _ALLOWED_PROPOSAL_EVENT_KEYS
        serialised = json.dumps(payload)
        assert "hunter2hunter2hunter2" not in serialised
        assert "diff --git" not in serialised
        assert "password" not in serialised.lower()
    for payload in review_payloads:
        serialised = json.dumps(payload)
        assert "hunter2hunter2hunter2" not in serialised
        assert "diff --git" not in serialised


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


def test_a_review_never_turns_a_capability_gate_on(tmp_path: Path) -> None:
    # Before against after: the property is that proposing fixes changes no
    # gate, not that every gate starts off. See the note in
    # `test_phase_2_5_code_review_safety.py`.
    _init_repo(tmp_path)
    before = ContextGatherer()._capability_status(tmp_path, SQLiteStore(tmp_path), None)
    CodeReviewWorkflow().review(workspace_root=tmp_path, propose_fixes=True)
    after = ContextGatherer()._capability_status(tmp_path, SQLiteStore(tmp_path), None)
    for capability in CAPABILITY_GATE_TOOLS:
        assert after.metadata[capability] == before.metadata[capability], capability  # type: ignore[index]


def test_no_apply_or_execute_command_introduced() -> None:
    commands_src = Path("raiker/cli/commands.py").read_text(encoding="utf-8")
    assert "/apply-fixes" not in commands_src
    assert "/review --apply" not in commands_src
    assert "handle_apply" not in commands_src


def test_proposal_generator_pure_function_no_side_effects(tmp_path: Path) -> None:
    from raiker.review.models import ReviewFinding

    finding = ReviewFinding(
        finding_id="missing-tests",
        severity="medium",
        category="tests",
        title="t",
        description="d",
        evidence="e",
        recommendation="r",
        confidence="medium",
    )
    proposals1 = generate_action_proposals([finding])
    proposals2 = generate_action_proposals([finding])
    assert proposals1 == proposals2
