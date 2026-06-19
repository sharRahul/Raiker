from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_readiness_audit_doc_exists() -> None:
    assert (ROOT / "docs" / "PRE_PHASE_3_READINESS_AUDIT.md").exists()


def test_readiness_audit_lists_all_phases_complete() -> None:
    text = _read("docs/PRE_PHASE_3_READINESS_AUDIT.md")
    for marker in (
        "Phase 1",
        "Phase 2",
        "Phase 2.5",
        "Phase 2.6",
        "implemented_verified",
    ):
        assert marker in text
    assert "Phase 2.6" in text


def test_readiness_audit_says_phase_3_ready_to_start_planning() -> None:
    text = _read("docs/PRE_PHASE_3_READINESS_AUDIT.md")
    assert "Ready to start Phase 3 planning" in text
    assert "scoped plan" in text


def test_readiness_audit_does_not_claim_phase_3_runtime_activation() -> None:
    text = _read("docs/PRE_PHASE_3_READINESS_AUDIT.md").lower()
    assert "phase 3 is **not** complete" in text or "phase 3 is not complete" in text
    assert "phase 3 runtime activation complete" not in text
    assert "phase 3 is implemented by this task" not in text


def test_readiness_audit_lists_deferred_capabilities() -> None:
    text = _read("docs/PRE_PHASE_3_READINESS_AUDIT.md")
    for marker in (
        "Auto-fix",
        "GitHub PR review automation",
        "semantic",
        "graph",
        "plugin execution",
    ):
        assert marker.lower() in text.lower()


def test_readiness_audit_lists_disabled_runtime_flags() -> None:
    text = _read("docs/PRE_PHASE_3_READINESS_AUDIT.md")
    for flag in (
        "plugin_execution_enabled",
        "graph_indexing_enabled",
        "semantic_memory_writes_enabled",
        "vector_writes_enabled",
        "embedding_creation_enabled",
        "approval_execution_enabled",
        "approval_relay_runtime_enabled",
        "cleanup_execution_enabled",
        "rollback_execution_enabled",
        "external_channels_enabled",
        "notifications_enabled",
        "remote_execution_enabled",
        "container_execution_enabled",
        "cloud_execution_enabled",
        "process_execution_enabled",
        "shell_execution_enabled",
        "network_execution_enabled",
        "runtime_execution_enabled",
    ):
        assert flag in text


def test_readiness_audit_includes_green_local_validation_baseline() -> None:
    text = _read("docs/PRE_PHASE_3_READINESS_AUDIT.md")
    assert "ruff" in text
    assert "mypy" in text
    assert "pytest" in text
    assert "validate_phase_status.py" in text
    assert "validate_repo_truthfulness.py" in text


def test_readiness_audit_states_proposal_only_safety() -> None:
    text = _read("docs/PRE_PHASE_3_READINESS_AUDIT.md")
    for marker in (
        "Proposal-only.",
        "No fixes are applied.",
        "No files are modified.",
        "No tests are run.",
        "No shell/process/network execution is used.",
    ):
        assert marker in text


def test_truthfulness_validator_passes() -> None:
    import subprocess

    result = subprocess.run(
        ["python", "scripts/validate_repo_truthfulness.py"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_phase_status_validator_passes() -> None:
    import subprocess

    result = subprocess.run(
        ["python", "scripts/validate_phase_status.py"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert result.returncode == 0, result.stdout + result.stderr
