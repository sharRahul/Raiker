# Chat Composer Context Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Chat composer expose only configured models, truthful live context/cost/quota data, global approval modes, and safe automatic 90% context compaction.

**Architecture:** Extend the existing models/dashboard read DTOs with configuration-owned capacity and pricing facts. Add a session-scoped usage ledger and compaction service to the prompt path; the web UI consumes the read model through focused Svelte controls, never from provider catalogue discovery.

**Tech Stack:** Python 3/FastAPI/SQLite, existing model contracts and gateway, Svelte 5/TypeScript/Vitest.

## Global Constraints

- Chat lists only configured, usable model profiles; it never lists remote provider catalogues or free-text model ids.
- Context click is read-only; automatic compaction runs at exactly 90% of known capacity.
- Counts, cost, quota, and exchange conversion must be omitted or labelled estimated/unavailable when their source is unavailable.
- Permission changes use existing authorized/audited capability decision modes; no unrestricted mode is added.
- Governance evidence stays in Sessions/Checkpoints, not normal chat bubbles.

## Implementation status (2026-07-26)

The configured-profile selector, conservative transcript estimate, read-only
context popover, and global permission control are implemented. The selector
does not expose provider catalogues or arbitrary model ids. The current context
meter is explicitly an estimate derived from chat text because no configured
profile currently supplies a trusted capacity/usage source.

The following remain open and must not be represented as shipped: provider
token/accounting data, configured pricing and local-currency display, weekly
quota data, a session usage endpoint, and automatic 90% compaction. The
checkboxes below remain the source of truth for those unimplemented steps.

---

### Task 1: Profile context/pricing contract

**Files:**
- Modify: `raiker/control/dashboard.py:423-490, 2005-2065`
- Modify: `apps/web/src/lib/apiTypes.ts:160-190`
- Modify: `raiker/config/model-profiles.json`
- Test: `tests/test_api_dashboard.py`
- Test: `apps/web/src/lib/views/ChatView.test.ts`

**Interfaces:**
- Produces `ModelProfileView.context_window_tokens: int | None`, `configured: bool`, and `pricing: dict[str, object] | None`.
- Consumed by the Chat selector and `ContextMeterPopover` in Task 4.

- [ ] **Step 1: Write the failing dashboard contract test**

```python
def test_models_exposes_only_configured_chat_profiles_and_context(client, owner_token):
    body = client.get("/api/models", headers=_auth(owner_token)).json()
    profile = next(row for row in body["profiles"] if row["profile_id"] == "anthropic-hosted")
    assert "context_window_tokens" in profile
    assert profile["configured"] is True
    assert all(row["configured"] for row in body["chat_profiles"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_api_dashboard.py::TestDashboardApi::test_models_exposes_only_configured_chat_profiles_and_context -v`

- [ ] **Step 3: Add the minimal DTO/config implementation**

```python
@dataclass(frozen=True)
class ModelProfileView:
    # existing fields ...
    context_window_tokens: int | None = None
    configured: bool = False
    pricing: dict[str, object] | None = None

# `get_models` reads only `context_window_tokens` and `pricing` from profile.raw,
# validates positive integers/non-negative prices, and populates `chat_profiles`
# from profiles that are configured for the acting principal.
```

Add only documented capacities and pricing to `model-profiles.json`; placeholders
remain capacity/pricing unknown. Mirror the fields in TypeScript.

- [ ] **Step 4: Run backend contract and web type tests**

Run: `pytest tests/test_api_dashboard.py tests/test_api_contract_schemas.py -v; npm.cmd run check`

- [ ] **Step 5: Commit**

```bash
git add raiker/control/dashboard.py raiker/config/model-profiles.json apps/web/src/lib/apiTypes.ts tests/test_api_dashboard.py tests/test_api_contract_schemas.py
git commit -m "feat(models): expose configured context capacity"
```

### Task 2: Session usage, cost, quota, and compaction service

**Files:**
- Create: `raiker/runtime/context_usage.py`
- Modify: `raiker/storage/migrations.py`
- Modify: `raiker/storage/sqlite.py`
- Modify: `raiker/gateway/agent_gateway.py`
- Modify: `raiker/api/routes_dashboard.py`
- Modify: `raiker/control/dashboard.py`
- Test: `tests/test_context_usage.py`
- Test: `tests/test_api_dashboard.py`

**Interfaces:**
- Produces `ContextUsageView(session_id, profile_id, used_tokens, context_window_tokens, source, cost, currency, weekly_usage)` from `GET /api/sessions/{session_id}/context-usage`.
- Consumes provider `summarize_model_usage` data and profile pricing from Task 1.
- Produces `ContextCompactionService.compact_if_needed(envelope, transcript) -> CompactionResult` consumed by `AgentGateway` before the model request.

- [ ] **Step 1: Write failing usage and threshold tests**

```python
def test_usage_prefers_provider_prompt_tokens_and_calculates_configured_price(store):
    view = ContextUsageService(store).record_usage(
        session_id="sess_1", profile=profile, usage={"prompt_tokens": 900, "completion_tokens": 100}
    )
    assert view.used_tokens == 900
    assert view.source == "provider"
    assert view.cost == Decimal("0.004")

def test_compaction_runs_before_a_turn_at_ninety_percent(tmp_path):
    result = ContextCompactionService(tmp_path).compact_if_needed(usage=900, capacity=1000, transcript=TRANSCRIPT)
    assert result.compacted is True
    assert result.checkpoint_id is not None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_context_usage.py -v`

- [ ] **Step 3: Implement bounded storage and service**

```python
@dataclass(frozen=True)
class ContextUsageView:
    session_id: str
    profile_id: str
    used_tokens: int | None
    context_window_tokens: int | None
    source: Literal["provider", "estimated", "unavailable"]
    cost: Decimal | None
    currency: str | None
    weekly_usage: WeeklyUsageView | None

class ContextCompactionService:
    THRESHOLD = Decimal("0.90")
    def compact_if_needed(self, *, usage: int | None, capacity: int | None, transcript: list[Message]) -> CompactionResult: ...
```

Persist only aggregate counts, source, amount/currency, compaction id, and
checkpoint reference. Use provider input tokens where present; otherwise use a
bounded text estimate marked `estimated`. Preserve the newest messages and a
bounded summary; create a checkpoint and append the compaction evidence before
the next model invocation. On failure, return a fail-closed result without
mutating the transcript.

- [ ] **Step 4: Add the authenticated context usage route and run tests**

Run: `pytest tests/test_context_usage.py tests/test_api_dashboard.py -v`

- [ ] **Step 5: Commit**

```bash
git add raiker/runtime/context_usage.py raiker/storage/migrations.py raiker/storage/sqlite.py raiker/gateway/agent_gateway.py raiker/api/routes_dashboard.py raiker/control/dashboard.py tests/test_context_usage.py tests/test_api_dashboard.py
git commit -m "feat(chat): track context usage and compact safely"
```

### Task 3: Global approval mode facade

**Files:**
- Modify: `raiker/control/dashboard.py`
- Modify: `raiker/api/routes_dashboard.py`
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/lib/apiTypes.ts`
- Test: `tests/test_api_dashboard.py`
- Test: `apps/web/src/lib/views/ChatView.test.ts`

**Interfaces:**
- Produces `GET/PUT /api/chat-permission-mode` with `"ask" | "safe_auto" | "custom"` display states.
- Calls existing `RuntimeControlService.set_capability_decision_mode` for each authorized capability; it never bypasses the policy/audit path.

- [ ] **Step 1: Write failing authorization and mapping tests**

```python
def test_chat_permission_mode_maps_safe_auto_to_existing_capability_modes(client, owner_token):
    response = client.put("/api/chat-permission-mode", json={"mode": "safe_auto"}, headers=_auth(owner_token))
    assert response.status_code == 200
    assert response.json()["mode"] == "safe_auto"

def test_chat_permission_mode_rejects_non_human_principal(client, agent_token):
    assert client.put("/api/chat-permission-mode", json={"mode": "ask"}, headers=_auth(agent_token)).status_code == 403
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_api_dashboard.py -k chat_permission_mode -v`

- [ ] **Step 3: Implement the thin facade**

The facade determines its display state from the existing capability modes and
uses existing authorized setters with reason `chat composer global mode`. `ask`
sets all eligible capabilities to `ask`; `safe_auto` sets eligible capabilities
to `auto`; `custom` is read-only and links to `#/capabilities`.

- [ ] **Step 4: Run targeted tests**

Run: `pytest tests/test_api_dashboard.py -k chat_permission_mode -v; npm.cmd run check`

- [ ] **Step 5: Commit**

```bash
git add raiker/control/dashboard.py raiker/api/routes_dashboard.py apps/web/src/lib/api.ts apps/web/src/lib/apiTypes.ts tests/test_api_dashboard.py apps/web/src/lib/views/ChatView.test.ts
git commit -m "feat(chat): add global permission mode control"
```

### Task 4: Context and permission Svelte controls

**Files:**
- Create: `apps/web/src/lib/components/ContextMeterPopover.svelte`
- Create: `apps/web/src/lib/components/PermissionModeControl.svelte`
- Create: `apps/web/src/lib/contextPresentation.ts`
- Test: `apps/web/src/lib/contextPresentation.test.ts`
- Test: `apps/web/src/lib/components/ContextMeterPopover.test.ts`
- Test: `apps/web/src/lib/components/PermissionModeControl.test.ts`

**Interfaces:**
- `ContextMeterPopover` accepts `usage: ContextUsageView | null`, `locale`, and `currency`.
- `PermissionModeControl` accepts current mode/authority and dispatches `change` only after the API succeeds.

- [ ] **Step 1: Write failing presentation/control tests**

```ts
expect(formatContextUsage({ used_tokens: 63900, context_window_tokens: 1_000_000, source: "provider" }))
  .toEqual({ label: "63.9K / 1.0M (6%)", percent: 6, estimated: false });
expect(screen.getByRole("button", { name: /context window/i })).toBeInTheDocument();
expect(screen.queryByText(/context compacted/i)).not.toBeInTheDocument();
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm.cmd test -- contextPresentation ContextMeterPopover PermissionModeControl`

- [ ] **Step 3: Implement focused controls**

Use `Intl.NumberFormat` for locale/currency formatting, a `progressbar` with
bounded `aria-valuenow`, and omit unavailable weekly/cost rows. The popover is
purely presentational/read-only. The permission control uses the Task 3 facade
and routes Custom to `#/capabilities`.

- [ ] **Step 4: Run focused tests and checks**

Run: `npm.cmd test -- contextPresentation ContextMeterPopover PermissionModeControl; npm.cmd run check`

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/lib/components/ContextMeterPopover.svelte apps/web/src/lib/components/PermissionModeControl.svelte apps/web/src/lib/contextPresentation.ts apps/web/src/lib/contextPresentation.test.ts apps/web/src/lib/components/ContextMeterPopover.test.ts apps/web/src/lib/components/PermissionModeControl.test.ts
git commit -m "feat(chat): add context and permission controls"
```

### Task 5: Integrate controls into conversational Chat

**Files:**
- Modify: `apps/web/src/lib/views/ChatView.svelte`
- Modify: `apps/web/src/lib/views/ChatView.test.ts`
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/lib/apiTypes.ts`

**Interfaces:**
- Uses Task 1 `models.chat_profiles`, Task 2 `api.sessionContextUsage(sessionId)`, and Task 3 `api.chatPermissionMode()`.
- Sends only `model_profile`; it never sends an arbitrary `model` override.

- [ ] **Step 1: Write failing integration tests**

```ts
expect(screen.getByRole("option", { name: /configured anthropic/i })).toBeInTheDocument();
expect(screen.queryByRole("option", { name: /unconfigured/i })).not.toBeInTheDocument();
await user.click(screen.getByRole("button", { name: /context window/i }));
expect(screen.getByText("63.9K / 1.0M (6%)")).toBeInTheDocument();
expect(streamRequestBody.model).toBeUndefined();
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm.cmd test -- ChatView`

- [ ] **Step 3: Remove provider catalogue/free-text state and wire controls**

Delete `providerModels`, `modelChoice`, `onProfileChange`, and the corresponding
API use from Chat. Refresh usage when a session is loaded, a model changes, and
a streamed turn finalizes. Render the quiet `Context compacted` notice only from
the safe final response flag, never raw governance events.

- [ ] **Step 4: Run focused verification**

Run: `npm.cmd test -- ChatView; npm.cmd run check; npm.cmd run build`

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/lib/views/ChatView.svelte apps/web/src/lib/views/ChatView.test.ts apps/web/src/lib/api.ts apps/web/src/lib/apiTypes.ts
git commit -m "feat(chat): integrate contextual composer controls"
```
