# RU-11 Memory summary implementation plan

> **For agentic workers:** Use superpowers:executing-plans for the UI integration and superpowers:subagent-driven-development for isolated backend validation.

**Goal:** Implement the approved [memory summary design](RU_11_MEMORY_SUMMARY_DESIGN.md).
**Architecture:** Render canonical approved memories in the landing view. Reuse the account Incognito boundary for Use memory, preserve conversation controls, and place the existing engine under Memory Controls with a guarded local setup operation.
**Tech stack:** Svelte 5, TypeScript, Python, FastAPI, pytest and Playwright.

## Constraints

- Preserve owner isolation, approvals, audit and encrypted storage.
- Only verified local embedding profiles qualify for the local meaning-search choice.
- Preserve old navigation links and recall-mode choices.
- Verify screenshots at 1440 and 390 px in light and dark appearance.

## Tasks

- [ ] Summary: extend `web/src/lib/views/MemoryView.test.ts` with a landing-view test that expects `What Raiker knows about you`, approved text, topic labels, scope, Edit and Forget; exclude inactive and unapproved records. Run `npm test -- --run src/lib/views/MemoryView.test.ts` before implementing a focused summary component and grouping helper.
- [ ] Switch: test Use memory toggling the existing Incognito API while preserving `recall_mode`. Verify the server's ambient and explicit retrieval opt-out tests and owner isolation; fix any uncovered path before exposing the switch.
- [ ] Meaning search: test a local-only setup operation against a hosted profile (refused), wrong owner (refused), and available local profile (governed index build plus selection). Reuse current indexing authorization and API types; keep word-only status until retrieval is query-embeddable.
- [ ] Controls: render the engine in Memory Controls, preserve the Settings destination as a compatibility link, and test the unavailable-local-model and authorization-failure states. Run the affected component tests, web check, lint and build.
- [ ] Live: add `web/e2e/ru-11-memory-summary-live.spec.ts` against an isolated running host. Import reviewed facts, edit, forget, toggle use, check refresh persistence, controls navigation and no overflow. Capture and inspect both appearances and widths. Qualify real semantic recall separately if a local embedding model is available.
- [ ] Documentation: update the Memory guide, status table, FIXED_ITEMS and live test record with actual results. Record any unmet acceptance or discovered issue in TO_BE_FIXED. Delete this implementation plan once every task is complete; keep unresolved work in the parent plan.
- [ ] Delivery: run relevant Python tests, Ruff and Mypy plus web checks; inspect the final diff, commit, push origin/main and monitor every triggered workflow. Repair failures and report any environmental qualification still open.

## Progress

2026-11-27: summary, global switch integration, local setup, controls move and
import-type regression implemented. Real-host UI/store journey passed with
screenshots inspected; 54 focused Python tests, the new route contract, Ruff,
Mypy and web checks pass. Real Ollama setup, paraphrase vector recall and global
off/on also pass. Subsequent chat-model turns, conversation Incognito and
delivery remain pending.
The parent plan and TO_BE_FIXED own the outstanding qualification; this plan
must not be marked complete from the UI/store test alone.
