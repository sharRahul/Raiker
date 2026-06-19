from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from raiker.review.workflow import CodeReviewWorkflow, ReviewPathError


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    (root / ".gitignore").write_text(".raiker/\n", encoding="utf-8")


def _stage(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", rel], check=True)


def _modify(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _finding_ids(result) -> list[str]:  # type: ignore[no-untyped-def]
    return [finding.finding_id for finding in result.findings]


def test_clean_repository_has_no_findings(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    result = CodeReviewWorkflow(emit_events=False).review(workspace_root=tmp_path)
    assert result.scope.mode == "clean"
    assert result.summary.findings_count == 0
    assert result.summary.files_reviewed == 0


def test_source_changed_without_tests_emits_one_medium_finding(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _stage(tmp_path, "raiker/example.py", "def f():\n    return 1\n")
    _modify(tmp_path, "raiker/example.py", "def f():\n    return 2\n")
    result = CodeReviewWorkflow(emit_events=False).review(workspace_root=tmp_path)
    missing = [f for f in result.findings if f.finding_id == "missing-tests"]
    assert len(missing) == 1
    assert missing[0].severity == "medium"
    assert missing[0].category == "tests"


def test_source_and_tests_changed_suppresses_missing_test_finding(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _stage(tmp_path, "raiker/example.py", "def f():\n    return 1\n")
    _stage(tmp_path, "tests/test_example.py", "def test_f():\n    assert True\n")
    _modify(tmp_path, "raiker/example.py", "def f():\n    return 2\n")
    _modify(tmp_path, "tests/test_example.py", "def test_f():\n    assert 1\n")
    result = CodeReviewWorkflow(emit_events=False).review(workspace_root=tmp_path)
    assert "missing-tests" not in _finding_ids(result)


def test_docs_only_change_emits_info_docs_finding(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _stage(tmp_path, "docs/guide.md", "hello\n")
    _modify(tmp_path, "docs/guide.md", "hello world\n")
    result = CodeReviewWorkflow(emit_events=False).review(workspace_root=tmp_path)
    docs = [f for f in result.findings if f.finding_id == "docs-only"]
    assert len(docs) == 1
    assert docs[0].severity == "info"
    assert "missing-tests" not in _finding_ids(result)


def test_test_only_change_emits_info_tests_finding(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _stage(tmp_path, "tests/test_example.py", "def test_f():\n    assert True\n")
    _modify(tmp_path, "tests/test_example.py", "def test_f():\n    assert 1\n")
    result = CodeReviewWorkflow(emit_events=False).review(workspace_root=tmp_path)
    test_only = [f for f in result.findings if f.finding_id == "test-only"]
    assert len(test_only) == 1
    assert test_only[0].severity == "info"
    assert "missing-tests" not in _finding_ids(result)


def test_secret_like_diff_emits_high_security_without_leak(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _stage(tmp_path, "config/app.yaml", "name: app\n")
    _modify(tmp_path, "config/app.yaml", 'name: app\npassword = "hunter2hunter2hunter2"\n')
    workflow = CodeReviewWorkflow(emit_events=False)
    result = workflow.review(workspace_root=tmp_path)
    secret = [f for f in result.findings if f.finding_id == "secret-introduced"]
    assert len(secret) == 1
    assert secret[0].severity == "high"
    assert result.summary.redaction_applied is True
    # The raw secret must not appear anywhere in the result payload.
    assert "hunter2hunter2hunter2" not in str(result.to_dict())


def test_scope_expansion_emits_high_finding(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _stage(tmp_path, "config/flags.yaml", "feature: off\n")
    _modify(tmp_path, "config/flags.yaml", "feature: off\nshell_execution_enabled: true\n")
    result = CodeReviewWorkflow(emit_events=False).review(workspace_root=tmp_path)
    scope = [f for f in result.findings if f.finding_id == "scope-expansion"]
    assert len(scope) == 1
    assert scope[0].severity == "high"
    assert scope[0].category == "scope"


def test_risky_runtime_activation_emits_high_finding(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _stage(tmp_path, "tool.py", "x = 1\n")
    _modify(tmp_path, "tool.py", "x = 1\nimport subprocess\nsubprocess.run(['ls'])\n")
    result = CodeReviewWorkflow(emit_events=False).review(workspace_root=tmp_path)
    runtime = [f for f in result.findings if f.finding_id == "unsafe-runtime"]
    assert len(runtime) == 1
    assert runtime[0].severity == "high"
    assert runtime[0].category == "security"


def test_large_diff_is_truncated(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _stage(tmp_path, "big.py", "a = 1\n")
    _modify(tmp_path, "big.py", "a = 1\nb = 2  # " + ("x" * 5000) + "\n")
    result = CodeReviewWorkflow(emit_events=False).review(
        workspace_root=tmp_path, max_diff_chars=80
    )
    assert result.summary.truncated is True
    truncated = [f for f in result.findings if f.finding_id == "review-truncated"]
    assert len(truncated) == 1
    assert truncated[0].severity == "info"


def test_path_filter_scopes_review_to_one_file(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _stage(tmp_path, "one.py", "a = 1\n")
    _stage(tmp_path, "two.py", "b = 1\n")
    _modify(tmp_path, "one.py", "a = 2\n")
    _modify(tmp_path, "two.py", "b = 2\n")
    result = CodeReviewWorkflow(emit_events=False).review(
        workspace_root=tmp_path, path="one.py"
    )
    assert result.scope.mode == "path"
    assert result.summary.files_reviewed == 1


def test_invalid_path_is_rejected(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    with pytest.raises(ReviewPathError):
        CodeReviewWorkflow(emit_events=False).review(
            workspace_root=tmp_path, path="../outside"
        )


def test_staged_changes_reviewed_with_staged_flag(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _stage(tmp_path, "raiker/example.py", "def f():\n    return 1\n")
    result = CodeReviewWorkflow(emit_events=False).review(workspace_root=tmp_path, staged=True)
    assert result.scope.mode == "staged"
    assert result.summary.files_reviewed == 1


def test_default_mode_reports_staged_changes_present(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _stage(tmp_path, "raiker/example.py", "def f():\n    return 1\n")
    result = CodeReviewWorkflow(emit_events=False).review(workspace_root=tmp_path)
    assert result.scope.mode == "clean"
    assert result.event_metadata.get("staged_changes_present") is True
