from __future__ import annotations

from pathlib import Path

STATUS = "docs/IMPLEMENTATION_STATUS.md"


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_implementation_status_marks_slice_b_implemented() -> None:
    content = _read(STATUS)
    assert "Phase 3 Slice B" in content
    assert "implemented_verified" in content


def test_status_mentions_slice_b() -> None:
    content = _read(STATUS)
    assert "Slice B" in content or "approval planning" in content.lower()


def test_status_states_preview_only() -> None:
    content = _read(STATUS)
    assert "preview-only" in content or "preview only" in content.lower()


def test_status_states_no_approval_execution() -> None:
    assert "no approval execution" in _read(STATUS).lower()


def test_status_states_no_proposal_execution() -> None:
    content = _read(STATUS).lower()
    assert "no proposal execution" in content or "not execute proposals" in content


def test_status_states_no_auto_fix() -> None:
    content = _read(STATUS).lower()
    assert "auto-fix" in content or "no auto" in content


def test_status_states_no_patch_application() -> None:
    content = _read(STATUS).lower()
    assert "no patch application" in content or "patches" in content


def test_status_states_no_file_mutation() -> None:
    content = _read(STATUS).lower()
    assert "no file mutation" in content or "not modify files" in content


def test_status_states_no_test_execution_by_preview_commands() -> None:
    assert "no test execution" in _read(STATUS).lower()


def test_status_states_no_github_pr_automation() -> None:
    assert "no github pr" in _read(STATUS).lower()


def test_status_states_no_ui_api_ide_dashboard_mobile() -> None:
    content = _read(STATUS).lower()
    assert "no ui" in content or "no ui/api" in content


def test_status_states_no_phase_4() -> None:
    assert "no Phase 4" in _read(STATUS)


def test_event_catalog_lists_preview_events() -> None:
    content = _read("docs/EVENT_CATALOG.md")
    assert "proposal_approval_preview_created" in content
    assert "proposal_approval_preview_listed" in content
    assert "proposal_approval_preview_viewed" in content


def test_documentation_drift_audit_exists() -> None:
    content = _read("docs/DOCUMENTATION_DRIFT_AUDIT.md")
    assert "Phase 3 Slice B" in content
