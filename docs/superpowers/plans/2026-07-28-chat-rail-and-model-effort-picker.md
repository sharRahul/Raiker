# Chat Rail and Model-Effort Picker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put Background Work in Chat's own desktop right rail and allow a per-turn model/effort selection only where the provider/model advertises it.

**Architecture:** The Chat view owns its responsive local grid and reuses `BuildSidePanel`; Build's DOM and rail stay unchanged. Model profile capability metadata becomes part of `/api/models`, and a validated optional reasoning effort flows from the prompt request through `PromptOptions` into the existing provider reasoning transport.

**Tech Stack:** Svelte 5, TypeScript/Vitest, FastAPI/Pydantic, Python dataclasses/pytest.

## Global Constraints

- Keep Build's rail and existing approval policies unchanged.
- Never fabricate an effort value; derive it from the resolved profile's declared capabilities.
- Do not persist per-turn model or effort selection globally.
- Credentials used in live testing are process environment only and must never be logged or committed.

---

### Task 1: Expose and validate per-turn reasoning effort

**Files:**
- Modify: `raiker/api/schemas.py`, `raiker/api/routes_prompts.py`, `raiker/contracts/models.py`, `raiker/api/routes_dashboard.py`, `raiker/models/factory.py`, `raiker/runtime/orchestrator.py`
- Test: `tests/test_api_prompts.py`, `tests/test_api_web_read_models.py`, `tests/test_turn_model_binding.py`

**Interfaces:**
- Produces `PromptRequest.reasoning_effort: str | None`, `PromptOptions.reasoning_effort: str`, and `ModelProfile` API fields for `supports_reasoning`, `supports_reasoning_effort`, and `reasoning_effort_values`.
- Consumes the existing provider `ReasoningOptions` transport.

- [ ] **Step 1: Write failing API/turn tests**

```python
def test_prompt_rejects_effort_not_declared_by_the_resolved_profile(): ...
def test_prompt_binds_declared_effort_to_the_provider_request(): ...
def test_models_view_exposes_declared_reasoning_effort_values(): ...
```

- [ ] **Step 2: Run the focused tests to verify red**

Run: `python -m pytest --basetemp=F:\GitHub\Raiker\output\pytest-model-effort tests/test_api_prompts.py tests/test_api_web_read_models.py tests/test_turn_model_binding.py -q`

- [ ] **Step 3: Implement the minimum validated contract and propagation**

```python
if options.reasoning_effort and options.reasoning_effort not in capabilities.reasoning_effort_values:
    raise ContractValidationError("invalid_reasoning_effort")
```

- [ ] **Step 4: Run the focused tests to verify green**

- [ ] **Step 5: Commit the backend slice**

### Task 2: Render Chat's local right rail and capability-driven composer controls

**Files:**
- Modify: `apps/web/src/lib/apiTypes.ts`, `apps/web/src/lib/api.ts`, `apps/web/src/lib/views/ChatView.svelte`, `apps/web/src/lib/views/BuildView.svelte`
- Test: `apps/web/src/lib/views/ChatView.composerParity.test.ts`, `apps/web/src/lib/views/BuildView.test.ts`

**Interfaces:**
- Consumes `/api/models` reasoning capability fields and the optional `reasoning_effort` prompt body field from Task 1.
- Produces a per-turn model/effort request without calling `api.selectModel`.

- [ ] **Step 1: Write failing layout and picker tests**

```ts
it("places Chat background work in its own desktop rail, not below the composer", () => { ... });
it("shows only the selected model's declared thinking efforts", () => { ... });
it("omits thinking effort when the selected model does not support it", () => { ... });
```

- [ ] **Step 2: Run focused Vitest to verify red**

Run: `npm.cmd --prefix apps/web run test -- ChatView BuildView`

- [ ] **Step 3: Implement the responsive Chat grid and picker**

```svelte
{#if activeProfile?.supports_reasoning_effort}
  <select bind:value={reasoningEffort} aria-label="Thinking effort">...</select>
{/if}
```

- [ ] **Step 4: Run focused Vitest and `svelte-check` to verify green**

- [ ] **Step 5: Commit the UI slice**

### Task 3: Verify the built app and live providers

**Files:**
- Test only; no source changes unless a failing test identifies a defect.

- [ ] **Step 1: Run full web tests and build**

Run: `npm.cmd --prefix apps/web run test; npm.cmd --prefix apps/web run check; npm.cmd --prefix apps/web run build`

- [ ] **Step 2: Run focused Python model-effort tests**

- [ ] **Step 3: Start an isolated loopback `raiker-web` process with process-scoped provider credentials**

- [ ] **Step 4: Use Playwright to select Ollama, Anthropic, and OpenRouter models; exercise an effort picker only where that exact model advertises it, and run one authenticated end-to-end turn per reachable provider**

- [ ] **Step 5: Capture screenshots and browser console evidence; do not write secrets to artifacts**
