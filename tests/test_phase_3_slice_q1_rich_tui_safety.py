from __future__ import annotations

import ast
from pathlib import Path

from raiker.cli.commands import handle_slash_command
from raiker.tui.accessibility import TerminalProfile
from raiker.tui.status_bar import StatusBarConfig, StatusBarRenderer, StatusContext

# Pure presentation modules that must never gain runtime authority.
_PANEL_MODULES = [
    "raiker/tui/layout.py",
    "raiker/tui/transcript.py",
    "raiker/tui/welcome.py",
    "raiker/tui/render_models.py",
    "raiker/tui/accessibility.py",
    "raiker/tui/command_palette.py",
    "raiker/tui/status_bar.py",
]

_FORBIDDEN_MODULES = {
    "subprocess",
    "socket",
    "requests",
    "urllib",
    "urllib.request",
    "httpx",
    "asyncio",
}


def _imported_names(path: str) -> set[str]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_panel_modules_do_not_import_runtime_or_network() -> None:
    for module in _PANEL_MODULES:
        imported = _imported_names(module)
        leaked = imported & _FORBIDDEN_MODULES
        assert not leaked, f"{module} imports forbidden runtime/network modules: {leaked}"


def test_panel_modules_do_not_import_model_or_tool_runtime() -> None:
    for module in _PANEL_MODULES:
        imported = _imported_names(module)
        for name in imported:
            assert not name.startswith("raiker.models"), f"{module} imports model runtime {name}"
            assert not name.startswith("raiker.tools"), f"{module} imports tool runtime {name}"
            assert not name.startswith("raiker.gateway"), f"{module} imports gateway {name}"


def test_panel_modules_have_no_file_mutation_or_exec() -> None:
    for module in _PANEL_MODULES:
        source = Path(module).read_text(encoding="utf-8")
        for forbidden in ("open(", "Path.write_text", ".write_text(", "os.system", "eval(", "exec("):
            assert forbidden not in source, f"{module} contains forbidden call: {forbidden}"


def test_status_bar_items_are_named_and_configurable() -> None:
    config = StatusBarConfig(fields=["state", "approvals", "network", "clock"])
    rendered = StatusBarRenderer(config).render(StatusContext(approvals=3), clock="00:00")
    assert rendered == "READY | approvals:3 | net:blocked | 00:00"


def test_status_bar_pinned_safety_items_cannot_be_hidden_in_compact() -> None:
    config = StatusBarConfig(
        fields=["state", "task", "approvals", "model", "context", "network", "cost", "clock"],
    )
    compact = StatusBarRenderer(config).render(
        StatusContext(state="RISK", approvals=2, network="blocked"), clock="00:00", compact=True
    )
    # Safety-critical items survive compact rendering even in a risky state.
    assert "RISK" in compact
    assert "approvals:2" in compact
    assert "net:blocked" in compact


def test_status_bar_clock_is_deterministic_when_injected() -> None:
    out = StatusBarRenderer().render(StatusContext(), clock="13:42")
    assert "13:42" in out


def test_status_bar_narrow_width_triggers_compact_overflow() -> None:
    config = StatusBarConfig(
        fields=["state", "task", "approvals", "model", "context", "network", "cost", "clock"],
    )
    out = StatusBarRenderer(config).render(StatusContext(), width=60)
    assert "+" in out  # overflow indicator
    assert "net:blocked" in out


def test_disabled_runtime_flags_remain_false(tmp_path) -> None:  # type: ignore[no-untyped-def]
    status = handle_slash_command("/status", workspace_root=tmp_path)
    assert "runtime_execution_enabled: False" in status
    caps = handle_slash_command("/capabilities", workspace_root=tmp_path)
    assert "disabled" in caps


def test_tui_does_not_create_new_command_semantics() -> None:
    # The palette overlay references only existing slash commands.
    from raiker.tui.command_palette import COMMAND_GROUPS

    for group in COMMAND_GROUPS:
        for entry in group.commands:
            assert entry.name.startswith("/")


def test_default_layout_does_not_leak_sensitive_fields() -> None:
    from raiker.tui.layout import render_home_layout
    from raiker.tui.welcome import WelcomeContent

    out = render_home_layout(
        WelcomeContent(),
        status_line=StatusBarRenderer().render(StatusContext(), clock="00:00"),
        input_hint="? side question | / command",
        profile=TerminalProfile(width=120, color=False),
    )
    for forbidden in ("Authorization", "api_key", "secret", "BEGIN PRIVATE KEY"):
        assert forbidden not in out
