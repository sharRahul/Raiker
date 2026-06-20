# Phase 3 Slice Q1 — Documented Default Rich TUI Access Shell

Status: `implemented_verified` for the documented default layout only.

## Objective

Implement the documented default Rich TUI layout from `docs/UI_UX_DESIGN_SPEC.md` as
Raiker's minimum usable terminal interface: a compact welcome/workspace view, recent
activity, an input area, and a configurable status bar. The default shell must give
access to every currently implemented Raiker capability through the existing prompt,
slash-command, command, and gateway paths, without showing every capability as a
permanent developer panel.

This slice is **not** a full advanced Rich TUI implementation.

## Current truth

- `raiker` is the global terminal entry point; `raiker/cli/main.py` calls
  `raiker.tui.app.run_terminal_client`.
- Before Q1, `raiker/tui/app.py` was a plain print/input loop and
  `raiker/tui/status_bar.py` had a basic status renderer.
- Phase 3 slices A–P are already implemented and documented, so Q1 is the correct
  continuation label (not "Slice B", which is already used for approval planning preview).
- All runtime execution and unsafe capabilities remain disabled.

## Default layout scope

Exactly four required panels, aligned with `docs/UI_UX_DESIGN_SPEC.md`:

1. **Primary / Main Panel** — welcome text, workspace root, current mode
   (`Rich TUI default access shell`), model/effort, and rendered prompt/command results.
2. **Activity Panel** — compact, safe summary: workspace, client mode
   (`rich_tui_default`), runtime safety state (`runtime execution disabled`), network
   state, approval count, model/profile summary, last safe event, and a help hint.
3. **Input Panel** — the documented prompt hints
   (`? side question | / command | normal prompt | ! command proposal | @ file mention`).
4. **Status Bar Panel** — configurable named status items with pinned safety fields.

Layout variants:

- **Standard** — main panel left/larger, activity panel right/smaller, input below, status bottom.
- **Narrow** — main first, activity compacted/stacked, input visible, compact status, safety fields retained.
- **No-colour / low-colour** — text labels retained, no colour-only meaning, ASCII-safe fallback.
- **Non-interactive** — `raiker --prompt ...` stays line-oriented and exits; non-interactive stdin exits safely; no full-screen trap.

Fallback activates when rich is unavailable, the terminal is non-interactive, a
capability check fails, `RAIKER_TUI=plain` is set, or tests request it.

## Non-goals

This does not implement the full advanced Rich TUI, extended developer panels, plugin
panels, custom panel registry, desktop/web/mobile apps, REST API, external channels,
runtime execution, proposal execution, approval execution, graph indexing,
semantic/vector writes, remote/container/cloud execution, shell/process execution, or
direct network execution.

Deferred: persistent advanced dockable panels, custom/plugin/user-built panels, advanced
drawers, dashboard-style multi-pane views, theme marketplace, full screen routing, full
mouse-driven UI, full async live task UI, background daemons/watchers, external channel
UI runtime, and desktop/web/mobile/IDE/voice/browser-extension apps. A searchable
keyboard-driven command palette is deferred to a later slice (Q1 ships a grouped command
list overlay via `/commands` / `/help`).

## Accessibility requirements

- No colour-only meaning; labels for state, risk, network, approvals, disabled runtime.
- Readable plain-text output; no-colour and ASCII-safe fallback.
- Narrow-terminal fallback that does not crash.
- Keyboard-first operation; safe `Ctrl+C`/`Ctrl+D` handling; focus not trapped.
- Approval/risk/network states visible as text; command errors readable.
- Tests prove safety labels remain present with colour disabled.

## Model / tool / command access rules

- Q1 provides model accessibility, not a new model runtime.
- The status bar shows the current model/profile where available; `/models`,
  `/model current`, `/model health`, `/model capabilities`, `/model use ...` route through
  existing handlers.
- Normal prompts route through `submit_terminal_prompt()` → Agent Gateway → runtime/model path.
- Slash commands route through `handle_slash_command()`; results render in the Main Panel
  or a transient overlay.
- The TUI panel modules must not instantiate model clients, call llama.cpp/Ollama/LM
  Studio/OpenAI-compatible/OpenRouter, import or use `httpx` for model calls, start model
  servers, run shell commands, or invent a new model registry.

## Safety boundaries

The TUI exposes access to existing commands but creates no new runtime authority. Every
action routes through existing CLI handlers, the Agent Gateway, contracts, ToolBroker,
PolicyEngine, approval boundaries, event logging, and storage services. TUI panel modules
do not call tools, models, plugins, memory/graph writes, channel connectors, shell,
subprocess, sockets, or network APIs directly; do not mutate files; and do not execute
approvals or proposals.

All disabled runtime flags remain false: `plugin_execution_enabled`,
`graph_indexing_enabled`, `semantic_memory_writes_enabled`, `vector_writes_enabled`,
`embedding_creation_enabled`, `approval_execution_enabled`,
`approval_relay_runtime_enabled`, `cleanup_execution_enabled`,
`rollback_execution_enabled`, `external_channels_enabled`, `notifications_enabled`,
`remote_execution_enabled`, `container_execution_enabled`, `cloud_execution_enabled`,
`process_execution_enabled`, `shell_execution_enabled`, `network_execution_enabled`,
`runtime_execution_enabled`.

## Events

Q1 adds **no new events**. The default shell reuses existing command/runtime events only
(for example, the model/prompt/command events already emitted by the handlers it calls).
No raw prompt text, file contents, diffs, secrets, tool output, private reasoning, or
chain-of-thought is introduced into any payload.

## Storage impact

Q1 adds no new durable storage and no new SQLite tables. No storage is added for panel
layouts, themes, custom panels, command history, transcripts, or user preferences.

## Tests

- `tests/test_phase_3_slice_q1_rich_tui_default_layout.py`
- `tests/test_phase_3_slice_q1_rich_tui_accessibility.py`
- `tests/test_phase_3_slice_q1_rich_tui_command_access.py`
- `tests/test_phase_3_slice_q1_rich_tui_safety.py`
- `tests/test_phase_3_slice_q1_docs_truthfulness.py`

## Validation gate

```text
python -m ruff check .
python -m mypy raiker apps tests
python -m pytest
python scripts/validate_phase_status.py
python scripts/validate_repo_truthfulness.py
raiker --help
raiker --prompt "Hello Raiker"
raiker --prompt "/help"
RAIKER_TUI=plain raiker --prompt "/help"
RAIKER_TUI=rich raiker --prompt "/help"
```

GitHub Actions remain paused due to quota; local validation evidence is mandatory.

## Acceptance criteria

1. The default layout matches `docs/UI_UX_DESIGN_SPEC.md` and includes the Primary/Main,
   Activity, Input, and Status Bar panels.
2. The TUI does not invent a different default dashboard or show all advanced panels permanently.
3. All currently implemented command capabilities remain reachable; model commands are accessible through existing paths.
4. Normal prompts route through the existing prompt/runtime path; slash commands route through existing handlers.
5. `raiker --prompt` remains non-interactive and safe; the plain fallback remains available and tested.
6. Accessibility labels are present and tested; narrow/no-colour fallback does not crash.
7. No direct tool/model/plugin/memory/channel/shell/process/network execution is introduced in TUI panels.
8. Runtime disabled flags remain false; docs are updated in one coordinated run without overclaiming full Rich TUI completion.
