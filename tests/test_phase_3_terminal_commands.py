from __future__ import annotations

import json

from raiker.cli.commands import handle_slash_command


def test_phase_3_read_only_terminal_commands(tmp_path) -> None:  # type: ignore[no-untyped-def]
    assert "Workspace inspection:" in handle_slash_command("/workspace", workspace_root=tmp_path)
    assert "desktop: UIActionEnvelope" in handle_slash_command("/clients", workspace_root=tmp_path)
    assert "Plugin registration plans:" in handle_slash_command("/plugins", workspace_root=tmp_path)


def test_plugin_plan_command_validates_without_execution(tmp_path) -> None:  # type: ignore[no-untyped-def]
    manifest = tmp_path / "raiker-plugin.json"
    manifest.write_text(json.dumps({"plugin_id": "com.example.safe", "name": "Safe", "version": "1", "permissions": ["tool:read_file"]}), encoding="utf-8")
    output = handle_slash_command(f"/plugin-plan {manifest}", workspace_root=tmp_path)
    assert "status: planned" in output
    assert "execution_enabled: False" in output
    assert handle_slash_command("/plugin-plan", workspace_root=tmp_path) == "Usage: /plugin-plan <manifest_path>"
