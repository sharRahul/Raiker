from __future__ import annotations

import json

from raiker.cli.commands import handle_slash_command


def test_phase_3_read_only_terminal_commands(tmp_path) -> None:  # type: ignore[no-untyped-def]
    assert "Workspace inspection:" in handle_slash_command("/workspace", workspace_root=tmp_path)
    assert "desktop: UIActionEnvelope" in handle_slash_command("/clients", workspace_root=tmp_path)
    assert "Plugin registration plans:" in handle_slash_command("/plugins", workspace_root=tmp_path)
    assert "/workspace-view" in handle_slash_command("/help", workspace_root=tmp_path)


def test_workspace_view_command_is_read_only_and_validates_usage(tmp_path) -> None:  # type: ignore[no-untyped-def]
    before = handle_slash_command("/workspace", workspace_root=tmp_path)
    output = handle_slash_command("/workspace-view", workspace_root=tmp_path)
    after = handle_slash_command("/workspace", workspace_root=tmp_path)
    assert "Workspace view:" in output
    assert "read_only: True" in output
    assert "plugin_execution_enabled: False" in output
    assert before == after
    assert (
        handle_slash_command("/workspace-view --format json", workspace_root=tmp_path)
        == "Usage: /workspace-view"
    )


def test_plugin_plan_command_validates_without_execution(tmp_path) -> None:  # type: ignore[no-untyped-def]
    manifest = tmp_path / "raiker-plugin.json"
    manifest.write_text(
        json.dumps(
            {
                "plugin_id": "com.example.safe",
                "name": "Safe",
                "version": "1",
                "permissions": ["tool:read_file"],
            }
        ),
        encoding="utf-8",
    )
    output = handle_slash_command(f"/plugin-plan {manifest}", workspace_root=tmp_path)
    assert "status: planned" in output
    assert "execution_enabled: False" in output
    assert (
        handle_slash_command("/plugin-plan", workspace_root=tmp_path)
        == "Usage: /plugin-plan <manifest_path>"
    )


def test_plugin_plan_accepts_utf8_bom_manifest(tmp_path) -> None:  # type: ignore[no-untyped-def]
    manifest = tmp_path / "raiker-plugin-bom.json"
    manifest.write_text(
        json.dumps(
            {
                "plugin_id": "com.example.safe-bom",
                "name": "Safe BOM",
                "version": "1",
                "permissions": [],
            }
        ),
        encoding="utf-8-sig",
    )
    output = handle_slash_command(f"/plugin-plan {manifest}", workspace_root=tmp_path)
    assert "status: planned" in output
    assert "execution_enabled: False" in output
