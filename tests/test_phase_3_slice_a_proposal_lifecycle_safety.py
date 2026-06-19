from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path

from raiker.context.gatherer import CAPABILITY_FLAGS, ContextGatherer
from raiker.review.lifecycle import (
    ProposalLifecycleStore,
    record_to_json,
    records_to_json,
    render_record_text,
    render_records_text,
)
from raiker.review.models import ReviewActionProposal
from raiker.storage.sqlite import SQLiteStore

_FORBIDDEN_IMPORTS = {"subprocess", "socket", "requests", "httpx", "urllib", "asyncio"}

_ALLOWED_LIFECYCLE_EVENT_KEYS = {
    "proposal_id",
    "review_id",
    "finding_id",
    "action_type",
    "risk_level",
    "requires_approval",
    "would_modify_files",
    "status",
    "previous_status",
    "new_status",
    "status_filter",
    "limit",
    "result_count",
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


def _proposal() -> ReviewActionProposal:
    return ReviewActionProposal(
        proposal_id="rap_aaaa000000000001",
        finding_id="secret-introduced",
        title="Remove secret-like material",
        action_type="secret_removal_proposal",
        risk_level="high",
        requires_approval=True,
        would_modify_files=True,
        files=[],
        summary="Remove the secret and rotate the credential.",
        rationale="Secret detected.",
        safety_notes=["Proposal only.", "No files were modified."],
    )


def _store(tmp_path: Path) -> ProposalLifecycleStore:
    return ProposalLifecycleStore(SQLiteStore(tmp_path))


def test_saving_proposals_does_not_mutate_files(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _stage(tmp_path, "config/app.yaml", "name: app\n")
    _modify(tmp_path, "config/app.yaml", 'name: app\npassword = "hunter2hunter2hunter2"\n')
    before = (tmp_path / "config/app.yaml").read_text(encoding="utf-8")
    store = _store(tmp_path)
    store.save_proposals([_proposal()], review_id="rev_1")
    assert (tmp_path / "config/app.yaml").read_text(encoding="utf-8") == before


def test_marking_proposals_does_not_mutate_files(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _stage(tmp_path, "config/app.yaml", "name: app\n")
    _modify(tmp_path, "config/app.yaml", 'name: app\npassword = "hunter2hunter2hunter2"\n')
    before = (tmp_path / "config/app.yaml").read_text(encoding="utf-8")
    store = _store(tmp_path)
    store.save_proposals([_proposal()], review_id="rev_1")
    store.mark_status("rap_aaaa000000000001", new_status="deferred")
    assert (tmp_path / "config/app.yaml").read_text(encoding="utf-8") == before


def test_saving_proposals_does_not_stage_or_unstage(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _stage(tmp_path, "config/app.yaml", "name: app\n")
    _modify(tmp_path, "config/app.yaml", 'name: app\npassword = "hunter2hunter2hunter2"\n')
    staged_before = subprocess.run(
        ["git", "-C", str(tmp_path), "diff", "--cached", "--name-only"],
        capture_output=True, text=True, check=True,
    ).stdout
    store = _store(tmp_path)
    store.save_proposals([_proposal()], review_id="rev_1")
    store.mark_status("rap_aaaa000000000001", new_status="acknowledged")
    staged_after = subprocess.run(
        ["git", "-C", str(tmp_path), "diff", "--cached", "--name-only"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert staged_before == staged_after


def test_no_raw_secrets_in_saved_records(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    store = _store(tmp_path)
    proposal = ReviewActionProposal(
        proposal_id="rap_aaaa000000000001",
        finding_id="secret-introduced",
        title="Remove secret",
        action_type="secret_removal_proposal",
        risk_level="high",
        requires_approval=True,
        would_modify_files=True,
        files=[],
        summary="Remove the secret and rotate.",
        rationale="Secret detected.",
        safety_notes=["Proposal only."],
    )
    store.save_proposals([proposal], review_id="rev_1")
    record = store.get_record("rap_aaaa000000000001")
    assert record is not None
    blob = json.dumps(record.to_dict())
    assert "hunter2hunter2hunter2" not in blob
    assert "password" not in blob.lower()


def test_no_raw_secrets_in_cli_output(tmp_path: Path) -> None:
    from raiker.cli.commands import handle_slash_command

    _init_repo(tmp_path)
    _stage(tmp_path, "config/app.yaml", "name: app\n")
    _modify(tmp_path, "config/app.yaml", 'name: app\npassword = "hunter2hunter2hunter2"\n')
    handle_slash_command(
        "/review --propose-fixes --save-proposals", workspace_root=tmp_path
    )
    out = handle_slash_command("/proposals --json", workspace_root=tmp_path)
    assert "hunter2hunter2hunter2" not in out
    assert "password" not in out.lower()


def test_no_private_reasoning_in_records_or_output(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save_proposals([_proposal()], review_id="rev_1")
    record = store.get_record("rap_aaaa000000000001")
    assert record is not None
    blob = (
        render_record_text(record)
        + render_records_text([record])
        + record_to_json(record)
        + records_to_json([record])
    ).lower()
    for banned in ("chain-of-thought", "chain of thought", "scratchpad", "reasoning_trace"):
        assert banned not in blob


def test_lifecycle_events_are_metadata_only(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    store = ProposalLifecycleStore(SQLiteStore(tmp_path), emit_events=True)
    store.save_proposals([_proposal()], review_id="rev_1")
    store.mark_status("rap_aaaa000000000001", new_status="deferred")
    store.list_records()
    store.get_record("rap_aaaa000000000001")
    events_dir = tmp_path / ".raiker" / "events"
    payloads: list[dict[str, object]] = []
    for events_file in events_dir.glob("*.jsonl"):
        for line in events_file.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            if event["event_type"].startswith("proposal_lifecycle_"):
                payloads.append(event["payload"])
    assert len(payloads) >= 4
    for payload in payloads:
        assert set(payload.keys()) <= _ALLOWED_LIFECYCLE_EVENT_KEYS
        serialised = json.dumps(payload)
        assert "hunter2" not in serialised
        assert "diff --git" not in serialised
        assert "password" not in serialised.lower()


def test_review_and_lifecycle_modules_no_unsafe_imports() -> None:
    for review_dir in [Path("raiker/review")]:
        for source_file in review_dir.glob("*.py"):
            tree = ast.parse(source_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert alias.name.split(".")[0] not in _FORBIDDEN_IMPORTS, source_file
                elif isinstance(node, ast.ImportFrom):
                    module = (node.module or "").split(".")[0]
                    assert module not in _FORBIDDEN_IMPORTS, source_file


def test_disabled_runtime_flags_remain_false(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    store = _store(tmp_path)
    store.save_proposals([_proposal()], review_id="rev_1")
    item = ContextGatherer()._capability_status(tmp_path)
    for flag in CAPABILITY_FLAGS:
        assert item.metadata[flag] is False


def test_no_apply_or_execute_command_introduced() -> None:
    commands_src = Path("raiker/cli/commands.py").read_text(encoding="utf-8")
    assert "/apply-fixes" not in commands_src
    assert "/review --apply" not in commands_src
    assert "handle_apply" not in commands_src


def test_no_execution_status_in_lifecycle_statuses() -> None:
    from raiker.review.models import PROPOSAL_LIFECYCLE_STATUSES

    for bad in ("approved", "approved_for_execution", "ready_to_apply", "execute"):
        assert bad not in PROPOSAL_LIFECYCLE_STATUSES


def test_table_exists_after_bootstrap(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    assert "proposal_lifecycle_records" in store.table_names()
