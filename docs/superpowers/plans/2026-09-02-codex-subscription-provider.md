# ChatGPT Subscription (Codex) Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Let an owner authenticate a ChatGPT subscription through a locally installed Codex App Server and select the resulting subscription-backed models in both Chat and Build, without treating the subscription as an OpenAI API key or exposing OAuth credentials to Raiker.

**Architecture:** Add a distinct `chatgpt-codex-subscription` profile and an App Server JSONL client/`AsyncModelProvider` adapter. The Codex runtime owns all browser/device authentication, token persistence, renewal, and subscription entitlement. Raiker stores only a connection marker and safe status/model metadata. A small authenticated API exposes status and login start/cancel operations; the existing model registry, selection, readiness and shared `models.svelte` store continue to drive both work surfaces.

**Tech Stack:** Python 3.12, FastAPI, `asyncio` subprocess JSONL transport, existing Raiker model contracts/router, Svelte 5, Vitest, pytest.

## Global Constraints

- Keep `openai-hosted` API-key-only. Do not accept, derive, or exchange an API key in the subscription flow.
- Require an installed compatible Codex executable; never download or install it automatically.
- The Codex child process is the sole OAuth/token owner. Do not write tokens, authorization URLs containing secrets, device codes, or raw App Server events to SQLite, browser state, logs, API responses, or telemetry.
- The profile is hosted and remains subject to Raiker's existing hosted-provider gate and explicit egress policy. It is never a fallback unless the owner deliberately configures it.
- Support chat/streaming only in this slice. `embed` must return the existing unsupported-provider error, and tool/approval events must fail closed unless their approval semantics can be represented by Raiker's existing governed approval path.

---

### Task 1: Define the subscription profile and safe connection/status DTOs

**Files:**
- Modify: `raiker/config/model-profiles.json`
- Modify: `raiker/control/dashboard.py`
- Modify: `raiker/api/schemas.py`
- Modify: `apps/web/src/lib/apiTypes.ts`
- Test: `tests/test_authenticated_model_profiles.py`
- Test: `tests/test_api_web_read_models.py`

1. Write a failing registry test proving `chatgpt-codex-subscription` is a separate hosted profile, has no API-key requirement or endpoint override, declares no embeddings, and is hidden from selection until its runtime supplies a concrete model.
2. Write API view tests asserting the profile exposes only `connection_configured`, login/status fields and concrete registered models; assert neither a token nor a secret-shaped field is serialized.
3. Add the profile with provider `chatgpt-codex`, backend `codex_app_server`, `requires_network`, `requires_egress_policy`, hosted gate semantics, streaming support, no embeddings, and no static model id.
4. Extend `ModelProfileView` and the generated TypeScript type with a narrow `connection_kind: "api_key" | "codex_subscription" | null` plus `connection_status: "not_connected" | "codex_missing" | "signed_out" | "login_pending" | "connected" | "unavailable"`; populate only safe values in `DashboardService.get_models`.
5. Run `pytest tests/test_authenticated_model_profiles.py tests/test_api_web_read_models.py -q` and confirm the new behavior passes.
6. Commit: `git add raiker/config/model-profiles.json raiker/control/dashboard.py raiker/api/schemas.py apps/web/src/lib/apiTypes.ts tests/test_authenticated_model_profiles.py tests/test_api_web_read_models.py && git commit -m "Add Codex subscription model profile"`.

### Task 2: Implement the local Codex App Server transport and provider adapter

**Files:**
- Create: `raiker/models/providers/codex_app_server.py`
- Create: `raiker/models/codex_app_server.py`
- Modify: `raiker/models/factory.py`
- Modify: `raiker/models/router.py`
- Test: `tests/test_codex_app_server_provider.py`
- Test: `tests/test_async_model_runtime.py`

1. Write failing unit tests using a fake JSONL subprocess for: executable absence, initialize/account-read status parsing, login-start callback data redaction, runtime-supplied model list, a completed chat response, streamed text events, malformed JSONL, child exit, and `embed` refusal.
2. Implement a bounded `CodexAppServerClient` that starts only the configured local executable, speaks request-id-correlated JSONL over stdio, applies startup/request timeouts, terminates children in `aclose`, and converts all protocol/transport exceptions to existing `ModelProviderError` subclasses with safe reason codes.
3. Implement the exact adapter boundary: `account/read`, `account/login/start`, account-login event handling, thread creation/turn submission/turn stream consumption, and model enumeration. Keep protocol-specific payload conversion in this module rather than leaking it into `ModelRouter`.
4. Implement `AsyncCodexAppServerProvider` with `health`, `list_models`, `chat`, `stream_chat`, `embed`, and `aclose`. Map only role/content, max token, and supported reasoning inputs. Reject tool calls, schemas, and embeddings before calling Codex where the runtime cannot guarantee Raiker governance.
5. Update `ModelProviderFactory.create` to construct this adapter before endpoint/API-key validation. It must still enforce `allow_hosted_provider`, the configured hosted egress policy, and the profile's explicit policy gate, but it must not run an HTTP endpoint validation or API-key check for this backend.
6. Add a router contract test that `achat`, `astream`, `alist_models_for_profile`, and readiness use this provider exactly as they use other `AsyncModelProvider` implementations.
7. Run `pytest tests/test_codex_app_server_provider.py tests/test_async_model_runtime.py -q`.
8. Commit: `git add raiker/models/providers/codex_app_server.py raiker/models/codex_app_server.py raiker/models/factory.py raiker/models/router.py tests/test_codex_app_server_provider.py tests/test_async_model_runtime.py && git commit -m "Add Codex App Server model provider"`.

### Task 3: Add authenticated subscription login/status endpoints and persistence boundaries

**Files:**
- Create: `raiker/control/codex_subscription.py`
- Modify: `raiker/api/routes_dashboard.py`
- Modify: `raiker/api/schemas.py`
- Modify: `raiker/api/app.py`
- Test: `tests/test_api_codex_subscription.py`

1. Write failing endpoint tests for unauthenticated denial; Codex missing; signed-out status; initiating a browser/device-code login; connected status; cancel/disconnect; malformed App Server response; and assertions that JSON never contains access tokens, refresh tokens, verifier values, device codes, or authorization URLs with sensitive query data.
2. Implement `CodexSubscriptionService` as the only API-facing owner of the App Server client. Persist a per-principal boolean/opaque safe connection marker through the existing connector vault only after `account/read` confirms a signed-in account; store no OAuth material.
3. Add `GET /api/models/chatgpt-codex/status`, `POST /api/models/chatgpt-codex/login`, and `DELETE /api/models/chatgpt-codex/connection`. The login route returns only an explicit browser-launch instruction or non-secret verification URL policy-approved for display; the browser/device action itself is performed by Codex.
4. On successful connect, disconnect, or status transition, invalidate readiness for the subscription profile and refresh its configured model list through the same selection/catalogue path used by all providers.
5. Make errors operational: missing executable, unsupported runtime version, user-cancelled login, and expired/sign-out map to stable reason codes and remediation text.
6. Run `pytest tests/test_api_codex_subscription.py tests/test_api_model_selection.py -q`.
7. Commit: `git add raiker/control/codex_subscription.py raiker/api/routes_dashboard.py raiker/api/schemas.py raiker/api/app.py tests/test_api_codex_subscription.py && git commit -m "Expose ChatGPT subscription sign-in safely"`.

### Task 4: Present the connection flow in first run and Models

**Files:**
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/lib/apiTypes.ts`
- Modify: `apps/web/src/lib/components/ProviderMatrix.svelte`
- Modify: `apps/web/src/lib/views/ModelsView.svelte`
- Test: `apps/web/src/lib/components/ProviderMatrix.test.ts`
- Test: `apps/web/src/lib/views/ModelsView.test.ts`

1. Write UI tests showing a distinct “ChatGPT subscription (Codex)” row/card, an explicit “Sign in with ChatGPT” control, Codex-missing guidance, a connected account without an account identifier, a disconnect action, and no API-key input for this provider.
2. Add typed client methods for status/login/disconnect. Do not reuse `saveModelConnection` for this flow.
3. In `ProviderMatrix`, classify `connection_kind === "codex_subscription"` before API-key/endpoint rows. On connect, show the runtime-provided browser/device instruction, poll only while login is pending, then list models and call `onchanged`.
4. In `ModelsView`, provide the same subscription card/modal and model picker behavior. Route successful refreshes through `load()` and `setModels(models)` so mounted Chat and Build composers receive the updated shared choices without reload.
5. Preserve the existing API-key connection experience for `openai-hosted`; use wording that makes the distinction explicit: subscription access is through Codex, API access is through an API key.
6. Run `npm test -- --run src/lib/components/ProviderMatrix.test.ts src/lib/views/ModelsView.test.ts` from `apps/web`.
7. Commit: `git add apps/web/src/lib/api.ts apps/web/src/lib/apiTypes.ts apps/web/src/lib/components/ProviderMatrix.svelte apps/web/src/lib/views/ModelsView.svelte apps/web/src/lib/components/ProviderMatrix.test.ts apps/web/src/lib/views/ModelsView.test.ts && git commit -m "Add ChatGPT subscription connection UI"`.

### Task 5: Verify Chat and Build model selection end-to-end

**Files:**
- Modify: `tests/test_model_readiness.py`
- Modify: `tests/test_turn_model_binding.py`
- Modify: `apps/web/src/lib/models.svelte.ts`
- Test: `apps/web/src/lib/models.svelte.test.ts`
- Test: `apps/web/src/lib/views/ModelSetupView.test.ts`

1. Write regression tests that a connected subscription runtime model appears in the shared model store and is selectable from both Chat and Build, while a signed-out profile is unavailable to both.
2. Make any shared-store normalization preserve the provider/profile/model tuple rather than collapsing models by display name.
3. Add backend selection/readiness tests proving the subscription profile only runs a runtime-published model and fails closed after disconnect or expired sign-in.
4. Run the focused frontend tests and `pytest tests/test_model_readiness.py tests/test_turn_model_binding.py -q`.
5. Run the complete relevant suite: `pytest tests/test_codex_app_server_provider.py tests/test_api_codex_subscription.py tests/test_authenticated_model_profiles.py tests/test_model_readiness.py tests/test_turn_model_binding.py -q` and `npm test -- --run src/lib/components/ProviderMatrix.test.ts src/lib/views/ModelsView.test.ts src/lib/views/ModelSetupView.test.ts` from `apps/web`.
6. Commit: `git add tests/test_model_readiness.py tests/test_turn_model_binding.py apps/web/src/lib/models.svelte.ts apps/web/src/lib/models.svelte.test.ts apps/web/src/lib/views/ModelSetupView.test.ts && git commit -m "Make Codex subscription models available to Chat and Build"`.

## Plan Review

- [ ] `openai-hosted` remains API-key-only and Codex OAuth secrets have no Raiker persistence path.
- [ ] Every App Server process outcome has bounded cleanup and a safe user-facing reason code.
- [ ] Subscription models are runtime-published and appear in both Chat and Build only after explicit owner selection/readiness.
- [ ] No unsupported tools, embeddings, or approval semantics are silently delegated.
