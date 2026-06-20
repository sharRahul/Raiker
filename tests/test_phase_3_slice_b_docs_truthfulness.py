from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_implementation_status_marks_slice_b_implemented() -> None:
    content = _read("docs/IMPLEMENTATION_STATUS.md")
    assert "Phase 3 Slice B" in content
    assert "implemented_verified" in content


def test_readme_mentions_slice_b() -> None:
    content = _read("README.md")
    assert "Slice B" in content or "approval planning" in content.lower()


def test_docs_state_preview_only() -> None:
    readme = _read("README.md")
    assert "preview-only" in readme or "preview only" in readme.lower()


def test_docs_state_no_approval_execution() -> None:
    readme = _read("README.md")
    assert "no approval execution" in readme.lower()


def test_docs_state_no_proposal_execution() -> None:
    readme = _read("README.md")
    assert "no proposal execution" in readme.lower() or "not execute proposals" in readme.lower()


def test_docs_state_no_auto_fix() -> None:
    readme = _read("README.md")
    assert "auto-fix" in readme.lower() or "no auto" in readme.lower()


def test_docs_state_no_patch_application() -> None:
    readme = _read("README.md")
    assert "no patch application" in readme.lower() or "patches" in readme.lower()


def test_docs_state_no_file_mutation() -> None:
    readme = _read("README.md")
    assert "no file mutation" in readme.lower() or "not modify files" in readme.lower()


def test_docs_state_no_test_execution_by_preview_commands() -> None:
    readme = _read("README.md")
    assert "no test execution" in readme.lower()


def test_docs_state_no_github_pr_automation() -> None:
    readme = _read("README.md")
    assert "no GitHub PR" in readme.lower() or "no github pr" in readme.lower()


def test_docs_state_no_ui_api_ide_dashboard_mobile() -> None:
    readme = _read("README.md")
    assert "no UI" in readme.lower() or "no ui/api" in readme.lower()


def test_docs_state_no_phase_4() -> None:
    readme = _read("README.md")
    assert "no Phase 4" in readme


def test_event_catalog_lists_preview_events() -> None:
    content = _read("docs/EVENT_CATALOG.md")
    assert "proposal_approval_preview_created" in content
    assert "proposal_approval_preview_listed" in content
    assert "proposal_approval_preview_viewed" in content


def test_documentation_drift_audit_exists() -> None:
    content = _read("docs/DOCUMENTATION_DRIFT_AUDIT.md")
    assert "Phase 3 Slice B" in content


def test_slice_b_spec_exists() -> None:
    content = _read("docs/completed/PHASE_3_SLICE_B_APPROVAL_PLANNING_PREVIEW_SPEC.md")
    assert "implemented_verified" in content
    assert "preview" in content.lower()
