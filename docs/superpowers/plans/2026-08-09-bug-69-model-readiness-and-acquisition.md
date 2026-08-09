# BUG-69 Model Readiness and Acquisition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make exact provider/model readiness authoritative across Raiker, guide first-run setup, discover and deploy local GGUF models, and acquire or safely convert Hugging Face models.

**Architecture:** A server-owned readiness service persists short-lived, exact provider/model observations and guards every model-backed API. Focused local-operation, model-library, Hugging Face, and conversion services feed the same readiness boundary; shared Svelte components project it consistently across all work surfaces and the Models onboarding UI.

**Tech Stack:** Python 3.11+, FastAPI, SQLite/SQLCipher, httpx, `huggingface_hub>=1.25,<2`, Svelte 5, TypeScript, Vitest, Testing Library, Playwright CLI, llama.cpp/Ollama/LM Studio command and loopback APIs.

## Global Constraints

- Exact readiness, not a configured model name, controls Workbench, Chat, Build, Tasks, Schedule, and background-agent submission.
- Preserve the owner-authoritative, monitored, fail-closed posture in `docs/SECURITY_AND_POLICY.md`.
- Never silently install software, download weights, accept licences, move/copy models, execute repository code, enable `trust_remote_code`, or fall back to a hosted provider.
- Do not redistribute LM Studio. Ollama installation retrieves the official installer at runtime only after explicit owner consent.
- Scan only provider inventories and owner-approved roots; never scan a whole drive, home directory, workspace, backup root, or network share by default.
- Treat model weights and repository files as untrusted data. Conversion runs no-network with no workspace or vault access and accepts Safetensors, not pickle weights.
- Hugging Face downloads are exact-revision, dry-run-first, resumable, and licence/source preserving; gated terms remain a browser action for the owner.
- Credentials supplied for live tests are entered only through the UI and never written to source, fixtures, logs, screenshots, shell history artifacts, or commits.
- Preserve current responsive breakpoints, semantic theme tokens, keyboard behavior, and WCAG AA contrast.
- Use test-driven development: observe every new behavioral test fail for the intended reason before writing production code.

## File structure

- `raiker/models/readiness.py`: readiness states, probe protocol, exact-key cache, invalidation, and submission guard.
- `raiker/models/local_operations.py`: human-only durable install/download/import/conversion job lifecycle.
- `raiker/models/runtime_installers.py`: reviewed Ollama, LM Studio/llmster, and llama.cpp install plans and execution adapters.
- `raiker/models/library.py`: approved roots, provider inventory adapters, bounded GGUF metadata indexing, and deployment records.
- `raiker/models/gguf.py`: bounded pure-Python GGUF header reader and shard/projector grouping.
- `raiker/models/local_runtime.py`: managed loopback llama.cpp lifecycle and exact-model health.
- `raiker/models/huggingface.py`: Hub search, repository/variant metadata, dry-run and revision-pinned downloads.
- `raiker/models/conversion.py`: pinned llama.cpp conversion/quantization plan and isolated worker invocation.
- `raiker/api/routes_models.py`: focused readiness, setup, operation, library, Hugging Face, and conversion API.
- `apps/web/src/lib/modelReadiness.svelte.ts`: shared reactive readiness and setup-dialog state.
- `apps/web/src/lib/components/ModelReadinessStrip.svelte`: inline cross-surface disabled-state explanation.
- `apps/web/src/lib/components/ModelSetupDialog.svelte`: shared setup/repair modal.
- `apps/web/src/lib/components/ModelOperationTray.svelte`: persistent long-operation progress.
- `apps/web/src/lib/views/ModelSetupView.svelte`: resumable first-owner setup flow.
- `apps/web/src/lib/views/models/ProvidersPanel.svelte`: provider readiness and install/connect actions.
- `apps/web/src/lib/views/models/LocalLibraryPanel.svelte`: sources, discovered models, and deployment review.
- `apps/web/src/lib/views/models/HuggingFacePanel.svelte`: search, variant comparison, download and conversion review.
- `apps/web/src/lib/views/models/DownloadsPanel.svelte`: durable job history and cleanup controls.
- `apps/web/src/lib/views/models/ExistingModelsPanel.svelte`: unchanged Routing, Pricing, and Posture content extracted from the current Models view.

---

### Task 1: Exact readiness domain and persistence

**Files:**
- Create: `raiker/models/readiness.py`
- Modify: `raiker/storage/migrations.py`
- Modify: `raiker/storage/sqlite.py`
- Test: `tests/test_model_readiness.py`

**Interfaces:**
- Produces: `ModelReadinessState`, `ModelReadinessKey`, `ModelReadiness`, `ModelProbe`, and `ModelReadinessService`.
- Produces: `SQLiteStore.save_model_readiness()`, `load_model_readiness()`, `invalidate_model_readiness()`, and `list_model_readiness()`.

- [ ] **Step 1: Write failing state, storage, freshness, and invalidation tests**

```python
def test_ready_is_exact_to_owner_profile_model_and_endpoint(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    service = ModelReadinessService(store, probe=AnsweringProbe())
    ready = asyncio.run(service.check("owner-a", "ollama-local-openai-compatible", "gemma4:31b-cloud", "endpoint-a"))
    assert ready.state is ModelReadinessState.READY
    assert service.current("owner-a", "ollama-local-openai-compatible", "other", "endpoint-a").state is ModelReadinessState.NOT_CONFIGURED
    service.invalidate_profile("owner-a", "ollama-local-openai-compatible", reason_code="connection_changed")
    assert service.current("owner-a", "ollama-local-openai-compatible", "gemma4:31b-cloud", "endpoint-a").state is ModelReadinessState.STALE
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python -m pytest tests/test_model_readiness.py -q`
Expected: collection fails because `raiker.models.readiness` does not exist.

- [ ] **Step 3: Add migration `RAIKER-1042-model-readiness` and minimal domain/service**

```python
class ModelReadinessState(StrEnum):
    NOT_CONFIGURED = "not_configured"
    CHECKING = "checking"
    READY = "ready"
    RUNTIME_MISSING = "runtime_missing"
    RUNTIME_STOPPED = "runtime_stopped"
    MODEL_MISSING = "model_missing"
    POLICY_BLOCKED = "policy_blocked"
    AUTHENTICATION_FAILED = "authentication_failed"
    UNREACHABLE = "unreachable"
    UNSUPPORTED = "unsupported"
    STALE = "stale"

@dataclass(frozen=True)
class ModelReadinessKey:
    owner_principal_id: str
    profile_id: str
    model: str
    endpoint_fingerprint: str

@dataclass(frozen=True)
class ModelReadiness:
    key: ModelReadinessKey
    state: ModelReadinessState
    checked_at: str | None
    expires_at: str | None
    summary: str
    reason_code: str
    remediation: str
    evidence: dict[str, object]

class ModelProbe(Protocol):
    async def check(self, key: ModelReadinessKey) -> ModelReadiness:
        raise NotImplementedError
```

Persist only redacted evidence JSON. Add unique key `(owner_principal_id, profile_id, model, endpoint_fingerprint)` and indexes for owner/profile and expiry.

- [ ] **Step 4: Verify GREEN and migration compatibility**

Run: `python -m pytest tests/test_model_readiness.py tests/test_storage_migrations.py -q`
Expected: all pass; legacy workspaces migrate without a readiness row.

- [ ] **Step 5: Commit**

```bash
git add raiker/models/readiness.py raiker/storage/migrations.py raiker/storage/sqlite.py tests/test_model_readiness.py
git commit -m "feat: add exact model readiness state"
```

### Task 2: Provider probes, Models projection, and readiness API

**Files:**
- Modify: `raiker/models/readiness.py`
- Modify: `raiker/control/dashboard.py`
- Modify: `raiker/api/schemas.py`
- Create: `raiker/api/routes_models.py`
- Modify: `apps/api/main.py`
- Test: `tests/test_api_model_readiness.py`
- Test: `tests/test_api_dashboard.py`
- Test: `tests/test_api_model_selection.py`

**Interfaces:**
- Consumes: Task 1 `ModelReadinessService`.
- Produces: `GET /api/model-readiness`, `POST /api/model-readiness/check`, and readiness fields on `ModelProfileView`.
- Produces: `ModelReadinessService.require_ready(owner, profile_id, model) -> ModelReadiness`.

- [ ] **Step 1: Write failing API and configured-versus-ready tests**

```python
def test_native_default_is_preferred_but_not_ready(client: TestClient, owner_token: str) -> None:
    body = client.get("/api/models", headers=_auth(owner_token)).json()
    ollama = next(p for p in body["profiles"] if p["profile_id"] == "ollama-local-openai-compatible")
    assert ollama["selected"] is True
    assert ollama["readiness_state"] in {"runtime_missing", "runtime_stopped", "model_missing", "unreachable"}
    assert body["ready_provider_count"] == 0

def test_check_returns_plain_language_exact_model_result(client: TestClient, owner_token: str) -> None:
    response = client.post("/api/model-readiness/check", json={"profile_id": "ollama-local-openai-compatible", "model": "missing"}, headers=_auth(owner_token))
    assert response.status_code == 200
    assert response.json()["reason_code"] == "local_model_missing"
    assert "Ollama" in response.json()["summary"]
```

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest tests/test_api_model_readiness.py tests/test_api_dashboard.py::TestDashboardAPI::test_models -q`
Expected: readiness endpoints and response fields are missing.

- [ ] **Step 3: Implement provider-aware probing and API serialization**

Use provider catalogue/health calls already exposed by `ModelRouter.alist_models_for_profile()`. Normalize exceptions without provider response bodies. Add these exact fields to `ModelProfileView`: `readiness_state`, `readiness_summary`, `readiness_reason_code`, `readiness_checked_at`, `readiness_expires_at`, `readiness_remediation`, and `ready`. Add `ready_provider_count` to `ModelsView`.

```python
class ModelReadinessCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())
    profile_id: str
    model: str

@router.post("/api/model-readiness/check")
async def check_model_readiness(body: ModelReadinessCheckRequest, request: Request, auth_data=Depends(_auth)) -> dict[str, Any]:
    return (await _readiness(request).check_selected(auth_data[0].principal_id, body.profile_id, body.model)).to_dict()
```

Invalidate readiness after connection, model-selection, pull/import, endpoint, or credential changes. Do not make a billable inference request.

- [ ] **Step 4: Verify GREEN plus provider exception mapping**

Run: `python -m pytest tests/test_api_model_readiness.py tests/test_api_dashboard.py tests/test_api_model_selection.py -q`
Expected: all pass; `provider_error_unclassified` never appears in API summaries.

- [ ] **Step 5: Commit**

```bash
git add raiker/models/readiness.py raiker/control/dashboard.py raiker/api/schemas.py raiker/api/routes_models.py apps/api/main.py tests/test_api_model_readiness.py tests/test_api_dashboard.py tests/test_api_model_selection.py
git commit -m "fix: make model readiness honest"
```

### Task 3: Guard every model-backed server submission

**Files:**
- Modify: `raiker/api/routes_prompts.py`
- Modify: `raiker/api/routes_dashboard.py`
- Modify: `raiker/runtime/orchestrator.py`
- Test: `tests/test_model_readiness_guards.py`
- Test: `tests/test_api_prompts.py`
- Test: `tests/test_api_dashboard.py`

**Interfaces:**
- Consumes: `ModelReadinessService.require_ready()`.
- Produces: structured HTTP/SSE refusal `{reason_code: "model_not_ready", readiness: {state, summary, remediation, reason_code}}`.

- [ ] **Step 1: Write failing Chat, Build-stream, Task, Schedule, and background tests**

```python
@pytest.mark.parametrize("path,payload", [
    ("/api/prompts", {"text": "hello", "model_profile": "ollama-local-openai-compatible", "model": "gemma4:31b-cloud"}),
    ("/api/tasks", {"title": "Run now", "description": "Do work", "model_profile": "ollama-local-openai-compatible", "model": "gemma4:31b-cloud"}),
    ("/api/tasks", {"title": "Run later", "description": "Do work", "scheduled_at": "2030-01-01T00:00:00Z", "model_profile": "ollama-local-openai-compatible", "model": "gemma4:31b-cloud"}),
])
def test_unready_model_creates_no_work(client, owner_token, path, payload):
    response = client.post(path, json=payload, headers=_auth(owner_token))
    assert response.status_code == 409
    assert response.json()["detail"]["reason_code"] == "model_not_ready"
```

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest tests/test_model_readiness_guards.py -q`
Expected: requests create a turn/task or fail later at the provider.

- [ ] **Step 3: Add one guard before envelope/task creation and recheck at runtime**

```python
def require_model_ready(workspace: Path, owner_principal_id: str, profile_id: str, model: str) -> ModelReadiness:
    readiness = ModelReadinessService(SQLiteStore(workspace)).require_ready(owner_principal_id, profile_id, model)
    if readiness.state is not ModelReadinessState.READY:
        raise ModelNotReady(readiness)
    return readiness
```

Resolve omitted profile/model through the same principal model selection used by the gateway. A task without executable instructions remains a non-agent draft; any task/schedule/background run with an objective must be ready. Convert stream refusal into one final SSE event without creating a session/turn.

- [ ] **Step 4: Verify GREEN and no durable side effects**

Run: `python -m pytest tests/test_model_readiness_guards.py tests/test_api_prompts.py tests/test_api_dashboard.py -q`
Expected: all pass and rejected requests add no turn, task, attachment reference, or model usage row.

- [ ] **Step 5: Commit**

```bash
git add raiker/api/routes_prompts.py raiker/api/routes_dashboard.py raiker/runtime/orchestrator.py tests/test_model_readiness_guards.py tests/test_api_prompts.py tests/test_api_dashboard.py
git commit -m "fix: guard all model backed work"
```

### Task 4: Shared web readiness state, picker, strip, and setup dialog

**Files:**
- Modify: `apps/web/src/lib/apiTypes.ts`
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/lib/models.svelte.ts`
- Create: `apps/web/src/lib/modelReadiness.svelte.ts`
- Modify: `apps/web/src/lib/components/ModelPicker.svelte`
- Create: `apps/web/src/lib/components/ModelReadinessStrip.svelte`
- Create: `apps/web/src/lib/components/ModelSetupDialog.svelte`
- Modify: `apps/web/src/App.svelte`
- Test: `apps/web/src/lib/components/ModelPicker.test.ts`
- Test: `apps/web/src/lib/components/ModelReadinessStrip.test.ts`
- Test: `apps/web/src/lib/components/ModelSetupDialog.test.ts`

**Interfaces:**
- Produces: `readyProfiles()`, `selectedModelReadiness()`, `openModelSetup()`, and `refreshModelReadiness()`.
- Produces: component props `readiness: ModelReadinessView | null`, `draftPreserved?: boolean`, and `onRetry?: () => Promise<void>`.

- [ ] **Step 1: Write failing component behavior tests**

```ts
it("groups runnable choices and repair actions without selecting an unready model", async () => {
  render(ModelPicker, { profiles: [readyProfile, stoppedProfile], selectedProfile: stoppedProfile });
  await fireEvent.click(screen.getByRole("button", { name: /Model for this turn/ }));
  expect(screen.getByText("Ready")).toBeInTheDocument();
  expect(screen.getByText("Needs setup")).toBeInTheDocument();
  await fireEvent.click(screen.getByRole("button", { name: /Set up Ollama/ }));
  expect(screen.getByRole("dialog", { name: "Set up a model to continue" })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run and verify RED**

Run: `npm --prefix apps/web test -- ModelPicker.test.ts ModelReadinessStrip.test.ts ModelSetupDialog.test.ts`
Expected: new modules/components and readiness fields are missing.

- [ ] **Step 3: Implement shared reactive state and accessible components**

Add TypeScript unions matching Task 1 states. Keep all profiles in the shared store. `chatProfiles()` remains for compatibility, while `readyProfiles()` filters `profile.ready === true`. The strip emits no navigation by itself; the dialog primary action sets `window.location.hash = "#/models"`. The dialog traps focus, returns focus to its trigger, exposes technical details collapsed, and announces retry state.

```ts
export function readyProfiles(): ModelProfile[] {
  return chatProfiles().filter((profile) => profile.ready === true);
}

export function selectedModelReadiness(): ModelProfile | null {
  return allProfiles().find((profile) => profile.selected) ?? null;
}

export function openModelSetup(profile: ModelProfile | null): void {
  setupDialog.profile = profile;
  setupDialog.open = true;
}
```

Mount one `ModelSetupDialog` in `App.svelte`; `ModelPicker` repair buttons update the shared dialog state instead of creating nested dialogs.

- [ ] **Step 4: Verify GREEN, types, and accessibility assertions**

Run: `npm --prefix apps/web test -- ModelPicker.test.ts ModelReadinessStrip.test.ts ModelSetupDialog.test.ts && npm --prefix apps/web run check`
Expected: all pass without Svelte accessibility warnings.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/lib/apiTypes.ts apps/web/src/lib/api.ts apps/web/src/lib/models.svelte.ts apps/web/src/lib/modelReadiness.svelte.ts apps/web/src/lib/components/ModelPicker.svelte apps/web/src/lib/components/ModelPicker.test.ts apps/web/src/lib/components/ModelReadinessStrip.svelte apps/web/src/lib/components/ModelReadinessStrip.test.ts apps/web/src/lib/components/ModelSetupDialog.svelte apps/web/src/lib/components/ModelSetupDialog.test.ts apps/web/src/App.svelte
git commit -m "feat: add shared model readiness controls"
```

### Task 5: Apply readiness UI to Workbench, Chat, Build, Tasks, and schedules

**Files:**
- Modify: `apps/web/src/lib/views/WorkbenchView.svelte`
- Modify: `apps/web/src/lib/views/ChatView.svelte`
- Modify: `apps/web/src/lib/views/BuildView.svelte`
- Modify: `apps/web/src/lib/views/TasksView.svelte`
- Test: `apps/web/src/lib/views/WorkbenchView.test.ts`
- Test: `apps/web/src/lib/views/ChatView.test.ts`
- Test: `apps/web/src/lib/views/BuildView.test.ts`
- Test: `apps/web/src/lib/views/TasksView.test.ts`

**Interfaces:**
- Consumes: Task 4 shared store/components.
- Produces: identical disabled-state and draft-preservation behavior on every surface.

- [ ] **Step 1: Write one failing readiness scenario per surface**

```ts
it.each(["Chat", "Build", "Create task", "Schedule"])("preserves the %s draft when no model is ready", async (mode) => {
  render(WorkbenchView);
  await chooseMode(mode);
  await fireEvent.input(screen.getByRole("textbox"), { target: { value: "keep this draft" } });
  expect(screen.getByRole("button", { name: /Start|Create|Review/ })).toBeDisabled();
  expect(screen.getByText("No model is ready")).toBeInTheDocument();
  expect(screen.getByRole("textbox")).toHaveValue("keep this draft");
});
```

- [ ] **Step 2: Run and verify RED**

Run: `npm --prefix apps/web test -- WorkbenchView.test.ts ChatView.test.ts BuildView.test.ts TasksView.test.ts`
Expected: actions remain enabled or no readiness strip appears.

- [ ] **Step 3: Integrate one computed `canSubmit` rule and shared repair UI**

Use `effectiveModel?.ready === true && !uploading && !streaming` in each surface. Preserve existing upload, stop/steer, repository, schedule-time, and approval constraints by combining them rather than replacing them. Handle a server `model_not_ready` response by refreshing readiness and opening the shared dialog without clearing draft/attachments.

```svelte
{@const modelReady = effectiveModel?.ready === true}
{#if !modelReady}
  <ModelReadinessStrip readiness={effectiveModel ?? null} onSetup={() => openModelSetup(effectiveModel ?? null)} />
{/if}
<button type="submit" disabled={!modelReady || uploading || streaming}>{primaryLabel}</button>
```

- [ ] **Step 4: Verify GREEN and composer parity**

Run: `npm --prefix apps/web test -- WorkbenchView.test.ts ChatView.test.ts ChatView.composerParity.test.ts BuildView.test.ts TasksView.test.ts`
Expected: all pass for ready and unready profiles.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/lib/views/WorkbenchView.svelte apps/web/src/lib/views/WorkbenchView.test.ts apps/web/src/lib/views/ChatView.svelte apps/web/src/lib/views/ChatView.test.ts apps/web/src/lib/views/BuildView.svelte apps/web/src/lib/views/BuildView.test.ts apps/web/src/lib/views/TasksView.svelte apps/web/src/lib/views/TasksView.test.ts
git commit -m "fix: disable work until a model is ready"
```

### Task 6: Resumable first-owner setup flow

**Files:**
- Modify: `raiker/storage/migrations.py`
- Modify: `raiker/storage/sqlite.py`
- Modify: `raiker/api/schemas.py`
- Modify: `raiker/api/routes_models.py`
- Create: `apps/web/src/lib/views/ModelSetupView.svelte`
- Modify: `apps/web/src/App.svelte`
- Modify: `apps/web/src/lib/nav.ts`
- Test: `tests/test_model_setup_state.py`
- Test: `apps/web/src/lib/views/ModelSetupView.test.ts`
- Test: `apps/web/src/App.test.ts`

**Interfaces:**
- Produces: `GET /api/model-setup`, `PUT /api/model-setup`, `ModelSetupState(step, status, path, selected_profile_id, selected_model)`.
- Consumes: Tasks 2 and 4 readiness APIs/components.

- [ ] **Step 1: Write failing first-owner, skip, resume, and existing-owner tests**

```python
def test_first_owner_starts_setup_and_skip_is_resumable(client, registered_owner_headers):
    state = client.get("/api/model-setup", headers=registered_owner_headers).json()
    assert state["status"] == "required"
    skipped = client.put("/api/model-setup", json={"status": "skipped", "step": "choose_path"}, headers=registered_owner_headers).json()
    assert skipped["status"] == "skipped"
    assert client.get("/api/model-setup", headers=registered_owner_headers).json()["step"] == "choose_path"
```

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest tests/test_model_setup_state.py -q && npm --prefix apps/web test -- ModelSetupView.test.ts App.test.ts`
Expected: setup API/view are missing.

- [ ] **Step 3: Add migration `RAIKER-1043-model-setup-state` and five-screen view**

Persist per owner: `status` (`required|in_progress|skipped|complete`), `step`, `path`, selected pair, and timestamps. `App.svelte` routes a newly registered owner with no ready model to `#/model-setup`; ordinary login respects the saved route. The view implements Choose how / Provider / Model / Review / Ready and uses the same provider, library, and operation components added in later tasks through stable slots.

```python
@dataclass(frozen=True)
class ModelSetupState:
    owner_principal_id: str
    status: str
    step: str
    path: str | None
    selected_profile_id: str | None
    selected_model: str | None

class ModelSetupUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())
    status: Literal["required", "in_progress", "skipped", "complete"]
    step: str
    path: str | None = None
    selected_profile_id: str | None = None
    selected_model: str | None = None

@router.put("/api/model-setup")
async def update_model_setup(body: ModelSetupUpdateRequest, request: Request, auth_data=Depends(_auth)) -> dict[str, Any]:
    return _setup(request).update(auth_data[0].principal_id, body).to_dict()
```

- [ ] **Step 4: Verify GREEN and navigation behavior**

Run: `python -m pytest tests/test_model_setup_state.py -q && npm --prefix apps/web test -- ModelSetupView.test.ts App.test.ts nav.test.ts`
Expected: all pass; Skip explains disabled model-backed controls.

- [ ] **Step 5: Commit**

```bash
git add raiker/storage/migrations.py raiker/storage/sqlite.py raiker/api/schemas.py raiker/api/routes_models.py apps/web/src/lib/views/ModelSetupView.svelte apps/web/src/App.svelte apps/web/src/lib/nav.ts tests/test_model_setup_state.py apps/web/src/lib/views/ModelSetupView.test.ts apps/web/src/App.test.ts
git commit -m "feat: add resumable model setup"
```

### Task 7: Durable owner-controlled local operations and runtime installers

**Files:**
- Create: `raiker/models/local_operations.py`
- Create: `raiker/models/runtime_installers.py`
- Modify: `raiker/storage/migrations.py`
- Modify: `raiker/storage/sqlite.py`
- Modify: `raiker/api/schemas.py`
- Modify: `raiker/api/routes_models.py`
- Test: `tests/test_model_local_operations.py`
- Test: `tests/test_runtime_installers.py`
- Test: `tests/test_api_model_operations.py`

**Interfaces:**
- Produces: `ModelOperationService.preview/start/cancel/retry/cleanup/list`.
- Produces: `InstallPlan(runtime, source_url, argv, requires_elevation, terms_url, redistribution)`.
- Produces: `/api/model-operations` read/start/cancel/retry/cleanup endpoints.

- [ ] **Step 1: Write failing authorization, source, lifecycle, and restart tests**

```python
def test_lm_studio_desktop_is_never_downloaded_or_redistributed(tmp_path: Path) -> None:
    plan = RuntimeInstallerRegistry().preview("lm-studio-desktop", platform="windows")
    assert plan.redistribution is False
    assert plan.action == "open_vendor_download"
    assert plan.source_url.startswith("https://lmstudio.ai/")

def test_agent_principal_cannot_start_install(client, machine_headers):
    response = client.post("/api/model-operations", json={"kind": "install", "target": "ollama", "confirmed": True}, headers=machine_headers)
    assert response.status_code == 403
    assert response.json()["detail"]["reason_code"] == "human_principal_required"
```

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest tests/test_model_local_operations.py tests/test_runtime_installers.py tests/test_api_model_operations.py -q`
Expected: modules/endpoints are missing.

- [ ] **Step 3: Add migration `RAIKER-1044-model-operations` and reviewed adapters**

The job state is `queued|running|waiting_for_owner|cancel_requested|cancelled|failed|complete`; store phase, progress bytes/percent, redacted source/destination, bounded error, timestamps, and owner. Ollama uses official HTTPS installer/download endpoints and verifies available signature/checksum. LM Studio desktop returns an open-vendor action; llmster invokes only the official published installer after confirmation. llama.cpp uses official releases or a supported package manager. Never pass tokens on argv.

```python
@dataclass(frozen=True)
class InstallPlan:
    runtime: str
    action: str
    source_url: str
    argv: tuple[str, ...]
    requires_elevation: bool
    terms_url: str
    redistribution: bool

class ModelOperationService:
    def start(self, owner_principal_id: str, request: ModelOperationRequest) -> ModelOperation:
        operation = ModelOperation.queued(owner_principal_id, request)
        self.store.save_model_operation(operation)
        self.runner.submit(operation.operation_id)
        return operation

    def cancel(self, owner_principal_id: str, operation_id: str) -> ModelOperation:
        operation = self.store.require_model_operation(owner_principal_id, operation_id)
        cancelled = replace(operation, state="cancel_requested")
        self.store.save_model_operation(cancelled)
        return cancelled
```

- [ ] **Step 4: Verify GREEN, redaction, and abandoned-job recovery**

Run: `python -m pytest tests/test_model_local_operations.py tests/test_runtime_installers.py tests/test_api_model_operations.py tests/test_api_security.py -q`
Expected: all pass; restart marks unowned child processes failed and resumable downloads queued only when supported.

- [ ] **Step 5: Commit**

```bash
git add raiker/models/local_operations.py raiker/models/runtime_installers.py raiker/storage/migrations.py raiker/storage/sqlite.py raiker/api/schemas.py raiker/api/routes_models.py tests/test_model_local_operations.py tests/test_runtime_installers.py tests/test_api_model_operations.py
git commit -m "feat: add governed model operations"
```

### Task 8: Approved local libraries, bounded GGUF indexing, and llama.cpp deployment

**Files:**
- Create: `raiker/models/gguf.py`
- Create: `raiker/models/library.py`
- Create: `raiker/models/local_runtime.py`
- Modify: `raiker/storage/migrations.py`
- Modify: `raiker/storage/sqlite.py`
- Modify: `raiker/api/routes_models.py`
- Test: `tests/test_gguf_metadata.py`
- Test: `tests/test_model_library.py`
- Test: `tests/test_managed_llama_runtime.py`
- Test: `tests/test_api_model_library.py`

**Interfaces:**
- Produces: `read_gguf_metadata(path, max_header_bytes=8_388_608) -> GgufMetadata`.
- Produces: `ModelLibraryService.add_root/rescan/remove_root/list_models/deploy`.
- Produces: `ManagedLlamaRuntime.start/stop/status` and exact readiness invalidation.

- [ ] **Step 1: Write failing bounded-header, approved-root, shard, symlink, and lifecycle tests**

```python
def test_scan_never_follows_symlink_outside_approved_root(tmp_path: Path) -> None:
    root = tmp_path / "approved"
    outside = tmp_path / "private"
    root.mkdir(); outside.mkdir()
    make_minimal_gguf(outside / "secret.gguf", name="secret")
    (root / "escape").symlink_to(outside, target_is_directory=True)
    models = ModelLibraryService(SQLiteStore(tmp_path)).scan_root("owner", root)
    assert models == []
```

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest tests/test_gguf_metadata.py tests/test_model_library.py tests/test_managed_llama_runtime.py tests/test_api_model_library.py -q`
Expected: library/parser/runtime modules are missing.

- [ ] **Step 3: Add migration `RAIKER-1045-model-library` and minimal adapters**

Read GGUF magic/version/KV metadata without tensor bytes; reject absurd lengths before allocation. Group `*-00001-of-N.gguf` shards and `mmproj*.gguf`. Store encrypted canonical path, bounded fingerprint, source, metadata, validation, and deployment. Inventory adapters use Ollama `/api/tags`, `lms ls --json`/REST, documented caches, and owner-approved folders. Managed llama.cpp binds `127.0.0.1` on a free port, launches an explicit file or `--models-dir`, captures bounded logs, and marks ready only after `/health` plus exact catalogue confirmation.

```python
@dataclass(frozen=True)
class GgufMetadata:
    name: str | None
    architecture: str | None
    parameter_count: int | None
    quantization: str | None
    context_length: int | None
    source_url: str | None
    license_id: str | None

def read_gguf_metadata(path: Path, *, max_header_bytes: int = 8_388_608) -> GgufMetadata:
    with path.open("rb") as stream:
        if stream.read(4) != b"GGUF":
            raise GgufValidationError("gguf_magic_invalid")
        version = read_u32(stream)
        if version not in {2, 3}:
            raise GgufValidationError("gguf_version_unsupported")
        return read_bounded_metadata(stream, max_header_bytes=max_header_bytes)
```

- [ ] **Step 4: Verify GREEN including runtime crash invalidation**

Run: `python -m pytest tests/test_gguf_metadata.py tests/test_model_library.py tests/test_managed_llama_runtime.py tests/test_api_model_library.py -q`
Expected: all pass; original files are unchanged and a stopped process invalidates readiness.

- [ ] **Step 5: Commit**

```bash
git add raiker/models/gguf.py raiker/models/library.py raiker/models/local_runtime.py raiker/storage/migrations.py raiker/storage/sqlite.py raiker/api/routes_models.py tests/test_gguf_metadata.py tests/test_model_library.py tests/test_managed_llama_runtime.py tests/test_api_model_library.py
git commit -m "feat: discover and deploy local gguf models"
```

### Task 9: Hugging Face catalogue and revision-pinned GGUF downloads

**Files:**
- Modify: `pyproject.toml`
- Create: `raiker/models/huggingface.py`
- Modify: `raiker/api/schemas.py`
- Modify: `raiker/api/routes_models.py`
- Test: `tests/test_huggingface_models.py`
- Test: `tests/test_api_huggingface_models.py`
- Test: `tests/test_credential_security.py`

**Interfaces:**
- Produces: `HuggingFaceService.search/repository/variants/dry_run/download`.
- Produces: `HfVariant(revision, files, quantization, total_bytes, cached_bytes, gated, license_id, complete)`.
- Consumes: Task 7 operation jobs and Task 8 library registration.

- [ ] **Step 1: Write failing variant, dry-run, gated, revision, and token-redaction tests**

```python
def test_existing_complete_gguf_is_preferred_and_revision_pinned(fake_hub, tmp_path: Path) -> None:
    service = HuggingFaceService(fake_hub, cache_dir=tmp_path / "hf")
    variants = service.variants("owner/repo", revision="a" * 40)
    assert variants[0].format == "gguf"
    assert variants[0].complete is True
    assert variants[0].revision == "a" * 40
    assert variants[0].quantization == "Q4_K_M"
```

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest tests/test_huggingface_models.py tests/test_api_huggingface_models.py -q`
Expected: service/API do not exist.

- [ ] **Step 3: Add official Hub client and owner-scoped API**

Add `huggingface_hub>=1.25,<2` to project dependencies. Use `HfApi` for metadata and `snapshot_download` with the full revision, selected-file patterns, and `dry_run=True` before starting a Task 7 job. Prefer complete GGUF variants; identify shard completeness from filenames. Store the token in the existing vault and pass it as an in-memory argument only. Gated access returns `gated_access_required` with the official repository URL.

```python
dry_run = snapshot_download(
    repo_id=repo_id,
    revision=full_commit_sha,
    allow_patterns=list(selected_files),
    token=token,
    dry_run=True,
)
return HfDownloadPreview.from_dry_run(repo_id, full_commit_sha, dry_run)
```

- [ ] **Step 4: Verify GREEN, cache reuse, and secret scan**

Run: `python -m pytest tests/test_huggingface_models.py tests/test_api_huggingface_models.py tests/test_credential_security.py -q`
Expected: all pass; token never appears in jobs, argv, exceptions, or API JSON.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml raiker/models/huggingface.py raiker/api/schemas.py raiker/api/routes_models.py tests/test_huggingface_models.py tests/test_api_huggingface_models.py tests/test_credential_security.py
git commit -m "feat: download hugging face gguf models"
```

### Task 10: Isolated Safetensors-to-GGUF conversion and quantization

**Files:**
- Create: `raiker/models/conversion.py`
- Modify: `raiker/models/local_operations.py`
- Modify: `raiker/api/routes_models.py`
- Test: `tests/test_model_conversion.py`
- Test: `tests/test_model_conversion_isolation.py`
- Test: `tests/test_api_model_conversion.py`

**Interfaces:**
- Produces: `ConversionPlan(source_revision, source_files, architecture, intermediate, quantization, output, required_bytes)`.
- Produces: `ModelConversionService.preview/start/cancel/cleanup`.
- Consumes: Task 9 immutable source snapshot and Task 8 deployment.

- [ ] **Step 1: Write failing supported/unsupported, no-code, no-network, and disk tests**

```python
def test_conversion_rejects_repository_code_and_pickle_weights(tmp_path: Path) -> None:
    repo = tmp_path / "snapshot"; repo.mkdir()
    (repo / "modeling_custom.py").write_text("raise RuntimeError('must not run')")
    (repo / "pytorch_model.bin").write_bytes(b"pickle")
    with pytest.raises(ConversionRefused, match="safetensors_required"):
        ModelConversionService(toolchain=fake_toolchain()).preview(repo, "Q4_K_M")
```

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest tests/test_model_conversion.py tests/test_model_conversion_isolation.py tests/test_api_model_conversion.py -q`
Expected: conversion module/endpoints are missing.

- [ ] **Step 3: Implement pinned command plans and isolated worker boundary**

Resolve the llama.cpp toolchain to an exact reviewed release/digest. Permit only its declared architecture list. Build argv as arrays, never shell strings: `convert_hf_to_gguf.py <snapshot> --outfile <bf16.gguf> --outtype bf16`, then `llama-quantize <bf16.gguf> <output.gguf> Q4_K_M`. Run with network disabled, read-only source, one writable output, empty credential environment, bounded CPU/memory/time/output, and no workspace mount. Validate output through Task 8 parser before registration. Cleanup requires a separate owner action.

- [ ] **Step 4: Verify GREEN and provenance chain**

Run: `python -m pytest tests/test_model_conversion.py tests/test_model_conversion_isolation.py tests/test_api_model_conversion.py -q`
Expected: all pass; output record names exact HF revision, toolchain digest, quantization, and fingerprint.

- [ ] **Step 5: Commit**

```bash
git add raiker/models/conversion.py raiker/models/local_operations.py raiker/api/routes_models.py tests/test_model_conversion.py tests/test_model_conversion_isolation.py tests/test_api_model_conversion.py
git commit -m "feat: convert hugging face models safely"
```

### Task 11: Models setup, local library, Hugging Face, and Downloads UI

**Files:**
- Modify: `apps/web/src/lib/apiTypes.ts`
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/lib/views/ModelsView.svelte`
- Create: `apps/web/src/lib/views/models/ProvidersPanel.svelte`
- Create: `apps/web/src/lib/views/models/LocalLibraryPanel.svelte`
- Create: `apps/web/src/lib/views/models/HuggingFacePanel.svelte`
- Create: `apps/web/src/lib/views/models/DownloadsPanel.svelte`
- Create: `apps/web/src/lib/views/models/ExistingModelsPanel.svelte`
- Create: `apps/web/src/lib/components/ModelOperationTray.svelte`
- Modify: `apps/web/src/App.svelte`
- Test: `apps/web/src/lib/views/ModelsView.test.ts`
- Test: `apps/web/src/lib/views/models/ProvidersPanel.test.ts`
- Test: `apps/web/src/lib/views/models/LocalLibraryPanel.test.ts`
- Test: `apps/web/src/lib/views/models/HuggingFacePanel.test.ts`
- Test: `apps/web/src/lib/views/models/DownloadsPanel.test.ts`
- Test: `apps/web/src/lib/components/ModelOperationTray.test.ts`

**Interfaces:**
- Consumes: Tasks 2 and 7–10 APIs.
- Produces: approved Models tab architecture and persistent operation tray.

- [ ] **Step 1: Write failing navigation and primary-flow component tests**

```ts
it("shows zero ready providers and offers setup instead of claiming Ollama is set up", async () => {
  render(ModelsView);
  expect(await screen.findByText("0 models ready")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Set up a model" })).toBeInTheDocument();
  expect(screen.queryByText(/1 of 10 providers set up/)).not.toBeInTheDocument();
});

it("prefers a fitting existing GGUF over conversion", async () => {
  render(HuggingFacePanel);
  await searchFor("owner/repo");
  expect(await screen.findByText("Existing GGUF")).toBeInTheDocument();
  expect(screen.getByText("Recommended balance")).toBeInTheDocument();
  expect(screen.getByText("Convert locally")).toHaveAttribute("aria-expanded", "false");
});
```

- [ ] **Step 2: Run and verify RED**

Run: `npm --prefix apps/web test -- ModelsView.test.ts ProvidersPanel.test.ts LocalLibraryPanel.test.ts HuggingFacePanel.test.ts DownloadsPanel.test.ts ModelOperationTray.test.ts`
Expected: panels/types/API methods are missing.

- [ ] **Step 3: Implement the approved UI decomposition**

Move provider markup from `ModelsView.svelte` into `ProvidersPanel` without changing existing Routing/Pricing/Posture behavior. Add Local library, Hugging Face, Downloads tabs with overflow behavior. Implement variant table, fit states, licence/gated review, source approval, deploy side panel, install review, job groups, cancellation, retry, and explicit partial cleanup. Mount `ModelOperationTray` once in `App.svelte`. Use semantic theme tokens only.

```svelte
{#if activeTab === "providers"}<ProvidersPanel {models} />
{:else if activeTab === "local-library"}<LocalLibraryPanel />
{:else if activeTab === "hugging-face"}<HuggingFacePanel />
{:else if activeTab === "downloads"}<DownloadsPanel />
{:else}<ExistingModelsPanel tab={activeTab} {models} />{/if}
```

- [ ] **Step 4: Verify GREEN, checks, lint, and production build**

Run: `npm --prefix apps/web test -- ModelsView.test.ts ProvidersPanel.test.ts LocalLibraryPanel.test.ts HuggingFacePanel.test.ts DownloadsPanel.test.ts ModelOperationTray.test.ts && npm --prefix apps/web run check && npm --prefix apps/web run lint && npm --prefix apps/web run build`
Expected: all pass with no accessibility or TypeScript warnings.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/lib/apiTypes.ts apps/web/src/lib/api.ts apps/web/src/lib/views/ModelsView.svelte apps/web/src/lib/views/models apps/web/src/lib/components/ModelOperationTray.svelte apps/web/src/lib/components/ModelOperationTray.test.ts apps/web/src/App.svelte
git commit -m "feat: build model setup and acquisition UI"
```

### Task 12: Live Playwright acceptance, documentation, and full verification

**Files:**
- Create: `apps/web/e2e/bug-69-model-readiness-live.spec.ts`
- Create: `apps/web/e2e/bug-69-local-model-library-live.spec.ts`
- Create: `apps/web/e2e/bug-69-huggingface-live.spec.ts`
- Modify: `docs/plans/TO_BE_FIXED.md`
- Modify: `docs/plans/RAIKER_LIVE_MANUAL_TEST_PLAN.md`
- Modify: `docs/plans/screenshots/README.md`
- Modify: `docs/WEB_APP_LIVE_TEST.md`
- Modify: `README.md`
- Modify: `docs/guide/README.md`
- Modify: `docs/guide/connecting-a-model.md`
- Modify: `docs/guide/troubleshooting.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md`
- Modify: `docs/API_AND_CONTRACT_SCHEMAS.md`
- Modify: `docs/SECURITY_AND_POLICY.md`
- Modify: `docs/THREAT_MODEL.md`
- Modify: `docs/OWASP_GENAI_SECURITY_MAPPING.md`
- Modify: `docs/FEATURE_COVERAGE_MATRIX.md`
- Modify: `docs/IMPLEMENTATION_STATUS.md`

**Interfaces:**
- Consumes: all previous tasks.
- Produces: reproducible live evidence, closed BUG-69 documentation, pushed green `main`.

- [ ] **Step 1: Write live specs before final UI adjustments**

```ts
test("BUG-69 blocks every model-backed surface until exact readiness", async ({ page }) => {
  await registerFreshOwner(page);
  for (const destination of ["Workbench", "Chat", "Build", "Tasks"]) {
    await openDestination(page, destination);
    await expect(page.getByText("No model is ready")).toBeVisible();
    await expect(primaryModelAction(page)).toBeDisabled();
  }
  await page.getByRole("link", { name: "Models" }).click();
  await expect(page.getByText("0 models ready")).toBeVisible();
});
```

- [ ] **Step 2: Run focused offline and mocked e2e verification**

Run: `python -m pytest tests/test_model_readiness.py tests/test_api_model_readiness.py tests/test_model_readiness_guards.py tests/test_model_setup_state.py tests/test_model_local_operations.py tests/test_model_library.py tests/test_huggingface_models.py tests/test_model_conversion.py -q`

Run: `npm --prefix apps/web run test:e2e:mocked -- --grep "BUG-69"`
Expected: all pass before using live credentials.

- [ ] **Step 3: Start one real service and run live provider/local acquisition flows**

Start `raiker-web` against a fresh temporary workspace with the required hosted-provider policy and egress allowlist. Enter Anthropic and OpenRouter credentials only through Models UI; test each exact model. Detect local Ollama `gemma4:31b-cloud`. Stop Ollama and verify readiness invalidation, then restart it. Add an approved small GGUF folder and deploy through managed llama.cpp. Download a small permissively licensed Hugging Face GGUF by pinned revision; run the supported Safetensors conversion fixture in the isolated worker.

Use the Playwright CLI workflow: snapshot before every referenced interaction, resnapshot after navigation/modal changes, and store screenshots under `docs/plans/screenshots/working/`.

- [ ] **Step 4: Review screenshots and fix every issue found test-first**

Capture the visual acceptance set from the design at 1440, 1024, 768, and 375 pixels in light/dark themes. For each discovered defect, add a failing unit/e2e regression, implement the smallest fix, rerun the focused test, and record it as FIXED in `TO_BE_FIXED.md`; if external state makes it impossible in this run, add a fully structured open BUG entry.

- [ ] **Step 5: Update documentation in existing formats**

Mark BUG-69 fixed only after all completion criteria pass. Document configured-versus-ready semantics, installer legal boundary, approved-root discovery, GGUF deployment, Hugging Face licensing/gating, conversion isolation, exact commands, provider evidence, screenshot filenames, and residual limits. Remove stale claims that the shipped Ollama preference is set up without a probe.

- [ ] **Step 6: Run the complete local quality gate**

Run: `python -m pytest -q`

Run: `python -m ruff check .`

Run: `python -m mypy raiker apps tests`

Run: `npm --prefix apps/web test`

Run: `npm --prefix apps/web run check`

Run: `npm --prefix apps/web run lint`

Run: `npm --prefix apps/web run build`

Run: `npm --prefix apps/web run test:e2e:mocked`

Expected: every command passes without warnings introduced by this change.

- [ ] **Step 7: Commit implementation evidence and push**

```bash
git add README.md docs apps/web/e2e apps/web/src raiker tests pyproject.toml
git commit -m "fix: complete model readiness and acquisition"
git push origin main
```

- [ ] **Step 8: Monitor GitHub Actions to green**

Run: `gh run list --branch main --commit "$(git rev-parse HEAD)" --limit 20`

For every non-green workflow, inspect with `gh run view <run-id> --log-failed`, reproduce locally, add a regression where applicable, fix, commit, push, and monitor the new head. Completion requires every required workflow for the final pushed commit to report success.

## Plan self-review mapping

- Readiness domain, all states, exact binding, freshness, invalidation: Tasks 1–3.
- Cross-surface UI, shared modal, draft preservation, responsive/accessibility behavior: Tasks 4–5 and 11–12.
- First-run and reusable Models setup: Tasks 6 and 11.
- Legal runtime installation boundary and durable progress: Tasks 7 and 11.
- Approved-root discovery, GGUF metadata, in-place deployment: Task 8 and Task 11.
- Hugging Face search, licences, gating, GGUF-first download: Tasks 9 and 11.
- Safetensors-only isolated conversion and quantization: Task 10 and Task 11.
- Three-provider live testing, local GGUF/Hugging Face evidence, docs, push, green CI: Task 12.
