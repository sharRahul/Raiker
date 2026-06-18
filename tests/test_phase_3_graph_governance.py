from __future__ import annotations

from typing import cast

from raiker.cli.commands import handle_slash_command
from raiker.graph.governance import graph_governance_status
from raiker.graph.planner import GraphCodemapPlanner, create_graph_codemap_plan
from raiker.phase_gates import get_capability_gate
from raiker.workspace.inspection import inspect_workspace


def test_graph_runtime_indexing_remains_disabled() -> None:
    assert get_capability_gate("graph_codemap_indexing").runtime_enabled is False
    status = graph_governance_status()
    assert status["graph_indexing_enabled"] is False
    assert status["planning_available"] is True
    assert status["runtime_indexing_enabled"] is False
    assert status["background_indexing_enabled"] is False


def test_graph_plan_is_dry_run_and_writes_no_durable_records(tmp_path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "src.py").write_text("print('safe')\n", encoding="utf-8")
    plan = create_graph_codemap_plan(tmp_path).to_dict()
    assert plan["can_index"] is False
    assert plan["runtime_indexing_enabled"] is False
    assert plan["requires_approval"] is True
    assert plan["included_paths"] == ["src.py"]
    assert "disabled" in str(plan["policy_decision"])


def test_graph_path_policy_denies_unsafe_paths(tmp_path) -> None:  # type: ignore[no-untyped-def]
    outside = tmp_path.parent / "outside.py"
    outside.write_text("x=1", encoding="utf-8")
    (tmp_path / ".hidden.py").write_text("x=1", encoding="utf-8")
    (tmp_path / "big.py").write_text("x" * 20, encoding="utf-8")
    (tmp_path / "bin.dat").write_bytes(b"abc\x00def")
    planner = GraphCodemapPlanner(tmp_path, max_file_size_bytes=8)
    assert planner.decide_path(outside).reason == "outside_workspace_root"
    assert planner.decide_path("../outside.py").reason == "outside_workspace_root"
    assert planner.decide_path(".hidden.py").reason == "hidden_or_system_path"
    assert planner.decide_path("big.py").reason == "file_too_large"
    assert planner.decide_path("bin.dat").reason == "binary_file"


def test_graph_plan_excludes_default_ignored_dirs_and_symlink_escape(tmp_path) -> None:  # type: ignore[no-untyped-def]
    for dirname in (".git", ".venv", "node_modules", "__pycache__", "build", "dist", "target", "vendor"):
        ignored = tmp_path / dirname
        ignored.mkdir()
        (ignored / "ignored.py").write_text("x=1", encoding="utf-8")
    outside = tmp_path.parent / "outside-link-target"
    outside.mkdir(exist_ok=True)
    (tmp_path / "escape").symlink_to(outside, target_is_directory=True)
    plan = create_graph_codemap_plan(tmp_path).to_dict()
    excluded_paths = cast(list[dict[str, object]], plan["excluded_paths"])
    reasons = {item["reason"] for item in excluded_paths}
    assert "symlink_escape" in reasons
    assert {f"excluded_directory:{name}" for name in (".git", ".venv", "node_modules", "__pycache__", "build", "dist", "target", "vendor")} <= reasons


def test_graph_cli_and_workspace_view_are_read_only(tmp_path) -> None:  # type: ignore[no-untyped-def]
    before = inspect_workspace("terminal", workspace_root=tmp_path)
    assert "Graph/codemap status:" in handle_slash_command("/graph-status", workspace_root=tmp_path)
    output = handle_slash_command("/graph-plan", workspace_root=tmp_path)
    assert "Graph/codemap dry-run plan:" in output
    assert "can_index: False" in output
    after = inspect_workspace("terminal", workspace_root=tmp_path)
    assert after["graph_codemap"]["graph_indexing_enabled"] is False
    assert after["graph_codemap"]["planning_available"] is True
    assert after["runtime_status"] == before["runtime_status"]
