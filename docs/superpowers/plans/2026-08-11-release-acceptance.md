# Release Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the seven bug fixes across every configured provider, browser viewport, packaged Windows host, documentation surface, and GitHub Actions workflow before declaring completion.

**Architecture:** Focused tests establish each invariant, full local suites catch integration regressions, a clean live server is driven exclusively through the UI for provider setup, Playwright captures reviewable screenshots, and the pushed `main` commit is monitored to a green workflow conclusion.

**Tech Stack:** pytest, Ruff, mypy, Svelte check, ESLint, Vitest, Playwright, PyInstaller/WiX, Git, GitHub CLI/Actions.

## Global Constraints

- Stop existing Raiker/Vite/uvicorn processes before live testing and verify the intended ports are free.
- Provider secrets are entered only in the UI, never embedded in tests, environment files, screenshots, console output, fixtures, commits, or CI.
- Use provider models available to the supplied accounts at test time; record provider/model names and pass/fail results, never credentials.
- If a defect cannot be safely fixed, add a new numbered entry to `docs/plans/TO_BE_FIXED.md` in its established format and include it in the final summary.

---

### Task 1: Update documentation truthfully

**Files:**
- Modify: `README.md`
- Modify: `docs/plans/TO_BE_FIXED.md`
- Modify: `docs/REFERENCE_PLATFORM_COMPATIBILITY.md`
- Modify: `docs/DESKTOP_DISTRIBUTION_DESIGN.md`
- Modify: relevant operator/security documentation discovered by `rg -n "SQLCipher|setup|tray|rate limit|transcript|task approval" README.md docs`

- [ ] Update README installation and first-run flow, native tray controls, backup limitations, SQLCipher posture, explicit task Run now behavior, citation-export behavior, and loopback/public rate-limit distinction.
- [ ] Update the compatibility matrix only for behavior verified in this run. Cite current official primary documentation for Claude Cowork/Code, ChatGPT/Codex, OpenClaw, and Hermes Agent; label comparisons as parity, stronger, weaker, or not applicable.
- [ ] Mark BUG-46, BUG-48, BUG-51, BUG-60, BUG-64, BUG-65, and BUG-88 fixed only after their tests pass. Preserve headings, numbering, evidence style, and links in `TO_BE_FIXED.md`.
- [ ] Run `python -m pytest tests/test_docs_consistency.py -q` and any documentation link/format checker found in project scripts; verify success.

### Task 2: Run focused and full local verification

**Files:**
- Modify only files needed to fix failures attributable to this change.

- [ ] Run all focused commands listed in the subsystem plans from a clean process state.
- [ ] Run `python -m pytest -q`; verify zero failures.
- [ ] Run `python -m ruff check .`; verify zero errors.
- [ ] Run `python -m mypy raiker apps`; verify zero errors.
- [ ] From `apps/web`, run `npm test`, `npm run check`, `npm run lint`, and `npm run build`; verify all pass.
- [ ] Build the Windows desktop bundle and installer, install or unpack into a clean temporary directory, launch it without repository Python on PATH, poll health, verify the tray integration probe, and shut it down cleanly.

### Task 3: Test every provider through the UI

**Files:**
- Modify: `apps/web/e2e/critical-bugs-live.spec.ts`
- Modify: `apps/web/e2e/setup-tray-live.spec.ts`

- [ ] Start one clean packaged or production-equivalent loopback server with browser console/network recording enabled and redaction verified.
- [ ] Through the setup/settings UI, add Anthropic, OpenRouter, OpenAI, and Ollama credentials/configuration. Select the requested Ollama model `gemma4:31b-cloud`.
- [ ] For each provider, run a simple chat, a safe read tool flow, a withheld/denied tool flow, and a citation-producing flow. Assert visible runtime refusal attribution, no unexplained assistant narration, no surprise task turn, and no unresolved export markers.
- [ ] Confirm provider API calls succeed or capture a provider-returned account/model availability error. Do not weaken the implementation or substitute mock success for an external provider rejection.
- [ ] Remove every external credential through the UI and verify the provider cards return to unconfigured state.

### Task 4: Capture and inspect visual evidence

**Files:**
- Create: `artifacts/playwright/bug-46-48-51-60-64-65-88/` screenshots through Playwright output configuration.

- [ ] Capture desktop and mobile screenshots for setup stages, SQLCipher posture, runtime refusal, proposed task with Run now, exported transcript preview/download confirmation, and navigation under repeated polling.
- [ ] Inspect each screenshot at original resolution. Verify no clipping, overlap, horizontal scroll, focus loss, stale labels, debug content, credential values, or unresolved citation markers.
- [ ] Re-run the affected screenshot after every visual fix and retain only the final redacted evidence set.
- [ ] Run `npm run test:e2e:live` from `apps/web`; verify all live projects pass.

### Task 5: Commit, push, and monitor GitHub Actions

**Files:**
- Modify only files needed to resolve CI-specific failures.

- [ ] Run `git status --short`, `git diff --check`, and inspect the full staged diff. Confirm no credential pattern or local runtime artifact is staged.
- [ ] Force-add the intentionally ignored approved spec and implementation plans under `docs/superpowers/`, stage all scoped implementation/docs changes, and commit with focused messages from the execution index.
- [ ] Pull/rebase only if required by a changed remote, rerun affected tests after conflict resolution, then push to `origin/main`.
- [ ] Use GitHub Actions/CLI to watch every workflow for the pushed commit. For any failure, open the failing job logs, reproduce locally when possible, add a regression test, fix, rerun local verification, commit, push, and watch again.
- [ ] Stop only when all required workflows for the final `main` SHA are green. Record the final SHA, workflow names/URLs, local test commands, provider outcomes, and screenshot paths in the completion summary.
