# Memory, Restart and Plan Closure — 2026-09-07

## Goal

Restore the owner's autonomous durable memory writes, preserve the existing
workspace on restart, and verify at least three requested plans end to end.

## Execution order

Priority precedes effort; within each priority, choose the smaller change first.
Existing closure records are evidence to verify, not work to repeat.

| Order | Priority | Effort | Work | State |
|---|---|---|---|---|
| 1 | P0 | Low | Trace memory gate and decision mode against the active owner; persist the requested setting | Done |
| 2 | P0 | Low–Medium | Refresh the same app data directory and prove owner/settings/history survive | Done |
| 3 | P1 | Low–Medium | Reverify Models, global web reads and environment/time/weather acceptance contracts; fix regressions | Done |
| 4 | P1 | Medium | Finish shared Work draft continuity and large-paste attachment handling | Done |
| 5 | P1 | Medium | Live UI tests with Anthropic, OpenAI, OpenRouter and available Ollama cloud model; screenshots | Done; Ollama Chat defect recorded separately |
| 6 | P1 | Low | Reconcile current plan status, fixed-item ledger and guide; record unresolved audit work | Done |
| 7 | P1 | Medium | Run Python/web checks, review diff, commit and push origin/main; monitor workflows | Local checks done; push/CI pending |

## Implementation and verification checklist

- [x] Read persisted memory admission and confirm the runtime describes the same state.
- [x] Enable the owner's memory-write capability and Allow behavior through supported controls.
- [x] Prove a real governed memory write and recall; verify persistence after restart.
- [x] Restart using the existing `C:/Users/1niki/AppData/Local/Raiker` workspace.
- [x] Verify [Models](MODELS_PAGE_UI_BACKEND_REVIEW_2026-09-06.md) source, tests and live UI.
- [x] Verify [web reads](GLOBAL_WEB_READ_CAPABILITIES_2026-09-07.md) source, tests and live UI.
- [x] Verify [environment](ENVIRONMENT_CONTEXT_TIME_WEATHER_2026-09-07.md) source, tests and live UI.
- [x] Complete [composer](UNIFIED_COMPOSER_REDESIGN_2026-09-06.md) draft/paste remainder with regression tests.
- [x] Record provider outcomes separately; a rejected credential is not a passing provider test.
- [x] Review screenshots, update documentation, and record open work in [TO_BE_FIXED](TO_BE_FIXED.md).
- [x] Run Ruff, Mypy, pytest, web check/lint/tests/build and relevant Playwright scenarios.
- [ ] Commit, push, and verify workflows for the pushed SHA.

## Constraints

Use the existing owner and data directory; do not seed a fresh run. Credentials
enter through the Models UI and never enter source, screenshots or documentation.
Memory admission continues through the existing runtime authority boundary.
Historical plan analysis stays labeled as historical where current implementation
supersedes it. Root coordinates shared ledger edits and the final commit.

## Delivered closure

Four requested plans are complete end to end in this continuation:

1. [Models](MODELS_PAGE_UI_BACKEND_REVIEW_2026-09-06.md) — the four requested
   provider connections survived restart and passed their UI connection tests;
   Ollama cloud execution is now labelled honestly.
2. [Global web reads](GLOBAL_WEB_READ_CAPABILITIES_2026-09-07.md) — the shared
   contract and built-in keyless search fallback were reverified with no open
   implementation item.
3. [Environment, time and weather](ENVIRONMENT_CONTEXT_TIME_WEATHER_2026-09-07.md)
   — Windows now carries IANA timezone data, preserving `Europe/London` rather
   than falling back to UTC.
4. [Unified composer](UNIFIED_COMPOSER_REDESIGN_2026-09-06.md) — COMPOSER-11
   and COMPOSER-14 are delivered with unit and live coverage.

The P0 memory path is fixed in [FIXED-475](FIXED_ITEMS.md#fixed-475--memory-allow-stopped-at-a-second-approval-gate)
and its live-found visibility defect in
[FIXED-480](FIXED_ITEMS.md#fixed-480--directly-allowed-memories-were-recallable-and-invisible).
The same-workspace restart retained the owner, settings, sessions, model
profiles and memory authority. Live evidence is in:

- `screenshots/working/memory-write-allow-after-restart.png`
- `screenshots/working/models-four-providers-after-restart.png`
- `screenshots/working/composer-large-paste-attachment.png`
- `screenshots/working/memory-write-recalled-after-restart.png`

The provider round passed Anthropic, OpenAI, OpenRouter and Ollama connection
tests. Direct `ollama run gemma4:31b-cloud` also completed, while Raiker Chat
could not use that cloud-tagged profile; [BUG-285](TO_BE_FIXED.md#bug-285--an-ollama-cloud-model-tests-and-runs-in-ollama-but-chat-cannot-use-it)
records that isolated adapter/stream issue.

## Local verification

- Full Python suite: passed from an external Windows temporary directory.
- Ruff: passed across `raiker` and `tests`.
- Mypy: no issues in 417 source files.
- Web unit suite: 154 files passed; 1,535 tests passed and one skipped.
- ESLint, design-token check and Svelte check: passed with zero diagnostics.
- Production web build: passed.
- Live Playwright closure spec: all three scenarios passed together; the final
  direct-memory scenario also passed once more after loading the exact broker
  implementation intended for the commit.
- Documentation consistency and `git diff --check`: passed.
