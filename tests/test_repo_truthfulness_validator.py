from __future__ import annotations

import json
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


def test_help_and_status_are_honest_about_phase_3_and_ui_scope(tmp_path: Path) -> None:
    help_output = handle_slash_command("/help", workspace_root=tmp_path)
    assert "Phase 3 Slice B approval planning preview is implemented" in help_output
    assert "Current launchable UI is the plain local terminal client only" in help_output
    assert "Phase 8 deferred work" in help_output

    status_output = handle_slash_command("/status", workspace_root=tmp_path)
    assert "phase_3_status: implemented_verified" in status_output
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
        payload = json.loads(handle_slash_command(command, workspace_root=tmp_path))
        assert payload["runtime_execution_enabled"] is False


def test_model_and_reasoning_commands_do_not_expose_private_cot(tmp_path: Path) -> None:
    current = handle_slash_command("/model current", workspace_root=tmp_path)
    capabilities = handle_slash_command("/model capabilities", workspace_root=tmp_path)
    reasoning = handle_slash_command("/reasoning status", workspace_root=tmp_path)
    combined = "\n".join([current, capabilities, reasoning]).lower()
    assert "private chain-of-thought exposure: never" in combined
    assert "hidden reasoning" not in combined


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


def test_architecture_phase_3_row_is_truthful() -> None:
    text = Path("docs/ARCHITECTURE.md").read_text(encoding="utf-8")
    row = next(line for line in text.splitlines() if line.startswith("| Phase 3 |"))
    assert "target platform architecture" in row
    assert "safe foundation/readiness" in row
    assert "Phase 8 deferred" in row
    assert "runtime semantic/vector search" in row


def test_feature_coverage_matrix_separates_spec_from_implementation() -> None:
    text = Path("docs/FEATURE_COVERAGE_MATRIX.md").read_text(encoding="utf-8")
    assert "Current implementation status" in text
    for row_name, qualifier in {
        "Desktop UI": "contract-only",
        "Web UI": "contract-only",
        "Dashboard": "metadata-only",
        "IDE extension": "deferred",
        "Apple mobile app": "deferred",
        "Android mobile app": "deferred",
        "Semantic/vector memory": "readiness-only",
        "Graph memory/code map": "readiness-only",
        "Recursive CTE graph queries": "specified only",
        "Scheduled automations": "deferred",
        "Hosted/cloud inference": "policy-gated",
        "OpenClaw-style gateway and channels": "metadata/readiness-only",
    }.items():
        row = next(line for line in text.splitlines() if line.startswith(f"| {row_name} |"))
        assert qualifier in row


def test_acceptance_and_local_validation_wording_are_truthful() -> None:
    acceptance = Path("docs/ACCEPTANCE_TESTS_BY_PHASE.md").read_text(encoding="utf-8")
    assert "Completed Phase 3 A-P safe foundation/readiness acceptance" in acceptance
    assert "Deferred platform acceptance after Phase 3 A-P" in acceptance
    assert "not required" in acceptance

    local_gate = Path("docs/LOCAL_VALIDATION_GATE.md").read_text(encoding="utf-8")
    assert "CI triggers are configured" in local_gate
    assert "hosted CI may stay red or unavailable" in local_gate
    assert "Local validation evidence is required" in local_gate
    assert "raiker --prompt \"/model current\"" in local_gate
    assert "raiker --prompt \"/graph-readiness --json\"" in local_gate


def test_mock_launch_command_is_test_only_truthful(tmp_path: Path) -> None:
    catalog = Path("docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md").read_text(encoding="utf-8")
    assert "/launch --provider mock --model mock-deterministic" in catalog
    assert "test-only" in catalog.lower()
    assert "deterministic_test_provider_requires_test_mode" in catalog
    output = handle_slash_command("/launch --provider mock --model mock-deterministic", workspace_root=tmp_path)
    assert "deterministic_test_provider_requires_test_mode" in output
