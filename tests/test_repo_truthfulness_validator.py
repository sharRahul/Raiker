from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from raiker.approvals.readiness_registry import approval_readiness_summary
from raiker.channels.readiness_registry import channel_readiness_summary
from raiker.cli.commands import handle_slash_command
from raiker.graph.governance import graph_governance_status
from raiker.memory.readiness_registry import semantic_memory_readiness_summary
from raiker.memory.semantic import semantic_memory_status
from raiker.plugins.readiness_registry import plugin_readiness_summary
from raiker.remote.readiness_registry import remote_readiness_summary
from raiker.storage.cleanup_readiness_registry import cleanup_readiness_summary


def test_truthfulness_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_repo_truthfulness.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Repository truthfulness validation passed." in result.stdout


def test_help_and_status_are_honest_about_backend_posture(tmp_path: Path) -> None:
    help_output = handle_slash_command("/help", workspace_root=tmp_path)
    status_output = handle_slash_command("/status", workspace_root=tmp_path)
    assert "Phase 3 Slice B approval planning preview is implemented" in help_output
    assert "Current launchable UI is the plain local terminal client only" in help_output
    assert "phase_4_status: memory_mvp_implemented" in status_output
    assert "runtime_execution_enabled: False" in status_output


def test_readiness_json_commands_are_parseable(tmp_path: Path) -> None:
    for command in [
        "/graph-readiness --json",
        "/memory-readiness --json",
        "/approval-readiness --json",
        "/cleanup-readiness --json",
        "/plugin-readiness --json",
        "/channel-readiness --json",
        "/remote-readiness --json",
    ]:
        payload = __import__("json").loads(handle_slash_command(command, workspace_root=tmp_path))
        assert payload["runtime_execution_enabled"] is False


def test_disabled_runtime_flags_remain_false(tmp_path: Path) -> None:
    snapshots = [
        plugin_readiness_summary(workspace_root=tmp_path),
        graph_governance_status(),
        {"graph_indexing_enabled": graph_governance_status()["runtime_indexing_enabled"]},
        semantic_memory_status(),
        semantic_memory_readiness_summary(workspace_root=tmp_path),
        {"semantic_memory_writes_enabled": semantic_memory_status()["semantic_writes_enabled"]},
        approval_readiness_summary(workspace_root=tmp_path),
        cleanup_readiness_summary(workspace_root=tmp_path),
        channel_readiness_summary(workspace_root=tmp_path),
        remote_readiness_summary(workspace_root=tmp_path),
    ]
    for name in [
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
    ]:
        values = [snapshot[name] for snapshot in snapshots if name in snapshot]
        assert values, f"missing disabled-runtime flag {name}"
        assert all(value is False for value in values), (name, values)


def test_architecture_and_security_docs_state_current_truth() -> None:
    architecture = Path("docs/architecture/ARCHITECTURE.md").read_text(encoding="utf-8")
    security = Path("docs/architecture/SECURITY_ARCHITECTURE.md").read_text(encoding="utf-8")
    assert "Current Backend Capability Matrix" in architecture
    assert "gateway finalisation events" in architecture
    assert "no `/sessions` command is currently implemented" in architecture
    # The security doc must state both the narrow executable allowlist and the
    # metadata-only remainder.
    assert "approval resolution executes a narrow allowlist" in security.lower()
    assert "remains metadata-only: it records the decision and executes nothing" in security.lower()
    assert "ssh remote execution | unavailable until owner profile selection" in security.lower()
    assert "plugin runtime slices" in security.lower()


def test_catalog_marks_memory_and_approval_semantics_precisely() -> None:
    catalog = Path("docs/architecture/RAIKER_TOOL_AND_PLUGIN_CATALOG.md").read_text(encoding="utf-8")
    assert "implemented_approval_required" in catalog
    assert "metadata_only" in catalog
    assert "executed once through the governed approval execution relay" in catalog
    assert "SSH/Daytona command" in catalog
    assert "metadata-only" in catalog


def test_truthfulness_validator_detects_known_overclaim_patterns() -> None:
    from scripts import validate_repo_truthfulness as validator

    errors = validator._validate_snippet(  # type: ignore[attr-defined]
        "docs/architecture/SECURITY_ARCHITECTURE.md",
        "Approval resolution executes any approved action. no-executor domains work. plugin execution enabled.",
    )
    joined = "\n".join(errors).lower()
    assert "forbidden overclaim" in joined


def test_truthfulness_validator_still_requires_the_execution_boundary_to_be_stated() -> None:
    """Naming what executes is not enough — the doc must bound it.

    BUG-06 narrowed the overclaim ban from "approval resolution executes" to the
    unbounded forms. This asserts the narrowing did not open a hole: a doc that
    mentions approval resolution without saying what stays metadata-only is
    still rejected.
    """
    from scripts import validate_repo_truthfulness as validator

    errors = validator._validate_snippet(  # type: ignore[attr-defined]
        "docs/architecture/SECURITY_ARCHITECTURE.md",
        "Approval resolution executes an approved local file mutation. fail-closed elsewhere. metadata-only preview.",
    )
    assert any("execution-boundary" in error for error in errors)
