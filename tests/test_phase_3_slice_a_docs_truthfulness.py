from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_slice_a_spec_doc_exists() -> None:
    assert (ROOT / "docs" / "completed" / "PHASE_3_SLICE_A_PROPOSAL_LIFECYCLE_SPEC.md").exists()


def test_implementation_status_marks_slice_a_verified() -> None:
    text = _read("docs/IMPLEMENTATION_STATUS.md")
    assert "Phase 3 Slice A proposal lifecycle foundation: implemented_verified" in text


def test_readme_lists_new_commands() -> None:
    text = _read("README.md")
    assert "/proposals" in text
    assert "/proposal <proposal_id>" in text
    assert "--save-proposals" in text


def test_readme_states_slice_a_safety_markers() -> None:
    text = _read("README.md")
    for marker in (
        "metadata-only",
        "proposal-only",
        "no proposal execution",
        "no auto-fix",
        "no Phase 4",
    ):
        assert marker.lower() in text.lower()


def test_spec_doc_states_safety_markers() -> None:
    text = _read("docs/completed/PHASE_3_SLICE_A_PROPOSAL_LIFECYCLE_SPEC.md")
    for marker in (
        "metadata-only",
        "proposal-only",
        "no proposal execution",
        "no auto-fix",
        "no patch application",
        "no file mutation",
        "no staging/unstaging",
        "no test execution",
        "no GitHub PR automation",
        "no UI/API/IDE/dashboard/mobile",
        "no approval execution",
        "no Phase 4",
        "disabled runtime flags remain false",
    ):
        assert marker.lower() in text.lower()


def test_spec_doc_does_not_claim_runtime_execution() -> None:
    text = _read("docs/completed/PHASE_3_SLICE_A_PROPOSAL_LIFECYCLE_SPEC.md").lower()
    assert "phase 3 runtime execution is implemented" not in text
    assert "auto-fix complete" not in text
    assert "patch application complete" not in text
    assert "approval execution complete" not in text
    assert "github pr automation complete" not in text


def test_event_catalog_documents_lifecycle_events() -> None:
    text = _read("docs/EVENT_CATALOG.md")
    assert "proposal_lifecycle_created" in text
    assert "proposal_lifecycle_status_changed" in text
    assert "proposal_lifecycle_listed" in text
    assert "proposal_lifecycle_viewed" in text


def test_commands_spec_documents_new_commands() -> None:
    text = _read("docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md")
    assert "/proposals" in text
    assert "/proposal <proposal_id>" in text
    assert "--save-proposals" in text


def test_tool_catalog_lists_new_commands() -> None:
    text = _read("docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md")
    assert "/proposals" in text
    assert "/proposal <proposal_id>" in text


def test_readiness_audit_mentions_slice_a() -> None:
    text = _read("docs/completed/PRE_PHASE_3_READINESS_AUDIT.md")
    assert "Phase 3 Slice A" in text or "Slice A" in text


def test_truthfulness_validator_passes() -> None:
    import subprocess

    result = subprocess.run(
        ["python", "scripts/validate_repo_truthfulness.py"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_phase_status_validator_passes() -> None:
    import subprocess

    result = subprocess.run(
        ["python", "scripts/validate_phase_status.py"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    assert result.returncode == 0, result.stdout + result.stderr
