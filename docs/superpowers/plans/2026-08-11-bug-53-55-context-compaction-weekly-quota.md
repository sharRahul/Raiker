# Chat Transcript, Context Compaction, and Weekly Quota Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close BUG-53, BUG-54, and BUG-55 while shipping automatic 90% context compaction and a connected-provider rolling seven-day usage and quota surface.

**Architecture:** Preserve the existing orchestrator and provider contracts. Add explicit response-boundary rendering, a repository-owned deterministic provider fixture, a timestamped usage/owner-budget read model with optional native provider adapters, and a durable compaction layer inserted before the normal agent loop. New network reads stay owner initiated, connection scoped, source labelled, bounded, and independent of the existing inference path.

**Tech Stack:** Python 3.11, FastAPI, SQLite/SQLCipher, httpx, Svelte 5, TypeScript, Vitest, Testing Library, Playwright, GitHub Actions.

## Global Constraints

- Work directly on `main` and preserve unrelated user changes.
- Enter provider credentials through the Models UI only; never place them in files, shell arguments, traces, screenshots, or reports.
- Display weekly rows only for connected providers.
- Prefer genuine documented provider telemetry when the configured credential has access; always retain the separately labelled Raiker-observed rolling seven-day baseline.
- Never display unknown cost or quota as zero or unlimited.
- Context compaction triggers at an estimated 90% of exact known capacity, uses no tools, retains the original transcript, and cannot alter protected governance state.
- Follow red-green-refactor for every behavior change and run fresh verification before each commit.
- Keep README, user-guide, plan-log, API, architecture, security, and live-test documentation in their existing format.
- Test Anthropic, OpenRouter, OpenAI, and Ollama `gemma4:31b-cloud` through the UI and visually inspect credential-free screenshots.

---

### Task 1: Make transcript text response-boundary aware and remove the disabled Chat branch

**Files:**
- Modify: `apps/web/src/lib/turnPhases.test.ts`
- Modify: `apps/web/src/lib/turnPhases.ts`
- Modify: `apps/web/src/lib/views/ChatView.svelte`
- Test: `apps/web/src/lib/turnPhases.test.ts`
- Test: `apps/web/src/lib/views/ChatView.test.ts`

**Interfaces:**
- Consumes: existing `StreamEvent` objects and `model_request_started` lifecycle events.
- Produces: `collectText(events: StreamEvent[]): string`, with `\n\n` only between non-empty model responses.

- [ ] **Step 1: Write failing response-seam tests**

Add cases that name the two realistic regressions: losing a model-response seam and inserting whitespace inside one streamed response.

```ts
it("separates text emitted by successive model responses", () => {
  expect(collectText([
    lifecycle("model_request_started"),
    delta("Reading the workspace."),
    lifecycle("model_request_completed"),
    lifecycle("model_request_started"),
    delta("I found two files."),
  ])).toBe("Reading the workspace.\n\nI found two files.");
});

it("does not separate deltas within one model response", () => {
  expect(collectText([
    lifecycle("model_request_started"),
    delta("Hel"),
    lifecycle("model_request_completed"),
    delta("lo"),
  ])).toBe("Hello");
});

it("does not create an empty paragraph for a tool-only response", () => {
  expect(collectText([
    lifecycle("model_request_started"),
    lifecycle("model_request_completed"),
    lifecycle("model_request_started"),
    delta("Finished."),
  ])).toBe("Finished.");
});
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `npm --prefix apps/web test -- src/lib/turnPhases.test.ts`

Expected: the successive-response test fails with the current run-on string; the existing within-response test still passes.

- [ ] **Step 3: Implement the minimal event scanner**

Replace the filter/map/join implementation with one pass that tracks `hasText`, `responseBoundaryPending`, and the accumulated string. Set the pending flag only when a `model_request_started` follows emitted text. On the next non-empty delta, append `\n\n` only when the accumulated text does not already end with a blank line and the new text does not start with one.

- [ ] **Step 4: Delete BUG-55's disabled transcript implementation**

Remove the outer `{#if false}` block and everything inside it, including its nested legacy approval card and commented metadata. Preserve the later live streaming label, Markdown answer, refusal card, governance timeline, approval card, and resume controls. Remove only imports/helpers/styles that `npm --prefix apps/web run check` proves unused.

- [ ] **Step 5: Run focused UI verification and verify GREEN**

Run:

```powershell
npm --prefix apps/web test -- src/lib/turnPhases.test.ts src/lib/views/ChatView.test.ts
npm --prefix apps/web run check
```

Expected: all selected tests pass and Svelte reports zero errors.

- [ ] **Step 6: Commit the two Chat fixes**

```powershell
git add -- apps/web/src/lib/turnPhases.ts apps/web/src/lib/turnPhases.test.ts apps/web/src/lib/views/ChatView.svelte apps/web/src/lib/views/ChatView.test.ts
git commit -m "fix: separate multi-call chat responses"
```

---

### Task 2: Add the repository-owned deterministic live model

**Files:**
- Create: `apps/web/e2e/fixtures/stub_model.py`
- Create: `tests/test_live_stub_model.py`
- Modify: `apps/web/e2e/add-02-batched-approval-queue-live.spec.ts`
- Modify: `apps/web/e2e/bug-52-first-pass-denial-live.spec.ts`

**Interfaces:**
- Produces: loopback HTTP server supporting `GET /v1/models` and `POST /v1/chat/completions` on a positional port defaulting to `8811`.
- Produces: model id `raiker-batch-stub` and deterministic OpenAI-compatible streaming chunks.

- [ ] **Step 1: Write the failing fixture contract test**

The test imports `apps.web.e2e.fixtures.stub_model`, starts `serve(port=free_port)` in a daemon thread, and asserts literal response behavior:

```python
def test_stub_catalogue_and_refusal_then_read_batch(free_port: int) -> None:
    with running_stub(free_port):
        models = httpx.get(f"http://127.0.0.1:{free_port}/v1/models").json()
        assert [item["id"] for item in models["data"]] == ["raiker-batch-stub"]
        response = httpx.post(
            f"http://127.0.0.1:{free_port}/v1/chat/completions",
            json={
                "model": "raiker-batch-stub",
                "stream": False,
                "messages": [{"role": "user", "content": "Read ../escape.md and list the workspace."}],
                "tools": TOOL_SPECS,
            },
        ).json()
        names = [call["function"]["name"] for call in response["choices"][0]["message"]["tool_calls"]]
        assert names == ["read_file", "list_directory"]
```

Add separate assertions for the three writes, refusal followed by two writes, SSE `[DONE]`, and a tool-result follow-up answer containing `policy refused that one call`.

- [ ] **Step 2: Run the fixture test and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests/test_live_stub_model.py -q`

Expected: import failure because the checked-in fixture does not exist.

- [ ] **Step 3: Implement the dependency-free stub**

Use `ThreadingHTTPServer` and `BaseHTTPRequestHandler`. Bind only `127.0.0.1`, cap request bodies at 1 MiB, suppress request-body logging, return OpenAI-compatible JSON, encode tool arguments as JSON strings, and emit valid `data: <serialized-completion-chunk>\n\n` SSE chunks plus `data: [DONE]`. Select exact batch shapes by the last user message and tool-result presence.

- [ ] **Step 4: Update both live specs to repository paths**

Replace `<scratch>/stub_model.py` with:

```text
python apps/web/e2e/fixtures/stub_model.py 8811
```

Keep the explicit statement that the fixture replaces only the upstream model while the API, orchestrator, broker, approvals, suspension store, resume route, and UI remain live product code.

- [ ] **Step 5: Run the focused fixture verification and verify GREEN**

Run: `.venv\Scripts\python.exe -m pytest tests/test_live_stub_model.py -q`

Expected: all fixture contract cases pass with no network beyond loopback.

- [ ] **Step 6: Commit the reproducible fixture**

```powershell
git add -- apps/web/e2e/fixtures/stub_model.py apps/web/e2e/add-02-batched-approval-queue-live.spec.ts apps/web/e2e/bug-52-first-pass-denial-live.spec.ts tests/test_live_stub_model.py
git commit -m "test: check in the live batching model"
```

---

### Task 3: Add connection-aware rolling usage and owner weekly budgets

**Files:**
- Modify: `raiker/storage/migrations.py`
- Modify: `raiker/storage/sqlite.py`
- Modify: `raiker/runtime/model_usage.py`
- Modify: `raiker/runtime/orchestrator.py`
- Modify: `tests/test_model_cost_accounting.py`
- Modify: `tests/test_storage_sqlite.py`

**Interfaces:**
- Produces: `ModelUsageLedger.record(*, owner_principal_id: str, session_id: str, provider: str, model: str, usage: Mapping[str, Any] | None, profile_id: str | None = None, request_kind: str = "turn", recorded_at: str | None = None) -> bool`.
- Produces: `ModelUsageLedger.provider_usage(owner_principal_id: str, *, profile_id: str | None = None, started_at: str | None = None, ended_at: str | None = None) -> list[ModelUsageRow]`.
- Produces: `ModelUsageLedger.weekly_usage(owner_principal_id: str, profile_id: str, *, now: datetime) -> UsageTotals`.
- Produces: `ModelUsageLedger.set_weekly_token_budget(owner_principal_id: str, profile_id: str, tokens: int | None) -> None`.
- Produces: `UsageTotals.requests`, `UsageTotals.turns`, and `UsageTotals.compactions` alongside token counts.

- [ ] **Step 1: Write failing rolling-window and connection-scope tests**

Add hand-derived rows with fixed UTC timestamps. Assert that an eight-day-old row is excluded, the window includes rows at its inclusive lower bound, two profiles from one provider remain separate, and a `request_kind="compaction"` contributes tokens/cost but not user turns.

```python
def test_weekly_usage_is_profile_scoped_and_excludes_older_rows(store: SQLiteStore) -> None:
    ledger = ModelUsageLedger(store)
    common = {"owner_principal_id": "p1", "session_id": "s1", "provider": "openai", "model": "gpt-5"}
    ledger.record(**common, profile_id="openai-hosted", recorded_at="2026-08-10T12:00:00+00:00", usage={"input_tokens": 80})
    ledger.record(**common, profile_id="openai-hosted", recorded_at="2026-08-01T12:00:00+00:00", usage={"input_tokens": 900})
    ledger.record(**common, profile_id="openai-compatible", recorded_at="2026-08-10T12:00:00+00:00", usage={"input_tokens": 40})
    totals = ledger.weekly_usage("p1", "openai-hosted", now=datetime(2026, 8, 11, 12, tzinfo=UTC))
    assert totals.input_tokens == 80
    assert totals.turns == 1
```

Add budget tests for set, update, clear, non-positive rejection, and owner isolation.

- [ ] **Step 2: Run focused ledger tests and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests/test_model_cost_accounting.py tests/test_storage_sqlite.py -q`

Expected: failures for missing `profile_id`, `request_kind`, bounded query, and budget APIs.

- [ ] **Step 3: Add additive schema migrations**

Add one migration that appends nullable `profile_id` and non-null `request_kind DEFAULT 'turn'` to `model_usage_ledger`, plus an owner/profile/time index. Add `model_weekly_budgets(owner_principal_id, profile_id, token_budget, updated_at, PRIMARY KEY(owner_principal_id, profile_id))`. Import and apply both migrations in `SQLiteStore.bootstrap()` after the original ledger migration.

- [ ] **Step 4: Implement bounded aggregation and budgets**

Change aggregation SQL to group by `profile_id, provider, model`, count every request, and derive user turns and compactions with conditional `SUM(CASE WHEN request_kind = <kind> THEN 1 ELSE 0 END)` expressions. Validate request kinds against `{"turn", "compaction", "readiness"}`. Keep old rows readable with null profile ids. Compute the rolling window as `[now - timedelta(days=7), now]` in UTC.

- [ ] **Step 5: Record the serving profile and compaction purpose**

In `Orchestrator._record_usage`, resolve the serving profile through `self.model_router.registry.resolve(provider, model).profile_id`; fall back to `None` only when the registry cannot resolve it. Preserve current best-effort accounting and add `request_kind` as an explicit keyword.

- [ ] **Step 6: Run focused storage verification and verify GREEN**

Run: `.venv\Scripts\python.exe -m pytest tests/test_model_cost_accounting.py tests/test_storage_sqlite.py -q`

Expected: all selected tests pass and existing all-time/session totals remain unchanged for ordinary turn rows.

- [ ] **Step 7: Commit rolling usage storage**

```powershell
git add -- raiker/storage/migrations.py raiker/storage/sqlite.py raiker/runtime/model_usage.py raiker/runtime/orchestrator.py tests/test_model_cost_accounting.py tests/test_storage_sqlite.py
git commit -m "feat: add rolling provider usage storage"
```

---

### Task 4: Normalize connected-provider native usage and expose owner-scoped APIs

**Files:**
- Create: `raiker/models/provider_usage.py`
- Create: `tests/test_provider_weekly_usage.py`
- Modify: `raiker/storage/migrations.py`
- Modify: `raiker/storage/sqlite.py`
- Modify: `raiker/api/schemas.py`
- Modify: `raiker/api/routes_dashboard.py`
- Modify: `raiker/control/dashboard.py`
- Modify: `raiker/models/connections.py`
- Modify: `tests/test_api_model_selection.py`
- Modify: `tests/test_api_dashboard.py`

**Interfaces:**
- Produces: `NativeUsageMetric(unit, used, limit, remaining, reset_interval, resets_at, scope, source)`.
- Produces: `ProviderUsageRow(profile_id, provider, display_name, observed, owner_budget, native, native_status, native_checked_at)`.
- Produces: `ProviderUsageService.weekly_rows(principal_id: str, *, now: datetime, refresh_native: bool) -> Sequence[ProviderUsageRow]`.
- Produces: `ProviderUsageSnapshotStore.latest(owner_principal_id: str, profile_id: str) -> NativeQuotaSnapshot | None` and `put(owner_principal_id: str, profile_id: str, snapshot: NativeQuotaSnapshot) -> None` for normalized, metadata-only five-minute caching.
- Produces: `GET /api/models/weekly-usage?refresh_native=false`.
- Produces: `PUT /api/models/{profile_id}/weekly-budget` with `{ "token_budget": positive-int-or-null }`.
- Extends: `ModelConnectionRequest.admin_api_key: str | None` and connection metadata `usage_admin_configured: bool` without returning a key.

- [ ] **Step 1: Write failing service tests with real HTTP parsing**

Use `httpx.MockTransport`, complete documented response shapes, and literal expectations. Cover:

- OpenRouter ordinary `GET /api/v1/key`: `usage_weekly`, `limit`, `limit_remaining`, `limit_reset`.
- OpenAI admin usage buckets: aggregate input, cached input, output, and requests for the requested seven-day range.
- Anthropic admin daily buckets: aggregate uncached, cache creation, cache read, output, and requests.
- Ollama/unsupported provider: no native metric, observed row retained.
- malformed, negative, oversized, 401/403, timeout, and secret-shaped payloads: native status unavailable, no exception escaping.
- only saved hosted connections and currently ready local profiles produce rows.

```python
async def test_openrouter_normal_key_reports_weekly_usage(mock_transport: httpx.MockTransport) -> None:
    snapshot = await OpenRouterUsageAdapter(client=client(mock_transport)).read(connection={"api_key": "test"})
    assert snapshot.metrics == (
        NativeUsageMetric(
            unit="USD", used=Decimal("25.5"), limit=Decimal("100"),
            remaining=Decimal("74.5"), reset_interval="weekly",
            resets_at=None, scope="api_key", source="provider",
        ),
    )
```

- [ ] **Step 2: Run provider tests and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests/test_provider_weekly_usage.py tests/test_api_model_selection.py tests/test_api_dashboard.py -q`

Expected: import/route/schema failures for the new service and contracts.

- [ ] **Step 3: Add normalized provider-snapshot caching**

Add `provider_usage_snapshots(owner_principal_id, profile_id, status, metrics_json, reason_code, checked_at, expires_at, PRIMARY KEY(owner_principal_id, profile_id))`. Persist only the normalized bounded metric contract; never persist raw provider responses, credentials, headers, key labels, or account identifiers. Add owner/profile and expiry indexes and apply the migration during bootstrap.

- [ ] **Step 4: Implement adapters and normalization**

Use the existing encrypted connection resolver and provider runtime policy. Enforce the configured endpoint's model-egress rule before a native request. Cap responses at 1 MiB, use bounded connect/read timeouts, validate finite non-negative Decimal values, cache successful and failed snapshots for five minutes, and never persist raw provider payloads.

OpenRouter uses its configured inference key. OpenAI and Anthropic adapters run only when `admin_api_key` is present; they do not try an inference key against an admin endpoint. Other providers return `not_supported` while observed usage remains available.

- [ ] **Step 5: Build connected-only weekly rows and exact cost**

Resolve connected profiles from `list_model_connections`; add ready local profiles from unexpired readiness rows. For each profile, aggregate the rolling ledger by `profile_id`, price each model at its own facts, attach its owner budget, and then optionally attach the native snapshot. Unknown prices yield `cost=None` and `price_unknown=True`.

- [ ] **Step 6: Add owner-scoped read/write routes**

Define strict Pydantic schemas (`extra="forbid"`) and return serialized dataclasses. The budget route rejects unknown/disconnected profiles with 404, non-positive or boolean values with 422, and records an audit event carrying only profile id, action, and numeric budget. Extend the connection route to store the optional admin key in the same vault entry and expose only `usage_admin_configured` in model/profile views.

- [ ] **Step 7: Run focused API verification and verify GREEN**

Run: `.venv\Scripts\python.exe -m pytest tests/test_provider_weekly_usage.py tests/test_api_model_selection.py tests/test_api_dashboard.py tests/test_model_cost_accounting.py -q`

Expected: all selected tests pass; no API response contains `api_key`, `admin_api_key`, or a key-shaped label.

- [ ] **Step 8: Commit provider usage APIs**

```powershell
git add -- raiker/models/provider_usage.py raiker/storage/migrations.py raiker/storage/sqlite.py raiker/api/schemas.py raiker/api/routes_dashboard.py raiker/control/dashboard.py raiker/models/connections.py tests/test_provider_weekly_usage.py tests/test_api_model_selection.py tests/test_api_dashboard.py
git commit -m "feat: expose connected provider weekly usage"
```

---

### Task 5: Add the connected-provider Usage & limits UI

**Files:**
- Create: `apps/web/src/lib/components/ProviderUsagePanel.svelte`
- Create: `apps/web/src/lib/components/ProviderUsagePanel.test.ts`
- Modify: `apps/web/src/lib/apiTypes.ts`
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/lib/views/ModelsView.svelte`
- Modify: `apps/web/src/lib/views/ModelsView.test.ts`

**Interfaces:**
- Consumes: `ProviderWeeklyUsageView` from `GET /api/models/weekly-usage`.
- Produces: connected-only rows, observed/native source labels, owner-budget controls, and per-row refresh/error states.

- [ ] **Step 1: Write failing component tests**

Render the real component with complete typed fixtures. Assert:

```ts
it("shows only returned connected providers and distinguishes both sources", async () => {
  render(ProviderUsagePanel, { usage: connectedUsageFixture, onsave: vi.fn(), onrefresh: vi.fn() });
  expect(screen.getByText("Anthropic")).toBeInTheDocument();
  expect(screen.queryByText("Gemini")).not.toBeInTheDocument();
  expect(screen.getByText("Observed by Raiker · last 7 days")).toBeInTheDocument();
  expect(screen.getByText("Reported by OpenRouter")).toBeInTheDocument();
});

it("calls the owner-budget contract without presenting it as a provider limit", async () => {
  const onsave = vi.fn();
  render(ProviderUsagePanel, { usage: connectedUsageFixture, onsave, onrefresh: vi.fn() });
  await fireEvent.input(screen.getByLabelText("OpenRouter weekly token budget"), { target: { value: "250000" } });
  await fireEvent.click(screen.getByRole("button", { name: "Save OpenRouter budget" }));
  expect(onsave).toHaveBeenCalledWith("openrouter", 250000);
  expect(screen.getByText("Owner budget")).toBeInTheDocument();
});
```

Also test empty state, local provider copy, unknown cost, native failure isolation, accessible meter values, clearing a budget, keyboard operation, and no credential-like text.

- [ ] **Step 2: Run component tests and verify RED**

Run: `npm --prefix apps/web test -- src/lib/components/ProviderUsagePanel.test.ts src/lib/views/ModelsView.test.ts`

Expected: import/type failures because the component and API types do not exist.

- [ ] **Step 3: Add API types and client methods**

Define exact `ProviderObservedUsage`, `NativeUsageMetric`, `ProviderWeeklyUsageRow`, and `ProviderWeeklyUsageView` interfaces. Add `api.providerWeeklyUsage(refreshNative = false)` and `api.setProviderWeeklyBudget(profileId, tokenBudget)`.

- [ ] **Step 4: Implement the panel with existing primitives**

Use `ProviderLogo`, existing `.card`, `.chip`, `.meter`, `.btn`, form-control tokens, `formatCost`, and locale number formatting. Render source labels as visible text. Clamp visual meters while preserving exact accessible numeric values. Keep error/loading state per profile and do not replace the whole panel when one native adapter fails.

- [ ] **Step 5: Integrate the panel and optional admin credential controls**

Load observed usage after `api.models()` resolves. Render `ProviderUsagePanel` once above the provider catalogue on provider tabs. Refresh native data only when the owner presses Refresh. In the connection dialog, show an optional collapsed `Provider usage access` field only for OpenAI and Anthropic, explain that it requires a separate admin key, and never prefill it. Extend `saveModelConnection` without exposing stored values.

- [ ] **Step 6: Run focused UI verification and verify GREEN**

Run:

```powershell
npm --prefix apps/web test -- src/lib/components/ProviderUsagePanel.test.ts src/lib/views/ModelsView.test.ts
npm --prefix apps/web run check
npm --prefix apps/web run lint
```

Expected: selected tests pass; Svelte and ESLint report zero errors.

- [ ] **Step 7: Commit the weekly UI**

```powershell
git add -- apps/web/src/lib/components/ProviderUsagePanel.svelte apps/web/src/lib/components/ProviderUsagePanel.test.ts apps/web/src/lib/apiTypes.ts apps/web/src/lib/api.ts apps/web/src/lib/views/ModelsView.svelte apps/web/src/lib/views/ModelsView.test.ts
git commit -m "feat: show connected provider usage and limits"
```

---

### Task 6: Add durable context compaction planning and protected state

**Files:**
- Create: `raiker/runtime/conversation_compaction.py`
- Create: `tests/test_conversation_compaction.py`
- Modify: `raiker/storage/migrations.py`
- Modify: `raiker/storage/sqlite.py`
- Modify: `raiker/hooks/contracts.py`
- Modify: `tests/test_hooks.py`

**Interfaces:**
- Produces: `estimate_message_tokens(messages: Sequence[ModelMessage]) -> int`.
- Produces: `ContextBudgetPlan(should_compact, estimated_tokens, capacity_tokens, threshold_tokens, compact_through_turn_id, eligible_turns)`.
- Produces: `ContextBudgetPlanner.plan(store, owner_principal_id, session_id, capacity_tokens, fixed_messages, current_prompt, latest_compaction) -> ContextBudgetPlan`.
- Produces: `ContextCompactionStore.latest(owner_principal_id: str, session_id: str) -> ContextCompactionRecord | None`, `record_success(record: ContextCompactionRecord) -> None`, and `record_failure(record: ContextCompactionRecord) -> None`.
- Produces: `protected_context(store, owner_principal_id, session_id) -> str`.
- Extends hook events with `PreCompact` and `PostCompact`.

- [ ] **Step 1: Write failing pure planning and persistence tests**

Cover exact threshold behavior at 89.99%/90%, unknown capacity (no compaction), newest-turn retention, owner/session isolation, successful boundary replay, failure records not becoming active summaries, transcript rows unchanged, and protected state containing literal plan/approval ids from stores.

```python
def test_compaction_triggers_at_ninety_percent() -> None:
    plan = planner.plan_messages(
        capacity_tokens=100,
        fixed_messages=[ModelMessage("system", "x" * 180)],
        history=[exchange("u" * 90, "a" * 90)],
        current_prompt="z",
    )
    assert plan.estimated_tokens >= 90
    assert plan.should_compact is True
```

- [ ] **Step 2: Run compaction tests and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests/test_conversation_compaction.py tests/test_hooks.py -q`

Expected: import failures for the compaction module and unknown hook events.

- [ ] **Step 3: Add the durable compaction schema**

Create `conversation_compactions` with the design fields, a `status IN ('completed','failed')` check, owner/session/time indexes, and no foreign-key deletion of transcript turns. Import and apply the migration after session/turn tables exist.

- [ ] **Step 4: Implement planner, store, and protected-state serialization**

Estimate tokens as `ceil(total UTF-8 text characters / 4)` and state the estimate source. Pick the oldest eligible completed turns while always retaining the two newest completed exchanges verbatim. A successful stored compaction is active only through its exact `through_turn_id`. Generate the protected block from `load_agent_plan`, `list_pending_suspended_turns`, checkpoint metadata, and turn-source ids; emit no credential or source content.

- [ ] **Step 5: Extend hooks without widening authority**

Add `PreCompact` and `PostCompact` to `HOOK_EVENTS`. They accept session/turn/context metadata and may add context or make the operation stricter; they cannot allow tools or override policy. Add dispatcher tests for matching, execution order, and denial.

- [ ] **Step 6: Run focused compaction verification and verify GREEN**

Run: `.venv\Scripts\python.exe -m pytest tests/test_conversation_compaction.py tests/test_hooks.py tests/test_owner_consent_and_history.py -q`

Expected: all selected tests pass and original bounded-history behavior remains a safe fallback.

- [ ] **Step 7: Commit the compaction foundation**

```powershell
git add -- raiker/runtime/conversation_compaction.py raiker/storage/migrations.py raiker/storage/sqlite.py raiker/hooks/contracts.py tests/test_conversation_compaction.py tests/test_hooks.py
git commit -m "feat: add durable context compaction planning"
```

---

### Task 7: Integrate 90% compaction into turns and surface its status

**Files:**
- Modify: `raiker/runtime/orchestrator.py`
- Modify: `raiker/runtime/conversation_history.py`
- Modify: `raiker/control/dashboard.py`
- Modify: `tests/test_owner_consent_and_history.py`
- Modify: `tests/test_model_tool_call_loop.py`
- Modify: `tests/test_api_dashboard.py`
- Modify: `apps/web/src/lib/apiTypes.ts`
- Modify: `apps/web/src/lib/components/ContextMeterPopover.svelte`
- Modify: `apps/web/src/lib/components/ContextMeterPopover.test.ts`

**Interfaces:**
- Consumes: `ContextBudgetPlanner`, `ContextCompactionStore`, provider `ModelRouter.achat`, and the broker's existing `hook_dispatcher`.
- Produces: lifecycle events `compacted_context_created` and `compacted_context_failed`.
- Extends: `ContextUsage` with `latest_compaction` metadata.

- [ ] **Step 1: Write failing orchestrator integration tests**

Use a real store and a recording model router. Assert:

- below 90%, the router receives one normal request;
- at 90%, the first request has `tools is None`, a bounded compaction prompt, and reasoning disabled; the second request is the user turn with the stored summary plus newest exchanges;
- a summary request's usage is recorded as `request_kind="compaction"`;
- provider summary failure emits `compacted_context_failed` and the normal turn continues with recent history;
- a denied PreCompact hook prevents compaction and records a safe failure reason;
- original transcript rows and export text are unchanged;
- the summary cannot replace locally serialized protected plan/approval state.

- [ ] **Step 2: Run orchestrator tests and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests/test_model_tool_call_loop.py tests/test_owner_consent_and_history.py tests/test_api_dashboard.py -q`

Expected: missing compaction calls/events/metadata.

- [ ] **Step 3: Prepare history asynchronously before the agent loop**

After assembling fixed system/retrieval/plan/skill messages and before appending the current prompt to the normal agent loop, calculate the budget. When compaction is required:

1. dispatch `PreCompact` through `tool_broker.hook_dispatcher` when active;
2. call the selected provider once with no tools, `ReasoningOptions(enabled=False)`, and a bounded output;
3. validate non-empty bounded text, append protected context, persist the exact turn boundary, record usage as compaction, and emit `compacted_context_created`;
4. dispatch `PostCompact`; and
5. replay the active summary plus turns after the boundary.

On any classified failure, persist metadata-only failure, emit `compacted_context_failed`, and use `conversation_messages`' recent-history fallback. Do not put summary text in lifecycle payloads or logs.

- [ ] **Step 4: Expose compaction metadata in the existing context API**

Add `latest_compaction` containing `created_at`, `source_turn_count`, `estimated_input_tokens_before`, `estimated_summary_tokens`, and `status`. Owner/session scope it in `DashboardService.get_context_usage`.

- [ ] **Step 5: Render compaction status in Chat and Build context popovers**

Below the context meter, render `Earlier context compacted` with relative time and before/after token estimates for a completed record. For a latest failed attempt, render `Recent history retained; compaction was unavailable` without hiding the working context/cost data. Use visible copy and existing status tones.

- [ ] **Step 6: Run focused backend/frontend verification and verify GREEN**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_model_tool_call_loop.py tests/test_owner_consent_and_history.py tests/test_api_dashboard.py -q
npm --prefix apps/web test -- src/lib/components/ContextMeterPopover.test.ts
npm --prefix apps/web run check
```

Expected: all selected tests pass; no transcript or export test regresses.

- [ ] **Step 7: Commit runtime compaction**

```powershell
git add -- raiker/runtime/orchestrator.py raiker/runtime/conversation_history.py raiker/control/dashboard.py tests/test_owner_consent_and_history.py tests/test_model_tool_call_loop.py tests/test_api_dashboard.py apps/web/src/lib/apiTypes.ts apps/web/src/lib/components/ContextMeterPopover.svelte apps/web/src/lib/components/ContextMeterPopover.test.ts
git commit -m "feat: compact conversation context at ninety percent"
```

---

### Task 8: Close logs, re-derive documentation, and run local acceptance

**Files:**
- Modify: `README.md`
- Modify: `docs/guide/working-in-chat.md`
- Modify: `docs/guide/connecting-a-model.md`
- Modify: `docs/API_AND_CONTRACT_SCHEMAS.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/MEMORY_AND_CONTEXT_STRATEGY.md`
- Modify: `docs/SECURITY_AND_POLICY.md`
- Modify: `docs/plans/TO_BE_FIXED.md`
- Modify: `docs/plans/FIXED_ITEMS.md`
- Modify: `docs/plans/RAIKER_LIVE_MANUAL_TEST_PLAN.md`
- Modify: `tests/test_docs_consistency.py`
- Modify: `tests/test_repo_truthfulness_validator.py`

**Interfaces:**
- Produces: fixed-item records preserving observation, root cause, required UI, implementation, tests, and live evidence.
- Produces: README Known Limits that name only boundaries still present in the code.

- [ ] **Step 1: Write failing documentation truth tests where behavior is machine-checkable**

Update repository-truth tests to require no open BUG-53/54/55 rows, require every README work limit to have an open plan reference or explicit deliberate-boundary wording, and reject the stale sentence `Automatic context compaction at 90 % and weekly quota display are specified but not shipped.`

- [ ] **Step 2: Run focused documentation tests and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests/test_docs_consistency.py tests/test_repo_truthfulness_validator.py -q`

Expected: failures against the current open bug table and Known Limits sentence.

- [ ] **Step 3: Move fixed records and re-derive Known Limits**

Move BUG-53, BUG-54, and BUG-55 in full to `FIXED_ITEMS.md`; add separately numbered fixed records for automatic compaction and connected-provider weekly usage/quotas. Remove the five closed items from `TO_BE_FIXED.md`. Re-read every remaining README Known Limit against code/tests; delete stale entries, keep deliberate security/product boundaries, and update the as-of date. Apply the same removal and source-aware quota explanation in `working-in-chat.md`.

- [ ] **Step 4: Update architecture, API, security, and user guidance**

Document:

- response seams and checked-in fixture path;
- rolling seven-day vs provider-native source labels;
- connected-only row eligibility;
- optional OpenAI/Anthropic admin telemetry and OpenRouter ordinary-key telemetry;
- owner weekly budgets as advisory, not provider enforcement;
- 90% compaction trigger, durable boundary, protected state, events, hooks, and transcript preservation;
- troubleshooting for unavailable native quota and failed compaction.

- [ ] **Step 5: Run workflow-equivalent local gates**

Run fresh and read every exit code:

```powershell
.venv\Scripts\python.exe -m pytest tests
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy raiker apps tests
npm --prefix apps/web test
npm --prefix apps/web run check
npm --prefix apps/web run lint
npm --prefix apps/web run build
npm --prefix apps/web run test:e2e:mocked
.venv\Scripts\python.exe scripts/licensing_check.py
.venv\Scripts\python.exe scripts/validate_documentation_truthfulness.py
.venv\Scripts\python.exe scripts/validate_repo_truthfulness.py
```

Expected: zero failures, zero type errors, zero lint errors, successful production build, and all mocked Playwright scenarios passing.

- [ ] **Step 6: Run the checked-in stub live scenarios**

Start the fixture and API against a fresh workspace using hidden background processes. Keep the non-secret loopback allowlist in process configuration. Run the ADD-02 and BUG-52 live projects and the multi-response seam assertion. Capture only post-credential/post-dialog screenshots under `output/playwright/`, inspect them with the image viewer, then stop both processes.

- [ ] **Step 7: Commit the documentation and local acceptance record**

```powershell
git add -- README.md docs tests/test_docs_consistency.py tests/test_repo_truthfulness_validator.py
git commit -m "docs: close chat compaction and weekly usage limits"
```

---

### Task 9: Run live UI tests across all requested providers and make GitHub Actions green

**Files:**
- Modify when evidence changes: `docs/plans/RAIKER_LIVE_MANUAL_TEST_PLAN.md`
- Create screenshots only after inspection: `output/playwright/*.png`
- Modify on discovered unresolved issue: `docs/plans/TO_BE_FIXED.md`

**Interfaces:**
- Consumes: the Models connection UI, Playwright CLI snapshots/refs, four provider connections, and GitHub Actions.
- Produces: a credential-free live acceptance record and a green pushed SHA on `origin/main`.

- [ ] **Step 1: Check Playwright CLI prerequisites**

Run `Get-Command npx` and then the bundled Playwright wrapper help command. If Node/npm is missing, stop and request installation using the Playwright skill's required wording. Create/retain artifacts only under `output/playwright/`.

- [ ] **Step 2: Start a fresh headed live instance**

Create a task-specific temporary workspace within the repository or system temp, start `raiker-web` hidden on an available loopback port with only the required non-secret model-egress hosts configured, and open the app headed. Do not put any provider key in the process environment or command line.

- [ ] **Step 3: Connect and test providers through the UI**

For Anthropic, OpenRouter, OpenAI, and Ollama `gemma4:31b-cloud`, use the Models UI to connect, select an exact live model, pass readiness, stream a simple answer, and run a tool-using turn. Enter the supplied secrets only into the visible credential fields through headed GUI interaction, never as literal `playwright-cli fill` shell arguments; use Playwright snapshots before element refs and re-snapshot after every navigation/modal change. Close all credential dialogs before screenshots.

- [ ] **Step 4: Verify weekly usage and response seams visually**

Open **Usage & limits** and prove:

- every connected provider appears and no disconnected provider appears;
- OpenRouter genuine weekly/native values render when returned;
- OpenAI/Anthropic/Ollama observed values render with honest native-availability copy;
- tokens, turns, and known prices match the live ledger;
- set/edit/clear owner budgets work for each connected row;
- disconnecting a provider removes its row;
- a tool-using answer has a visible paragraph boundary between model responses.

Capture light/dark and desktop/mobile screenshots only after the key fields are gone. Use the local image viewer to verify exact layout, clipping, overflow, focus states, and absence of secrets.

- [ ] **Step 5: Record any discovered issue**

Fix in-scope regressions test-first. If an issue cannot be fixed without expanding authority or scope, add a full BUG entry to `TO_BE_FIXED.md` containing severity, observation, reproduction, root cause/evidence, required fix, and UI outcome; name it in the final summary.

- [ ] **Step 6: Re-run the full verification gate after live fixes**

Repeat every command from Task 8 Step 5. Confirm `git diff --check`, inspect `git status --short`, and review the complete diff for credentials or unrelated changes.

- [ ] **Step 7: Commit remaining evidence and push**

```powershell
git add -- README.md docs raiker apps tests config
git commit -m "test: verify live provider usage and compaction"
git push origin main
```

If there are no remaining tracked changes, do not create an empty commit; push the existing implementation commits.

- [ ] **Step 8: Monitor GitHub Actions for the pushed SHA**

Verify `gh auth status`, obtain `git rev-parse HEAD`, and list workflow runs for that exact SHA. Watch every GitHub Actions run until terminal. For a repository-owned failure, inspect the run and job logs, state the root cause, implement the smallest test-first fix already authorized by the owner's `make it green` instruction, rerun the local affected/full gate, commit, push, and restart monitoring. External provider checks are reported by URL only.

- [ ] **Step 9: Stop live services and perform the completion gate**

Stop only the fixture/API processes started by this task. Prove no Raiker listener remains, then verify final branch/remote equality, clean tracked status, full local gate results, live screenshot inspection, and green workflow conclusions before reporting completion.
