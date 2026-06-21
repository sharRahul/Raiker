"""Command list plain-text catalog for the plain terminal client.

This is a lightweight, grouped command catalogue rendered as a transient plain-text catalog
(option B in the Q1 spec). A searchable, keyboard-driven palette is deferred to a
later slice. It only describes commands; it never executes them and never creates new
command semantics. Selecting/submitting a command is the user's responsibility through
the existing input parser and command handlers.
"""

from __future__ import annotations

from dataclasses import dataclass

from raiker.terminal.accessibility import TerminalProfile, safe_lines


@dataclass(frozen=True)
class CommandEntry:
    name: str
    purpose: str
    status: str = "available"


@dataclass(frozen=True)
class CommandGroup:
    title: str
    commands: tuple[CommandEntry, ...]


COMMAND_GROUPS: tuple[CommandGroup, ...] = (
    CommandGroup(
        "Core",
        (
            CommandEntry("/help", "Show command help in the main panel."),
            CommandEntry("/commands", "Show this grouped command plain-text catalog."),
            CommandEntry("/home", "Return to the welcome/home screen."),
            CommandEntry("/panels", "List optional panels you can open."),
            CommandEntry("/panel <id>", "Open an optional panel in its region."),
            CommandEntry("/mode <minimal|standard|advanced>", "Switch TUI mode variant."),
            CommandEntry("/keys", "Show keyboard shortcuts and their commands."),
            CommandEntry("/status", "Show runtime/workspace status."),
            CommandEntry("/clients", "Show client contract parity."),
        ),
    ),
    CommandGroup(
        "Model",
        (
            CommandEntry("/providers", "List configured provider profiles."),
            CommandEntry("/models", "List model profiles and live availability."),
            CommandEntry("/model current", "Show the selected model profile."),
            CommandEntry("/model use <profile_id>", "Select a model profile (policy-gated)."),
            CommandEntry("/model health", "Check selected model health."),
            CommandEntry("/model capabilities", "Show selected model capabilities."),
        ),
    ),
    CommandGroup(
        "Reasoning",
        (
            CommandEntry("/reasoning status", "Show reasoning control availability."),
            CommandEntry("/reasoning set <mode-or-effort>", "Set reasoning controls."),
            CommandEntry("/reasoning off", "Disable reasoning controls."),
        ),
    ),
    CommandGroup(
        "Workspace",
        (
            CommandEntry("/workspace", "Show workspace inspection summary."),
            CommandEntry("/workspace-view", "Show read-only workspace view."),
            CommandEntry("/execution-profiles", "List execution profiles."),
            CommandEntry("/capabilities", "List phase capability gates."),
        ),
    ),
    CommandGroup(
        "Tasks and Events",
        (
            CommandEntry("/tasks", "List tracked tasks."),
            CommandEntry("/events", "List recent events."),
            CommandEntry("/checkpoints", "List checkpoint summaries."),
        ),
    ),
    CommandGroup(
        "Approvals",
        (
            CommandEntry("/approvals", "List pending approvals."),
            CommandEntry("/approve <id>", "Resolve an approval (approve)."),
            CommandEntry("/deny <id>", "Resolve an approval (deny)."),
            CommandEntry("/approval-previews", "List approval planning previews."),
            CommandEntry("/approval-audit [--summary]", "Show preview-only approval audit."),
        ),
    ),
    CommandGroup(
        "Memory",
        (
            CommandEntry("/memory", "Show governed memory status."),
            CommandEntry("/semantic-memory", "Show semantic memory status."),
            CommandEntry("/memory-review [--summary]", "Show memory review queue."),
        ),
    ),
    CommandGroup(
        "Graph and Readiness",
        (
            CommandEntry("/graph-status", "Show graph/codemap status."),
            CommandEntry("/graph-plan", "Show graph dry-run plan."),
            CommandEntry("/graph-readiness [--summary|--json]", "Show graph indexing readiness."),
            CommandEntry("/memory-readiness [--summary|--json]", "Show memory write readiness."),
            CommandEntry("/approval-readiness [--summary|--json]", "Show approval readiness."),
            CommandEntry("/cleanup-readiness [--summary|--json]", "Show cleanup readiness."),
            CommandEntry("/remote-readiness [--summary|--json]", "Show remote readiness."),
            CommandEntry("/plugin-readiness [--summary|--json]", "Show plugin readiness."),
            CommandEntry("/channel-readiness [--summary|--json]", "Show channel readiness."),
        ),
    ),
    CommandGroup(
        "Storage Lifecycle",
        (
            CommandEntry("/storage-lifecycle [--summary|--graph|--memory]", "Lifecycle summary."),
            CommandEntry("/storage-lifecycle-retention [--summary]", "Retention metadata."),
            CommandEntry("/storage-lifecycle-cleanup-preview [--summary]", "Cleanup preview."),
            CommandEntry("/storage-lifecycle-handoff [--summary]", "Handoff metadata."),
            CommandEntry("/storage-lifecycle-evidence", "Lifecycle evidence records."),
            CommandEntry("/storage-lifecycle-policy-simulation", "Lifecycle policy simulation."),
            CommandEntry("/rollback-plan", "Show rollback planning surfaces."),
        ),
    ),
    CommandGroup(
        "Review and Proposals",
        (
            CommandEntry("/review [--summary]", "Run local read-only code review."),
            CommandEntry("/proposals", "List saved review proposals."),
            CommandEntry("/proposal <proposal_id>", "Show one proposal record."),
        ),
    ),
    CommandGroup(
        "Plugins and Channels",
        (
            CommandEntry("/plugins", "Show plugin registration planning status."),
            CommandEntry("/plugin-plan <manifest_path>", "Plan plugin registration (read-only)."),
            CommandEntry("/channels", "Show disabled/readiness channel status."),
        ),
    ),
    CommandGroup(
        "Diagnostics",
        (CommandEntry("/doctor", "Show diagnostics in the main panel."),),
    ),
    CommandGroup(
        "Exit",
        (
            CommandEntry("/q", "Exit the shell safely."),
            CommandEntry("/quit", "Exit the shell safely."),
            CommandEntry("/exit", "Exit the shell safely."),
        ),
    ),
)


def palette_lines(profile: TerminalProfile) -> list[str]:
    """Return the grouped command plain-text catalog as plain, accessible text lines."""

    lines: list[str] = ["Command palette (plain-text catalog) — submit a command to run it:"]
    for group in COMMAND_GROUPS:
        lines.append("")
        lines.append(f"[{group.title}]")
        for entry in group.commands:
            status = "" if entry.status == "available" else f" ({entry.status})"
            lines.append(f"  {entry.name} - {entry.purpose}{status}")
    lines.append("")
    lines.append("Searchable keyboard palette is deferred to a later slice.")
    return safe_lines(lines, profile)


def render_command_palette(profile: TerminalProfile | None = None) -> str:
    """Render the command plain-text catalog as text for main-panel/transient display."""

    from raiker.terminal.accessibility import TerminalProfile as _TP

    return "\n".join(palette_lines(profile or _TP()))
