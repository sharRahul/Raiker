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

- [x] **Step 1: Write failing API/turn tests**

```python
def test_prompt_rejects_effort_not_declared_by_the_resolved_profile(): ...
def test_prompt_binds_declared_effort_to_the_provider_request(): ...
def test_models_view_exposes_declared_reasoning_effort_values(): ...
```

- [x] **Step 2: Run the focused tests to verify red**

Run: `python -m pytest --basetemp=F:\GitHub\Raiker\output\pytest-model-effort tests/test_api_prompts.py tests/test_api_web_read_models.py tests/test_turn_model_binding.py -q`

- [x] **Step 3: Implement the minimum validated contract and propagation**

```python
if options.reasoning_effort and options.reasoning_effort not in capabilities.reasoning_effort_values:
    raise ContractValidationError("invalid_reasoning_effort")
```

- [x] **Step 4: Run the focused tests to verify green**

- [x] **Step 5: Commit the backend slice**

### Task 2: Render Chat's local right rail and capability-driven composer controls

**Files:**
- Modify: `apps/web/src/lib/apiTypes.ts`, `apps/web/src/lib/api.ts`, `apps/web/src/lib/views/ChatView.svelte`, `apps/web/src/lib/views/BuildView.svelte`
- Test: `apps/web/src/lib/views/ChatView.composerParity.test.ts`, `apps/web/src/lib/views/BuildView.test.ts`

**Interfaces:**
- Consumes `/api/models` reasoning capability fields and the optional `reasoning_effort` prompt body field from Task 1.
- Produces a per-turn model/effort request without calling `api.selectModel`.

- [x] **Step 1: Write failing layout and picker tests**

```ts
it("places Chat background work in its own desktop rail, not below the composer", () => { ... });
it("shows only the selected model's declared thinking efforts", () => { ... });
it("omits thinking effort when the selected model does not support it", () => { ... });
```

- [x] **Step 2: Run focused Vitest to verify red**

Run: `npm.cmd --prefix apps/web run test -- ChatView BuildView`

- [x] **Step 3: Implement the responsive Chat grid and picker**

```svelte
{#if activeProfile?.supports_reasoning_effort}
  <select bind:value={reasoningEffort} aria-label="Thinking effort">...</select>
{/if}
```

- [x] **Step 4: Run focused Vitest and `svelte-check` to verify green**

- [x] **Step 5: Commit the UI slice**

### Task 3: Verify the built app and live providers

**Files:**
- Test only; no source changes unless a failing test identifies a defect.

- [x] **Step 1: Run full web tests and build**

Run: `npm.cmd --prefix apps/web run test; npm.cmd --prefix apps/web run check; npm.cmd --prefix apps/web run build`

- [x] **Step 2: Run focused Python model-effort tests**

- [x] **Step 3: Start an isolated loopback `raiker-web` process with process-scoped provider credentials**

- [x] **Step 4: Use Playwright to select Ollama, Anthropic, and OpenRouter models; exercise an effort picker only where that exact model advertises it, and run one authenticated end-to-end turn per reachable provider**

- [x] **Step 5: Capture screenshots and browser console evidence; do not write secrets to artifacts**

## Verification Record — 2026-07-28

### Automated checks

- Python model/effort contract suite: 69 passed (`test_api_prompts`, `test_api_web_read_models`, `test_turn_model_binding`, `test_turn_resume_after_approval`, and `test_model_router`).
- Web views after the provider-catalogue repair: 69 passed across `ModelsView`, `ChatView`, and `BuildView`.
- `svelte-check`: 0 errors, 0 warnings.
- Production web build: passed.

### Live provider matrix

| Provider | Selected model | Turn result | Thinking effort control | Screenshot |
| --- | --- | --- | --- | --- |
| Ollama | `gemma4:31b-cloud` | `OLLAMA_MATRIX_OK` | Hidden: the resolved profile declares no effort values. | `.playwright-cli/page-2026-07-28T09-21-08-643Z.png` |
| Anthropic | `claude-haiku-4-5-20251001` | `ANTHROPIC_MATRIX_OK` | Hidden: the resolved profile declares no effort values. | `.playwright-cli/page-2026-07-28T09-29-05-754Z.png` |
| OpenRouter | `inclusionai/ling-3.0-flash:free` | `OPENROUTER_MATRIX_OK` | Hidden: the resolved profile declares no effort values. | `.playwright-cli/page-2026-07-28T09-45-06-954Z.png` |

The composer only renders a thinking-effort selector when the exact selected profile advertises `supports_reasoning_effort` and one or more declared values. This prevents the UI from implying unsupported controls for these three live selections.

### OpenRouter catalogue regression

The live OpenRouter catalogue returned duplicate model IDs. The picker previously keyed each option by its ID, causing Svelte's `each_key_duplicate` exception even though the provider request returned HTTP 200. The picker now performs a stable de-duplication at its shared input boundary, preserving first-seen order and leaving unavailable/error responses unchanged. A focused regression test covers the case; the repaired live run completed with no browser console errors.
