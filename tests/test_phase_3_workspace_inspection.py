from __future__ import annotations

from raiker.workspace.inspection import inspect_workspace


def test_desktop_web_dashboard_return_equivalent_read_only_shapes(tmp_path) -> None:  # type: ignore[no-untyped-def]
    summaries = [
        inspect_workspace(client, workspace_root=tmp_path)
        for client in ("desktop", "web", "dashboard")
    ]
    key_sets = [set(summary) for summary in summaries]
    assert key_sets[0] == key_sets[1] == key_sets[2]
    for summary in summaries:
        assert summary["contract"]["read_only"] is True
        assert summary["contract"]["shared_contract_path"] is True
        assert summary["contract"]["client"]["privileged"] is False


def test_inspection_does_not_mutate_runtime_or_activate_gated_features(tmp_path) -> None:  # type: ignore[no-untyped-def]
    before = inspect_workspace("desktop", workspace_root=tmp_path)
    after = inspect_workspace("dashboard", workspace_root=tmp_path)
    assert after["tasks"] == before["tasks"] == []
    assert after["approvals"] == before["approvals"] == []
    assert after["semantic_memory"]["semantic_writes_enabled"] is False
    assert all(
        connector["default_state"] == "disabled"
        for connector in after["channel_connectors"]
        if connector["connector_id"]
        in {"channel.slack", "channel.email", "channel.teams", "channel.discord", "channel.signal"}
    )
    assert after["capability_gates"]["plugin_execution"]["runtime_enabled"] is False
    assert after["capability_gates"]["remote_execution"]["runtime_enabled"] is False
