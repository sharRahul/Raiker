from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_slice_q1_spec_exists_with_required_sections() -> None:
    spec = _read("docs/PHASE_3_SLICE_Q1_RICH_TUI_DEFAULT_ACCESS_SHELL_SPEC.md")
    for section in (
        "Objective",
        "Current truth",
        "Default layout scope",
        "Non-goals",
        "Accessibility",
        "Safety boundaries",
        "Acceptance criteria",
    ):
        assert section in spec
    assert "implemented_verified" in spec


def test_readme_describes_q1_limited_scope() -> None:
    readme = _read("README.md")
    assert "Phase 3 Slice Q1" in readme
    assert "Rich TUI access shell" in readme
    assert "documented default layout only" in readme.lower()


def test_readme_keeps_runtime_disabled_truth() -> None:
    readme = _read("README.md")
    assert "runtime_execution_enabled" in readme
    assert "Runtime execution remains disabled." in readme


def test_implementation_status_marks_q1_implemented() -> None:
    content = _read("docs/IMPLEMENTATION_STATUS.md")
    assert "Phase 3 Slice Q1" in content
    assert "implemented_verified" in content


def test_implementation_status_does_not_overclaim_rich_tui() -> None:
    content = _read("docs/IMPLEMENTATION_STATUS.md").lower()
    assert "full rich tui complete" not in content
    assert "advanced panels complete" not in content


def test_event_catalog_states_q1_uses_existing_events() -> None:
    content = _read("docs/EVENT_CATALOG.md")
    assert "Phase 3 Slice Q1" in content
    assert "no new events" in content.lower() or "existing command/runtime events" in content.lower()


def test_acceptance_tests_list_q1() -> None:
    content = _read("docs/ACCEPTANCE_TESTS_BY_PHASE.md")
    assert "Phase 3 Slice Q1" in content


def test_verification_plan_lists_q1() -> None:
    content = _read("docs/VERIFICATION_PLAN.md")
    assert "Phase 3 Slice Q1" in content


def test_local_validation_gate_lists_q1_smoke() -> None:
    content = _read("docs/LOCAL_VALIDATION_GATE.md")
    assert "RAIKER_TUI=plain" in content


def test_feature_matrix_marks_rich_tui_default_shell() -> None:
    content = _read("docs/FEATURE_COVERAGE_MATRIX.md")
    assert "default access shell" in content.lower()


def test_docs_do_not_claim_apps_complete() -> None:
    readme = _read("README.md").lower()
    # Desktop/Web/Dashboard/Mobile must stay deferred.
    assert "specified/deferred" in readme
    for overclaim in (
        "desktop app is complete",
        "web app is complete",
        "mobile app is complete",
        "dashboard is complete",
        "approval execution enabled",
    ):
        assert overclaim not in readme
