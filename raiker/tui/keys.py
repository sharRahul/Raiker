"""Keyboard shortcut registry for the Rich TUI.

docs/UI_UX_DESIGN_SPEC.md documents a keyboard shortcut table, and the spec rule
"All actions remain accessible via command or API". This turn-based rich shell renders a
fresh frame per turn and reads a full input line, so it cannot portably capture raw
Ctrl-chords mid-prompt. We therefore honour the spec by giving every documented shortcut
an equivalent typed shell command, and by displaying the shortcut next to it. Capability
parity is preserved: anything a key would do is reachable by command.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KeyBinding:
    shortcut: str
    command: str
    description: str


# Order matters for the rendered keys reference.
KEY_BINDINGS: tuple[KeyBinding, ...] = (
    KeyBinding("Ctrl+C", "(interrupt)", "Request interrupt/pause at safe boundary."),
    KeyBinding("Esc", "(cancel)", "Cancel current input."),
    KeyBinding("Esc Esc", "/view checkpoints", "Open rewind/checkpoint menu."),
    KeyBinding("Ctrl+L", "/clear", "Clear/redraw screen."),
    KeyBinding("Ctrl+R", "/sessions", "Resume/fork session picker."),
    KeyBinding("Ctrl+P", "/commands", "Command palette."),
    KeyBinding("Ctrl+A", "/view approvals", "Approvals inbox."),
    KeyBinding("Ctrl+T", "/view tasks", "Task manager."),
    KeyBinding("Ctrl+E", "/view events", "Event viewer."),
    KeyBinding("Ctrl+M", "/view memory", "Memory inspector."),
    KeyBinding("Ctrl+G", "/view graph", "Graph/codemap inspector."),
    KeyBinding("Ctrl+K", "/view context", "Context usage panel."),
    KeyBinding("Shift+Tab", "/approval-mode", "Cycle permission/approval mode."),
    KeyBinding("? prefix", "? <question>", "Ask a side question."),
)


def keys_reference_lines() -> list[str]:
    lines = ["Keyboard shortcuts (each also runs as a typed command):", ""]
    width = max(len(b.shortcut) for b in KEY_BINDINGS)
    for binding in KEY_BINDINGS:
        lines.append(
            f"  {binding.shortcut.ljust(width)}  {binding.command.ljust(20)} {binding.description}"
        )
    return lines
