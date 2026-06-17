# Phase 1 Alignment Addendum

This addendum clarifies the Phase 1 MVP build plan and overrides any older wording that could imply vague future work or fragmented primary commands.

---

## Phase Scheduling Rule

Phase-scheduled features are fully specified elsewhere in the docs. Phase 1 does not wire those features into active behaviour, but it must preserve their contracts, registries, storage boundaries, gateway paths, and policy boundaries.

A builder must not treat phase scheduling as missing design.

---

## Phase 1 Must Include

Phase 1 must include:

- global `raiker` command entry point;
- `raiker` opens the Rich TUI;
- TUI prompt input creates the prompt path;
- TUI `/launch --provider mock --model mock-deterministic` resolves the mock profile;
- TUI `/channels` reads connector profiles;
- TUI `/models` reads model profiles;
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

Phase 1 must not wire Desktop UI, Web UI, Dashboard, plugin execution, external channel implementations, semantic/vector write path, graph runtime indexing, subagent teams, or remote execution unless a task explicitly changes the phase scope.

The related specifications still exist and must remain compatible.

---

## Validation Commands

Expected Phase 1 validation includes:

```bash
python -m pytest
python -m ruff check .
python -m mypy raiker apps tests
raiker
```

Expected TUI validation actions include:

```text
normal prompt: Hello Raiker
normal prompt: List files in this project
/launch --provider mock --model mock-deterministic
/channels
/models
```

During early packaging, module-based commands may be used temporarily, but the final Phase 1 deliverable must expose the global `raiker` command that opens the TUI.

---

## Builder Rule

When working on Phase 1, the builder must read this addendum after `docs/PHASE_1_MVP_BUILD_PLAN.md`.
