# Documentation Drift Audit

Date: 2026-06-21
Repository state: after the documentation alignment overhaul (Phases 1–9 reconciled; README rewritten).

This audit records where documentation had drifted from the code and what was done to realign it.
The canonical status ledger is `docs/IMPLEMENTATION_STATUS.md`; the missing-work backlog is
`docs/GAP_AND_TODO_ANALYSIS.md`.

## Drift found and corrected

| Drift | Reality in code | Resolution |
|---|---|---|
| README and `/help` said the launchable UI was "a simple terminal/CLI shell" and that the Rich TUI was "specified/deferred". | `raiker/cli/main.py` → `raiker/terminal/app.py` launches a plain local terminal client only; the prior Rich/Textual implementation has been removed and deferred to Phase 8. | README, `/help`, `docs/IMPLEMENTATION_STATUS.md`, and the truthfulness validator now describe a "local terminal client: plain local terminal client only; Rich/native TUI Phase 8 deferred". |
| README and `docs/ARCHITECTURE.md` omitted Phases 5–9, which are `implemented_verified` (record/metadata level) in the ledger. | Phases 5–9 exist in `raiker/` with SQLite records and CLI surfaces; runtime stays disabled. | Added Phase 6/7/9 rows to `docs/ARCHITECTURE.md`; the README "Project Status" section and the ledger now cover Phases 5–9. |
| Phase 8 appeared "missing". | There is Phase 8 is the planned UI/client phase; numbering intentionally skips 7→9. | Documented explicitly in `docs/ARCHITECTURE.md`, `docs/IMPLEMENTATION_STATUS.md`, and `docs/GAP_AND_TODO_ANALYSIS.md`. |
| README was a ~1000-line status ledger duplicating `docs/IMPLEMENTATION_STATUS.md`. | — | README rewritten into a conventional format; the exhaustive ledger, the CLI command surface, and the async-runtime notes now live in `docs/IMPLEMENTATION_STATUS.md` and `docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md`. |
| Spent planning scaffolding (build plans, per-slice specs, completion/readiness audits, the Phase 2–5 roadmap) lingered in `docs/` and `docs/completed/`. | Those phases/slices are complete. | Deleted the scaffolding; the truthfulness/phase validators and tests were repointed to the living docs so nothing was kept solely to satisfy a test. |
| Base design docs were buried under `docs/completed/`. | They are living foundations. | Moved the numbered `01`–`12` design docs to `docs/foundation/` and refreshed them. |

## Verification

- `python scripts/validate_repo_truthfulness.py` → passed.
- `python scripts/validate_phase_status.py` → passed.
- `python -m pytest` → passed (1 skipped, opt-in real-provider TUI integration).

## Truthfulness boundaries (unchanged guarantees)

- Phase 3 is `implemented_verified` only for safe foundation/readiness slices A-P.
- Phase 3 Slice A is metadata-only/proposal-only; Phase 3 Slice B is preview-only.
- Approval previews do not execute approvals or proposals; no fixes/patches are applied; no files are
  modified; preview commands run no tests; GitHub PR automation is not implemented.
- Desktop/Web/Dashboard/Mobile/IDE/REST apps are specified/deferred, not implemented.
- Phase 4 memory MVP is implemented; remaining Phase 4 capabilities remain blocked.
- All disabled runtime flags remain false; runtime execution remains disabled.
