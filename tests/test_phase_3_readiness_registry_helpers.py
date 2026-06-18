from __future__ import annotations

from dataclasses import dataclass

from raiker.approvals.readiness_registry import (
    approval_readiness_summary,
    render_approval_readiness,
)
from raiker.channels.readiness_registry import channel_readiness_summary, render_channel_readiness
from raiker.graph.readiness_registry import graph_readiness_summary, render_graph_readiness
from raiker.memory.readiness_registry import semantic_memory_readiness_summary
from raiker.plugins.readiness_registry import plugin_readiness_summary
from raiker.readiness.registry import (
    get_readiness_by_id,
    render_readiness_records,
    sort_readiness_records,
    summarize_readiness_records,
)
from raiker.storage.cleanup_readiness_registry import cleanup_readiness_summary


@dataclass(frozen=True)
class DummyReadinessRecord:
    readiness_id: str
    blockers: tuple[str, ...]
    required_gates: tuple[str, ...]


def test_sort_readiness_records_is_deterministic_by_readiness_id() -> None:
    records = [
        DummyReadinessRecord("ready_c", ("blocked",), ("gate",)),
        DummyReadinessRecord("ready_a", ("blocked",), ("gate",)),
        DummyReadinessRecord("ready_b", ("blocked",), ("gate",)),
    ]

    assert [record.readiness_id for record in sort_readiness_records(records)] == ["ready_a", "ready_b", "ready_c"]


def test_get_readiness_by_id_returns_match_or_none() -> None:
    records = [
        DummyReadinessRecord("ready_a", ("blocked",), ("gate",)),
        DummyReadinessRecord("ready_b", ("blocked",), ("gate",)),
    ]

    assert get_readiness_by_id(records, "ready_b") == records[1]
    assert get_readiness_by_id(records, "missing") is None


def test_summarize_readiness_records_preserves_latest_count_and_metadata_only_shape() -> None:
    records = [
        DummyReadinessRecord("ready_a", ("first", "second"), ("gate_a",)),
        DummyReadinessRecord("ready_b", ("first",), ("gate_a", "gate_b")),
    ]

    assert summarize_readiness_records(
        records,
        latest_key="latest_readiness_id",
        count_key="readiness_record_count",
        metadata_only_key="readiness_contract_available",
    ) == {
        "readiness_contract_available": True,
        "readiness_record_count": 2,
        "latest_readiness_id": "ready_b",
        "metadata_only": True,
        "blocker_count": 1,
        "required_gate_count": 2,
    }


def test_render_readiness_records_preserves_mapping_order() -> None:
    rendered = render_readiness_records({"a": True, "b": 2, "c": "value"})

    assert rendered == ["a: True", "b: 2", "c: value"]


def test_helper_use_preserves_representative_slice_j_through_o_summary_shapes(tmp_path) -> None:  # type: ignore[no-untyped-def]
    summaries = [
        graph_readiness_summary(workspace_root=tmp_path),
        semantic_memory_readiness_summary(workspace_root=tmp_path),
        approval_readiness_summary(workspace_root=tmp_path),
        cleanup_readiness_summary(workspace_root=tmp_path),
        plugin_readiness_summary(workspace_root=tmp_path),
        channel_readiness_summary(workspace_root=tmp_path),
    ]

    for summary in summaries:
        assert summary["metadata_only"] is True
        assert summary["latest_readiness_id"]
        assert summary["blocker_count"] > 0
        assert summary["required_gate_count"] > 0
        assert summary["runtime_execution_enabled"] is False


def test_helper_use_preserves_representative_render_output_shapes(tmp_path) -> None:  # type: ignore[no-untyped-def]
    rendered = [
        render_graph_readiness(workspace_root=tmp_path),
        render_approval_readiness(workspace_root=tmp_path),
        render_channel_readiness(workspace_root=tmp_path),
    ]

    for output in rendered:
        assert "persistence: metadata_only_optional_sqlite" in output
        assert "metadata_only: True" in output
        assert "runtime_execution_enabled: False" in output


def test_registry_helpers_do_not_create_sqlite_tables_or_runtime_state(tmp_path) -> None:  # type: ignore[no-untyped-def]
    records = [DummyReadinessRecord("ready_a", ("blocked",), ("gate",))]
    before_paths = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    sort_readiness_records(records)
    get_readiness_by_id(records, "ready_a")
    summarize_readiness_records(
        records,
        latest_key="latest_readiness_id",
        count_key="readiness_record_count",
        metadata_only_key="readiness_contract_available",
    )
    render_readiness_records({"runtime_execution_enabled": False})

    after_paths = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    assert after_paths == before_paths
