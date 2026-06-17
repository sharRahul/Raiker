# Phase 1 Alignment Addendum

This addendum clarifies the Phase 1 MVP build plan and overrides any older wording that could imply vague future work, fragmented primary commands, or a privileged terminal-only interface.

---

## Phase Scheduling Rule

Phase-scheduled features are fully specified elsewhere in the docs. Phase 1 does not wire those features into active behaviour, but it must preserve their contracts, registries, storage boundaries, gateway paths, and policy boundaries.

A builder must not treat phase scheduling as missing design or interface hierarchy.

---

## Equal Primary Interface Rule

All implemented and enabled clients are equal-status primary interfaces through the same Agent Gateway. This includes CLI, Rich TUI, Desktop, Web, Dashboard, IDE, Voice, Hotkeys, REST, Webhooks, chat clients, Email, Browser Extension, Apple mobile app, Android mobile app, Mobile Companion, and other governed clients.

The Phase 1 terminal client is the first implementation target only. It is not the primary human interface over other clients.

---

## Phase 1 Must Include

Phase 1 must include:

- global `raiker` command entry point;
- `raiker` opens the configured local terminal client, usually Rich TUI during early implementation;
- terminal prompt input creates the prompt path;
- terminal `/launch --provider mock --model mock-deterministic` resolves the mock profile;
- terminal `/channels` reads connector profiles;
- terminal `/models` reads model profiles;
- Apple and Android mobile app connector profiles exist as disabled Phase 3 profiles;
- SQLite bootstrap;
- JSONL event log;
- checkpoint stub;
- policy-gated tool broker;
- safe file/search tools;
- approval-gated local command proposal path;
- mock model provider;
- tests.

---

## Phase 1 Must Not Wire Unless Explicitly Tasked

Phase 1 must not wire Desktop UI, Web UI, Dashboard, Apple mobile app, Android mobile app, plugin execution, external channel implementations, semantic/vector write path, graph runtime indexing, subagent teams, or remote execution unless a task explicitly changes the phase scope.

The related specifications still exist and must remain compatible. These exclusions do not make those interfaces secondary.

---

## Validation Commands

Expected Phase 1 validation includes:

```bash
python -m pytest
python -m ruff check .
python -m mypy raiker apps tests
raiker
```

Expected terminal validation actions include:

```text
normal prompt: Hello Raiker
normal prompt: List files in this project
/launch --provider mock --model mock-deterministic
/channels
/models
```

During early packaging, module-based commands may be used temporarily, but the final Phase 1 deliverable must expose the global `raiker` command that opens the configured local terminal client.

---

## Builder Rule

When working on Phase 1, the builder must read this addendum after `docs/PHASE_1_MVP_BUILD_PLAN.md` and must not describe the terminal client as the only primary human interface.
