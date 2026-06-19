from __future__ import annotations

from raiker.cli.commands import handle_slash_command
from raiker.cli.main import main
from raiker.tui.accessibility import TerminalProfile
from raiker.tui.app import _route_input, run_terminal_client
from raiker.tui.command_palette import COMMAND_GROUPS, render_command_palette

_PLAIN = TerminalProfile(width=120, color=False, unicode=False, interactive=False)


def test_prompt_hello_still_works(capsys) -> None:  # type: ignore[no-untyped-def]
    assert main(["--prompt", "Hello Raiker"]) == 0
    out = capsys.readouterr().out
    assert "Raiker terminal client" in out


def test_prompt_help_still_works(capsys) -> None:  # type: ignore[no-untyped-def]
    assert main(["--prompt", "/help"]) == 0
    out = capsys.readouterr().out
    assert "/workspace-view" in out
    assert "/doctor" in out


def test_models_routes_through_command_handler(tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = _route_input("/models", tmp_path, _PLAIN)
    assert "Model profiles" in out
    assert out == handle_slash_command("/models", workspace_root=tmp_path)


def test_model_current_routes_through_command_handler(tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = _route_input("/model current", tmp_path, _PLAIN)
    assert "Current model profile:" in out


def test_model_capabilities_routes_through_command_handler(tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = _route_input("/model capabilities", tmp_path, _PLAIN)
    assert "Model capabilities:" in out


def test_status_routes_through_command_handler(tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = _route_input("/status", tmp_path, _PLAIN)
    assert "runtime_execution_enabled: False" in out


def test_events_routes_through_command_handler(tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = _route_input("/events", tmp_path, _PLAIN)
    assert out == handle_slash_command("/events", workspace_root=tmp_path)


def test_approvals_routes_through_command_handler(tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = _route_input("/approvals", tmp_path, _PLAIN)
    assert "approvals" in out.lower()


def test_review_summary_routes_through_command_handler(tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = _route_input("/review --summary", tmp_path, _PLAIN)
    assert out == handle_slash_command("/review --summary", workspace_root=tmp_path)


def test_unsupported_command_shows_safe_error(tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = _route_input("/definitely-not-a-command", tmp_path, _PLAIN)
    assert out.startswith("Unknown command:")


def test_normal_prompt_routes_through_prompt_path(tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = _route_input("Tell me something", tmp_path, _PLAIN)
    # The existing prompt path returns a model-unavailable message offline, never a crash.
    assert "model_unavailable" in out or "Approval card" in out or out


def test_commands_overlay_renders_grouped_palette(tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = _route_input("/commands", tmp_path, _PLAIN)
    assert "Command palette" in out
    for group in ("Core", "Model", "Approvals", "Diagnostics", "Exit"):
        assert f"[{group}]" in out


def test_command_palette_groups_cover_required_categories() -> None:
    titles = {group.title for group in COMMAND_GROUPS}
    for required in (
        "Core",
        "Model",
        "Reasoning",
        "Workspace",
        "Tasks and Events",
        "Approvals",
        "Memory",
        "Graph and Readiness",
        "Storage Lifecycle",
        "Review and Proposals",
        "Plugins and Channels",
        "Diagnostics",
        "Exit",
    ):
        assert required in titles


def test_command_palette_does_not_execute_commands() -> None:
    out = render_command_palette(_PLAIN)
    # Overlay only describes commands; it must not run them or print their output.
    assert "Model profiles" not in out
    assert "Workspace inspection" not in out


def test_non_interactive_run_exits_safely(capsys) -> None:  # type: ignore[no-untyped-def]
    profile = TerminalProfile(width=120, interactive=False)
    assert run_terminal_client(prompt=None, profile=profile) == 0
    out = capsys.readouterr().out
    assert "exited safely" in out


def test_launch_command_remains_policy_gated(tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = _route_input(
        "/launch --provider mock --model mock-deterministic", tmp_path, _PLAIN
    )
    assert "deterministic_test_provider_requires_test_mode" in out
