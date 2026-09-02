# Connected Provider Catalogue Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Reliably refresh the model catalogue for every connected provider after owner-triggered connection/model changes, including completed Ollama pulls, and propagate fresh choices to Chat and Build without background polling.

**Architecture:** Introduce one authenticated refresh coordinator that enumerates only connected/configured profiles, calls the existing `DashboardService.list_provider_models` sequentially under its normal gate and egress rules, and returns per-provider outcomes. The Models UI owns a single snapshot refresh function that updates both its local state and `models.svelte`; model operations notify that function on terminal catalogue-changing operations. First-run reuses the same API and shared-state update path.

**Tech Stack:** Python 3.12, FastAPI, existing provider factory/router/readiness store, Svelte 5, Vitest, pytest.

## Global Constraints

- Refreshes are explicit owner actions or the result of a Raiker-owned operation reaching `complete`; no timer polls remote provider catalogues.
- Never call a disconnected provider, bypass policy/egress gates, or fabricate a model list after an unavailable response.
- Preserve model ids exactly as published, de-duplicate only exact duplicates while keeping provider order, and retain current selections until an owner changes them.
- Update the single shared Chat/Build model state only from a fresh `GET /api/models` snapshot.
- Do not claim Ollama account usage/quota is known: this work refreshes the local/cloud model catalogue, not unsupported portal usage limits.

---

### Task 1: Add the server-side connected-provider refresh coordinator

**Files:**
- Modify: `raiker/control/dashboard.py`
- Modify: `raiker/api/routes_dashboard.py`
- Modify: `raiker/api/schemas.py`
- Test: `tests/test_api_model_selection.py`
- Test: `tests/test_api_web_read_models.py`

1. Write failing API tests for `POST /api/models/catalogues/refresh`: it returns one outcome per connected/configured profile, invokes no disconnected profile, preserves `available`/`unavailable`/`policy_denied` status, and requires the authenticated owner.
2. Add a `ProviderCatalogueRefreshView` DTO with `profile_id`, `provider`, `status`, `reason_code`, `model_count`, and `refreshed_at`; do not include raw provider payloads.
3. Implement `DashboardService.refresh_connected_provider_catalogues(principal_id, profile_ids=None)`. Resolve eligible profile ids from vault connection markers plus local detected profiles, deduplicate them, list each through the existing `list_provider_models`, and allow a supplied `profile_ids` subset only after validating it belongs to that eligible set.
4. Return success for partial failures: each provider gets its honest result and an unavailable provider cannot erase another provider's result. Keep existing facts/price caching behavior exclusively in `list_provider_models`.
5. Add the route, typed response serialization, and stable 403/404 validation behavior.
6. Run `pytest tests/test_api_model_selection.py tests/test_api_web_read_models.py -q`.
7. Commit: `git add raiker/control/dashboard.py raiker/api/routes_dashboard.py raiker/api/schemas.py tests/test_api_model_selection.py tests/test_api_web_read_models.py && git commit -m "Add connected provider catalogue refresh"`.

### Task 2: Bind Ollama pull completion to the catalogue refresh notification

**Files:**
- Modify: `raiker/api/routes_models.py`
- Modify: `raiker/control/model_operations.py` (or the existing operation completion owner discovered during implementation)
- Test: `tests/test_api_model_operations.py`
- Test: `tests/test_model_local_operations.py`

1. Write a failing operation test that a completed Ollama pull records the existing readiness invalidation and emits a durable `catalogue_changed` completion detail for `ollama-local-openai-compatible`; a failed/cancelled pull must not emit it.
2. Add the narrowly scoped completion metadata/state field rather than guessing by operation display text in the frontend.
3. Preserve the current operation state machine and cancellation behavior. The server must announce catalogue change only after `/api/pull` has completed successfully.
4. Add a regression test that the terminal operation response still has no model list and no secret data.
5. Run `pytest tests/test_api_model_operations.py tests/test_model_local_operations.py -q`.
6. Commit: `git add raiker/api/routes_models.py raiker/control/model_operations.py tests/test_api_model_operations.py tests/test_model_local_operations.py && git commit -m "Mark completed Ollama pulls as catalogue changes"`.

### Task 3: Refresh Models and shared Chat/Build choices from one UI path

**Files:**
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/lib/apiTypes.ts`
- Modify: `apps/web/src/lib/views/ModelsView.svelte`
- Modify: `apps/web/src/lib/views/models/ProvidersPanel.svelte`
- Modify: `apps/web/src/lib/views/models/DownloadsPanel.svelte`
- Test: `apps/web/src/lib/views/ModelsView.test.ts`
- Test: `apps/web/src/lib/views/models/ProvidersPanel.test.ts`
- Test: `apps/web/src/lib/views/models/DownloadsPanel.test.ts`

1. Write a `ModelsView` test that the visible “Refresh connected providers” action calls the new route, then `GET /api/models`, and the resulting snapshot reaches `setModels`.
2. Write an Ollama UI regression test: pull begins, Activity observes the matching operation become `complete` with `catalogue_changed`, and the Models page refreshes the Ollama catalogue so the pulled id is in the picker without a browser reload.
3. Add typed client calls for the refresh response and operation completion metadata.
4. Refactor `ModelsView.load` into one serialised refresh function that updates Models state, capacities where appropriate, `setModels`, fallback choices, and callbacks. Ensure a second refresh waits for an in-flight refresh rather than racing stale snapshots over newer results.
5. Pass a narrowly typed `onCatalogueChanged(profileIds)` callback to `ProvidersPanel` and `DownloadsPanel`. `ProvidersPanel` reports the started pull; `DownloadsPanel` reports only a matching terminal successful operation. The Models parent invokes the server refresh for those ids and then reloads its snapshot.
6. Add an explicit owner-facing Refresh control with per-provider outcome wording. It must remain usable when one provider is unavailable and must not show a successful refresh for a policy-denied provider.
7. Run `npm test -- --run src/lib/views/ModelsView.test.ts src/lib/views/models/ProvidersPanel.test.ts src/lib/views/models/DownloadsPanel.test.ts` from `apps/web`.
8. Commit: `git add apps/web/src/lib/api.ts apps/web/src/lib/apiTypes.ts apps/web/src/lib/views/ModelsView.svelte apps/web/src/lib/views/models/ProvidersPanel.svelte apps/web/src/lib/views/models/DownloadsPanel.svelte apps/web/src/lib/views/ModelsView.test.ts apps/web/src/lib/views/models/ProvidersPanel.test.ts apps/web/src/lib/views/models/DownloadsPanel.test.ts && git commit -m "Refresh model catalogues after provider changes"`.

### Task 4: Reuse refresh behavior in first-run setup and verify all provider classes

**Files:**
- Modify: `apps/web/src/lib/components/ProviderMatrix.svelte`
- Modify: `apps/web/src/lib/views/ModelSetupView.svelte`
- Test: `apps/web/src/lib/components/ProviderMatrix.test.ts`
- Test: `apps/web/src/lib/views/ModelSetupView.test.ts`
- Test: `tests/test_phase_4_provider_breadth.py`

1. Write first-run tests for local detect, API-key connection, custom endpoint connection, and Codex subscription connection: each causes a fresh models snapshot and makes its provider-provided model selectable immediately.
2. Replace any direct stale local-array assumptions with the parent refresh callback; the matrix may keep the current provider's immediate picker response, but the authoritative Chat/Build state comes from `GET /api/models`.
3. Add provider-breadth tests covering a connected local runtime, a hosted API-key profile, and the Codex subscription provider; prove gates/egress still prevent a prohibited refresh.
4. Run `pytest tests/test_phase_4_provider_breadth.py -q` and `npm test -- --run src/lib/components/ProviderMatrix.test.ts src/lib/views/ModelSetupView.test.ts` from `apps/web`.
5. Commit: `git add apps/web/src/lib/components/ProviderMatrix.svelte apps/web/src/lib/views/ModelSetupView.svelte apps/web/src/lib/components/ProviderMatrix.test.ts apps/web/src/lib/views/ModelSetupView.test.ts tests/test_phase_4_provider_breadth.py && git commit -m "Refresh connected catalogues during model setup"`.

### Task 5: Run regression verification

**Files:**
- Test: `tests/test_api_model_operations.py`
- Test: `tests/test_api_model_selection.py`
- Test: `tests/test_api_web_read_models.py`
- Test: `apps/web/src/lib/views/ModelsView.test.ts`

1. Run `pytest tests/test_api_model_operations.py tests/test_model_local_operations.py tests/test_api_model_selection.py tests/test_api_web_read_models.py tests/test_phase_4_provider_breadth.py -q`.
2. Run `npm test -- --run src/lib/views/ModelsView.test.ts src/lib/views/models/ProvidersPanel.test.ts src/lib/views/models/DownloadsPanel.test.ts src/lib/components/ProviderMatrix.test.ts src/lib/views/ModelSetupView.test.ts` from `apps/web`.
3. Manually verify in a local development host: pull a small Ollama model, wait for Activity to mark it complete, refresh providers if prompted, and confirm the identical model id appears in both Chat and Build selectors.
4. Commit any test-only fixes as `git commit -m "Verify provider catalogue refresh behavior"`.

## Plan Review

- [ ] All connected provider categories use the same refresh coordinator.
- [ ] A failed provider refresh leaves other catalogues and selections intact.
- [ ] Ollama pull completion—not pull request start—triggers its refresh.
- [ ] Chat and Build observe one fresh shared models snapshot.
