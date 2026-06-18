from __future__ import annotations

import json
from pathlib import Path

from raiker.cli.commands import handle_slash_command
from raiker.storage.lifecycle_evidence import create_evidence_bundle, create_policy_simulation
from raiker.storage.lifecycle_registry import (
    create_lifecycle_evidence_bundle,
    create_lifecycle_policy_simulation,
    get_lifecycle_evidence_bundle,
    get_lifecycle_policy_simulation,
    lifecycle_evidence_summary,
    list_lifecycle_evidence_bundles,
    list_lifecycle_policy_simulations,
)
from raiker.storage.sqlite import SQLiteStore


def test_evidence_bundle_ids_are_deterministic_redacted_and_json_safe() -> None:
    one = create_evidence_bundle(
        workspace_id="workspace",
        source_lifecycle_ids=["b", "a"],
        source_retention_policy_ids=["p1"],
        source_cleanup_preview_ids=["c1"],
        source_approval_handoff_ids=["h1"],
        record_counts={"z": 2, "a": 1},
        status_counts={"runtime_blocked": 1},
        redacted_summary={"api_token": "secret-token", "safe": "ok"},
    )
    two = create_evidence_bundle(
        workspace_id="workspace",
        source_lifecycle_ids=["a", "b"],
        source_retention_policy_ids=["p1"],
        source_cleanup_preview_ids=["c1"],
        source_approval_handoff_ids=["h1"],
        record_counts={"a": 1, "z": 2},
        status_counts={"runtime_blocked": 1},
        redacted_summary={"safe": "ok", "api_token": "other-secret"},
    )
    assert one.evidence_id == two.evidence_id
    assert one.evidence_id.startswith("sleb_")
    encoded = json.dumps(one.to_dict(), sort_keys=True)
    assert "secret-token" not in encoded
    assert "other-secret" not in encoded
    assert one.redacted_summary["api_token"] == "[REDACTED]"
    assert one.metadata_only is True
    assert one.export_only is True
    assert one.can_execute_now is False
    assert one.execution_enabled is False
    assert all(value is False for value in one.disabled_execution_flags.values())


def test_policy_simulation_ids_are_deterministic_and_non_executing() -> None:
    one = create_policy_simulation(
        workspace_id="workspace",
        input_retention_policy_ids=["p2", "p1"],
        input_cleanup_preview_ids=["c1"],
        would_expire_count=2,
        would_cleanup_count=3,
        would_handoff_count=1,
        blocked_reasons=["token=abc", "cleanup disabled"],
    )
    two = create_policy_simulation(
        workspace_id="workspace",
        input_retention_policy_ids=["p1", "p2"],
        input_cleanup_preview_ids=["c1"],
        would_expire_count=2,
        would_cleanup_count=3,
        would_handoff_count=1,
        blocked_reasons=["cleanup disabled", "token=abc"],
    )
    assert one.simulation_id == two.simulation_id
    assert one.simulation_id.startswith("slps_")
    assert json.loads(json.dumps(one.to_dict(), sort_keys=True))["simulation_id"] == one.simulation_id
    assert one.blocked_reasons == sorted(one.blocked_reasons)
    assert one.metadata_only is True
    assert one.simulation_only is True
    assert one.execution_enabled is False
    assert all(value is False for value in one.disabled_execution_flags.values())


def test_invalid_input_rejected() -> None:
    try:
        create_evidence_bundle(workspace_id="", source_lifecycle_ids=[])
    except ValueError as exc:
        assert "workspace_id_required" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_registry_create_list_get_and_summary(tmp_path) -> None:  # type: ignore[no-untyped-def]
    before = lifecycle_evidence_summary(workspace_root=tmp_path)
    evidence = create_lifecycle_evidence_bundle(workspace_root=tmp_path)
    simulation = create_lifecycle_policy_simulation(workspace_root=tmp_path)
    assert get_lifecycle_evidence_bundle(evidence.evidence_id) == evidence
    assert get_lifecycle_policy_simulation(simulation.simulation_id) == simulation
    assert list_lifecycle_evidence_bundles() == sorted(
        list_lifecycle_evidence_bundles(), key=lambda item: item.evidence_id
    )
    assert list_lifecycle_policy_simulations() == sorted(
        list_lifecycle_policy_simulations(), key=lambda item: item.simulation_id
    )
    after = lifecycle_evidence_summary(workspace_root=tmp_path)
    assert after["lifecycle_evidence_bundle_count"] >= before["lifecycle_evidence_bundle_count"]
    assert after["execution_enabled"] is False


def test_cli_evidence_and_policy_simulation_outputs_are_json_safe(tmp_path) -> None:  # type: ignore[no-untyped-def]
    evidence = handle_slash_command("/storage-lifecycle-evidence", workspace_root=tmp_path)
    assert "Storage lifecycle evidence bundles" in evidence
    assert "execution_enabled: False" in evidence
    assert "Usage:" in handle_slash_command(
        "/storage-lifecycle-evidence --target forbidden", workspace_root=tmp_path
    )
    evidence_summary = handle_slash_command(
        "/storage-lifecycle-evidence --summary", workspace_root=tmp_path
    )
    assert "lifecycle_evidence_bundle_count" in evidence_summary
    evidence_json = json.loads(
        handle_slash_command("/storage-lifecycle-evidence --json", workspace_root=tmp_path)
    )
    assert evidence_json["evidence_id"].startswith("sleb_")
    assert evidence_json["execution_enabled"] is False
    simulation = handle_slash_command(
        "/storage-lifecycle-policy-simulation", workspace_root=tmp_path
    )
    assert "Storage lifecycle policy simulations" in simulation
    simulation_summary = handle_slash_command(
        "/storage-lifecycle-policy-simulation --summary", workspace_root=tmp_path
    )
    assert "lifecycle_policy_simulation_count" in simulation_summary
    simulation_json = json.loads(
        handle_slash_command("/storage-lifecycle-policy-simulation --json", workspace_root=tmp_path)
    )
    assert simulation_json["simulation_id"].startswith("slps_")
    assert simulation_json["execution_enabled"] is False


def test_sqlite_slice_i_tables_exist_and_forbidden_runtime_tables_do_not(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SQLiteStore(tmp_path)
    store.bootstrap()
    tables = store.table_names()
    assert "phase3_storage_lifecycle_evidence_bundles" in tables
    assert "phase3_storage_lifecycle_policy_simulations" in tables
    assert "phase3_storage_lifecycle_evidence_events" in tables
    forbidden = {
        "graph_nodes",
        "graph_edges",
        "vector_embeddings",
        "semantic_memory_durable_writes",
        "rollback_executions",
        "plugin_executions",
        "channel_runtime",
        "approval_relay_runtime",
        "remote_executions",
        "container_executions",
        "cloud_executions",
    }
    assert tables.isdisjoint(forbidden)


def test_catalog_shape_permissions_and_approval_typo() -> None:
    catalog = Path("docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md").read_text(encoding="utf-8")
    assert "| Tool Name | Descriptions | Permissions | Implemented |" in catalog
    assert "approvals:read" not in catalog
    for name in [
        "storage_lifecycle_evidence_bundle",
        "storage_lifecycle_policy_simulation",
        "/storage-lifecycle-evidence",
        "/storage-lifecycle-evidence --summary",
        "/storage-lifecycle-evidence --json",
        "/storage-lifecycle-policy-simulation",
        "/storage-lifecycle-policy-simulation --summary",
        "/storage-lifecycle-policy-simulation --json",
    ]:
        assert name in catalog
