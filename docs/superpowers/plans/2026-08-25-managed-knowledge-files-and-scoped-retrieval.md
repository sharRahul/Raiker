# Managed Knowledge Files and Scoped Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add managed all-file libraries for Memory and Projects, enforce owner-wide Chat and selected-project Build retrieval, and finish the systematic desktop control refresh.

**Architecture:** A focused managed-file service owns contained disk writes and database metadata; extractor adapters feed the existing governed memory projections and context gatherer. Surface mode is explicit on every turn so the backend—not UI state—enforces Chat and Build retrieval boundaries.

**Tech Stack:** Python 3.12, FastAPI, SQLite/SQLCipher, Svelte 5, TypeScript, Vitest, Testing Library, Playwright.

## Global Constraints

- Memory originals live under `.raiker/memory-files/`.
- Project originals live under `.raiker/projects/<project-slug>/`.
- Both libraries accept every file type; only safely parseable formats receive content indexes.
- Chat retrieval is owner-wide; Build retrieval is account memory plus its selected project's files, memories, and assigned chats.
- Build requires one project before starting work and cannot change it during an active turn.
- Uploaded content is untrusted data and is never executed automatically.
- Preserve the current colour palette and existing sidebar/navigation information architecture.
- Keep original files, extracted content, indexes, and provenance linked through lifecycle changes.

---

## File Structure

- Create `raiker/knowledge/files.py`: managed-root containment, imports, metadata DTOs, lifecycle operations.
- Create `raiker/knowledge/extractors.py`: safe bounded extraction dispatch over existing document readers.
- Create `raiker/knowledge/indexing.py`: file chunk projection and retirement orchestration.
- Create `raiker/api/routes_knowledge_files.py`: owner-scoped list/import/delete/retry endpoints.
- Modify `raiker/storage/migrations.py` and `raiker/storage/sqlite.py`: managed-file catalogue and queries.
- Modify `raiker/control/dashboard.py`, `raiker/control/web_read_models.py`, and `raiker/context/gatherer.py`: project migration/read models and scoped retrieval.
- Modify `raiker/api/app.py`, turn schemas/routes, and web API types: register APIs and carry explicit surface/project scope.
- Modify `apps/web/src/App.svelte`, `Topbar.svelte`, `BuildView.svelte`, `ProjectsView.svelte`, and `MemoryView.svelte`: shell and library UX.
- Create `apps/web/src/lib/components/FileLibrary.svelte`: shared file/folder import and status UI.
- Modify shared CSS/components and individually reviewed views: systematic icon grouping and geometry.
- Modify backend/frontend tests and `apps/web/e2e/ui-sweep-responsive-live.spec.ts`; replace `docs/plans/screenshots/pages/**`.

### Task 1: Managed-file catalogue and contained storage

**Files:**
- Create: `raiker/knowledge/__init__.py`
- Create: `raiker/knowledge/files.py`
- Modify: `raiker/storage/migrations.py`
- Modify: `raiker/storage/sqlite.py`
- Test: `tests/test_managed_knowledge_files.py`

**Interfaces:**
- Produces: `ManagedFileScope(kind: Literal["memory", "project"], project_id: str | None)`.
- Produces: `ManagedFileService.import_file(scope, relative_path, data, media_type, owner_principal_id) -> ManagedFileRecord`.
- Produces: store methods `insert_managed_file`, `list_managed_files`, `get_managed_file`, `set_managed_file_index_state`, and `retire_managed_file`.

- [ ] **Step 1: Write failing containment and all-file tests**

```python
def test_memory_accepts_unknown_binary_type(tmp_path, owner_store):
    record = ManagedFileService(tmp_path, owner_store).import_file(
        ManagedFileScope("memory"), "archive/data.custom", b"\x00\x01payload",
        "application/x-custom", OWNER,
    )
    assert record.relative_path == "archive/data.custom"
    assert (tmp_path / ".raiker/memory-files/archive/data.custom").read_bytes() == b"\x00\x01payload"

@pytest.mark.parametrize("path", ["../escape.txt", "/absolute.txt", "folder/../../escape.txt"])
def test_import_rejects_paths_outside_managed_root(tmp_path, owner_store, path):
    with pytest.raises(ManagedFileError, match="managed_file_path_outside_scope"):
        ManagedFileService(tmp_path, owner_store).import_file(
            ManagedFileScope("memory"), path, b"x", "text/plain", OWNER,
        )
```

- [ ] **Step 2: Run the focused tests and confirm failure**

Run: `python -m pytest tests/test_managed_knowledge_files.py -q`
Expected: FAIL because `raiker.knowledge.files` does not exist.

- [ ] **Step 3: Add schema and store methods**

Add a migration for `managed_files` containing `file_id`, `owner_principal_id`, `scope_kind`, nullable `project_id`, `relative_path`, `media_type`, `size_bytes`, `content_hash`, `index_state`, nullable `index_error`, timestamps, and unique active `(owner_principal_id, scope_kind, project_id, relative_path)` identity.

- [ ] **Step 4: Implement atomic contained imports**

Use `internal_io_path`, resolved-root containment checks, a same-directory temporary file, `Path.replace`, and SHA-256. Reject traversal and symlink escapes; never reject solely because of file type.

- [ ] **Step 5: Run focused and migration tests**

Run: `python -m pytest tests/test_managed_knowledge_files.py tests/test_storage_migrations.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add raiker/knowledge raiker/storage/migrations.py raiker/storage/sqlite.py tests/test_managed_knowledge_files.py
git commit -m "Add managed knowledge file storage"
```

### Task 2: Project-root migration

**Files:**
- Modify: `raiker/control/dashboard.py`
- Modify: `raiker/control/knowledge_scope.py`
- Modify: `raiker/storage/sqlite.py`
- Test: `tests/test_projects.py`
- Test: `tests/test_project_root_migration.py`

**Interfaces:**
- Consumes: managed root `.raiker/projects/<slug>/` and existing project rows.
- Produces: `migrate_project_roots(workspace_root: Path, store: SQLiteStore) -> ProjectRootMigrationReport`.

- [ ] **Step 1: Write failing new-root and migration tests**

```python
def test_new_project_uses_managed_root(service):
    created = service.create_project("Alpha", OWNER)
    assert created.data["root_subpath"] == ".raiker/projects/alpha"

def test_existing_project_root_moves_without_overwrite(tmp_path, store):
    old = tmp_path / "projects/alpha"
    old.mkdir(parents=True)
    (old / "notes.txt").write_text("alpha", encoding="utf-8")
    store.create_project("proj_a", "Alpha", "projects/alpha")
    report = migrate_project_roots(tmp_path, store)
    assert report.migrated == ("proj_a",)
    assert (tmp_path / ".raiker/projects/alpha/notes.txt").read_text() == "alpha"
    assert store.load_project("proj_a")["root_subpath"] == ".raiker/projects/alpha"
```

- [ ] **Step 2: Run tests and confirm old-root assertions fail**

Run: `python -m pytest tests/test_projects.py tests/test_project_root_migration.py -q`
Expected: FAIL on `projects/alpha` behavior.

- [ ] **Step 3: Implement idempotent migration and managed project creation**

Do not overwrite destination conflicts. Update `root_subpath` only after destination validation. Ensure Knowledge Map roots follow the stored project root without exposing other `.raiker` internals.

- [ ] **Step 4: Run project and knowledge-scope tests**

Run: `python -m pytest tests/test_projects.py tests/test_nested_projects.py tests/test_project_root_migration.py tests/test_brain_sources.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add raiker/control/dashboard.py raiker/control/knowledge_scope.py raiker/storage/sqlite.py tests/test_projects.py tests/test_project_root_migration.py
git commit -m "Move projects into managed Raiker storage"
```

### Task 3: Extraction and projection lifecycle

**Files:**
- Create: `raiker/knowledge/extractors.py`
- Create: `raiker/knowledge/indexing.py`
- Modify: `raiker/runtime/attachments.py`
- Modify: `raiker/storage/sqlite.py`
- Test: `tests/test_managed_file_indexing.py`

**Interfaces:**
- Produces: `extract_managed_file(path, media_type, max_chars) -> ExtractionResult`.
- Produces: `ManagedFileIndexer.index(file_id, owner_principal_id) -> ManagedFileRecord` and `retire(file_id, owner_principal_id) -> None`.
- Consumes: existing TXT/Markdown/CSV/PDF/DOCX/XLSX local extractors.

- [ ] **Step 1: Write failing parsed and metadata-only tests**

```python
def test_text_file_is_chunked_with_provenance(indexer, imported_text):
    indexed = indexer.index(imported_text.file_id, OWNER)
    chunks = indexer.store.list_managed_file_chunks(imported_text.file_id, OWNER)
    assert indexed.index_state == "ready"
    assert chunks[0]["source_file_id"] == imported_text.file_id

def test_unknown_binary_is_metadata_only(indexer, imported_binary):
    indexed = indexer.index(imported_binary.file_id, OWNER)
    assert indexed.index_state == "metadata_only"
    assert indexer.store.list_managed_file_chunks(imported_binary.file_id, OWNER) == []
```

- [ ] **Step 2: Run and confirm failures**

Run: `python -m pytest tests/test_managed_file_indexing.py -q`
Expected: FAIL because extractor/indexer interfaces do not exist.

- [ ] **Step 3: Extract through bounded adapters and persist chunks**

Keep OOXML/PDF validation local. Treat `.doc`/`.xls` and unsupported data as metadata-only. Store chunk text as untrusted source data and link every projection to `file_id` and revision hash.

- [ ] **Step 4: Implement replacement and retirement**

Replacing or deleting a file retires old chunks, lexical rows, vectors, and graph evidence before publishing the new revision.

- [ ] **Step 5: Run indexing, attachment, and memory tests**

Run: `python -m pytest tests/test_managed_file_indexing.py tests/test_document_attachments.py tests/test_hybrid_memory_retrieval.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add raiker/knowledge raiker/runtime/attachments.py raiker/storage/sqlite.py tests/test_managed_file_indexing.py
git commit -m "Index managed files with source provenance"
```

### Task 4: File APIs and scoped hybrid retrieval

**Files:**
- Create: `raiker/api/routes_knowledge_files.py`
- Modify: `raiker/api/app.py`
- Modify: `raiker/api/schemas.py`
- Modify: `raiker/context/gatherer.py`
- Modify: `raiker/memory/retrieval.py`
- Modify: `raiker/api/routes_prompts.py`
- Modify: `raiker/runtime/orchestrator.py`
- Test: `tests/test_managed_file_api.py`
- Test: `tests/test_context_surface_scoping.py`

**Interfaces:**
- Produces endpoints `GET/POST /api/memory/files`, `GET/POST /api/projects/{project_id}/managed-files`, `DELETE /api/managed-files/{file_id}`, and `POST /api/managed-files/{file_id}/retry`.
- Produces explicit turn fields `surface: Literal["chat", "build"]` and `project_id: str | None`.
- Produces `ContextGatherer.gather(..., surface: str, project_id: str | None)` enforcement.

- [ ] **Step 1: Write failing owner isolation and boundary tests**

```python
def test_chat_recall_can_find_every_owned_project(client, owner_headers, two_projects):
    response = submit_turn(client, owner_headers, surface="chat", project_id=None, prompt="alpha handbook")
    assert source_projects(response) == {two_projects.alpha_id}

def test_build_recall_excludes_other_projects_and_unassigned_chats(client, owner_headers, two_projects):
    response = submit_turn(client, owner_headers, surface="build", project_id=two_projects.alpha_id, prompt="shared keyword")
    assert source_projects(response) <= {two_projects.alpha_id}
    assert unassigned_session_id not in source_sessions(response)

def test_build_without_project_fails_closed(client, owner_headers):
    response = submit_turn(client, owner_headers, surface="build", project_id=None, prompt="work")
    assert response.status_code == 422
```

- [ ] **Step 2: Run tests and confirm missing API/scope failures**

Run: `python -m pytest tests/test_managed_file_api.py tests/test_context_surface_scoping.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement APIs and explicit surface contract**

Authenticate before resolving project or file identifiers. Multipart/folder-manifest requests return per-file results. Bind Build session creation and retrieval to the explicit selected project; ignore the account-level active-project preference for Chat.

- [ ] **Step 4: Extend hybrid retrieval without a parallel engine**

Merge file chunks, approved memories, and matching conversations into bounded ranked results. Deduplicate by source revision and preserve `source_kind`, `file_id`, `relative_path`, `project_id`, and `session_id` provenance.

- [ ] **Step 5: Run API, isolation, context, and retrieval suites**

Run: `python -m pytest tests/test_managed_file_api.py tests/test_context_surface_scoping.py tests/test_owner_context_isolation.py tests/test_project_scoping.py tests/test_chat_search.py tests/test_hybrid_memory_retrieval.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add raiker/api raiker/context/gatherer.py raiker/memory/retrieval.py tests/test_managed_file_api.py tests/test_context_surface_scoping.py
git commit -m "Enforce scoped knowledge retrieval by surface"
```

### Task 5: Web API contracts and shared file library

**Files:**
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/lib/apiTypes.ts`
- Create: `apps/web/src/lib/components/FileLibrary.svelte`
- Create: `apps/web/src/lib/components/FileLibrary.test.ts`
- Modify: `apps/web/src/lib/views/MemoryView.svelte`
- Modify: `apps/web/src/lib/views/MemoryView.test.ts`
- Modify: `apps/web/src/lib/views/ProjectsView.svelte`
- Modify: `apps/web/src/lib/views/ProjectsView.test.ts`

**Interfaces:**
- Produces: `ManagedFile`, `ManagedFileImportResult`, `ManagedFileScope` web types.
- Produces: `<FileLibrary scope projectId? />` with file/folder upload, hierarchy, state, retry, and delete.

- [ ] **Step 1: Write failing component and view tests**

```ts
it("imports every file selected from a folder and preserves relative paths", async () => {
  render(FileLibrary, { props: { scope: "memory" } });
  expect(screen.getByRole("button", { name: "Add files" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Add folder" })).toBeVisible();
});
```

Assert accessible import grouping, status labels, retry, project-specific endpoint use, and no filtering by MIME type in the file inputs.

- [ ] **Step 2: Run tests and confirm failure**

Run: `cd apps/web && npm test -- FileLibrary.test.ts MemoryView.test.ts ProjectsView.test.ts`
Expected: FAIL because `FileLibrary` and APIs do not exist.

- [ ] **Step 3: Implement typed APIs and FileLibrary**

Use hidden `input[type=file]` controls with `multiple`; folder selection adds `webkitdirectory` as a progressive enhancement. Send each `webkitRelativePath` in the manifest. Announce partial results through an `aria-live` region.

- [ ] **Step 4: Mount library in Memory and selected Project detail**

Keep uploaded documents visually distinct from approved atomic memories. Show managed relative path, file size/type, and `queued`, `indexing`, `ready`, `metadata-only`, or `failed` state.

- [ ] **Step 5: Run component checks**

Run: `cd apps/web && npm test -- FileLibrary.test.ts MemoryView.test.ts ProjectsView.test.ts && npm run check`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/lib/api.ts apps/web/src/lib/apiTypes.ts apps/web/src/lib/components/FileLibrary.svelte apps/web/src/lib/components/FileLibrary.test.ts apps/web/src/lib/views/MemoryView.svelte apps/web/src/lib/views/MemoryView.test.ts apps/web/src/lib/views/ProjectsView.svelte apps/web/src/lib/views/ProjectsView.test.ts
git commit -m "Add managed file libraries to Memory and Projects"
```

### Task 6: Remove global project/theme controls and enforce Build selection

**Files:**
- Modify: `apps/web/src/lib/components/Topbar.svelte`
- Modify: `apps/web/src/lib/components/Topbar.test.ts`
- Modify: `apps/web/src/App.svelte`
- Modify: `apps/web/src/App.test.ts`
- Modify: `apps/web/src/lib/views/ChatView.svelte`
- Modify: `apps/web/src/lib/views/ChatView.test.ts`
- Modify: `apps/web/src/lib/views/BuildView.svelte`
- Modify: `apps/web/src/lib/views/BuildView.test.ts`
- Verify: `apps/web/src/lib/views/settings/Personalisation.svelte`
- Verify: `apps/web/src/lib/theme.ts`

**Interfaces:**
- Consumes: explicit `surface`/`project_id` turn contract.
- Produces: Build-owned persistent project selector and disabled composer without a project.

- [ ] **Step 1: Write failing shell and surface tests**

```ts
it("keeps project and theme choices out of the top bar", () => {
  render(Topbar, { props: { title: "Chat", hint: "Ask anything" } });
  expect(screen.queryByLabelText("Active project")).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/theme/i)).not.toBeInTheDocument();
});

it("requires a project before Build can send", () => {
  render(BuildView, { props: { projects: PROJECTS_WITHOUT_SELECTION } });
  expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
  expect(screen.getByText(/select a project to start/i)).toBeVisible();
});
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `cd apps/web && npm test -- Topbar.test.ts App.test.ts ChatView.test.ts BuildView.test.ts`
Expected: FAIL on existing top-bar controls and Build behavior.

- [ ] **Step 3: Remove top-bar project/theme dependencies**

Stop passing projects to `Topbar`. Keep theme under Settings and verify `loadThemeChoice()` returns `system` when no override exists. Chat submits `surface: "chat", project_id: null`.

- [ ] **Step 4: Make Build selection durable and fail closed**

Build submits `surface: "build"` with its selected project. Lock selector changes during streaming. Replace fallback to `projects.active_project_id` with the Build-local selection and expose a clear boundary label.

- [ ] **Step 5: Run shell, surface, and theme tests**

Run: `cd apps/web && npm test -- Topbar.test.ts App.test.ts ChatView.test.ts BuildView.test.ts Personalisation.test.ts theme.test.ts && npm run check`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/App.svelte apps/web/src/App.test.ts apps/web/src/lib/components/Topbar.svelte apps/web/src/lib/components/Topbar.test.ts apps/web/src/lib/views/ChatView.svelte apps/web/src/lib/views/ChatView.test.ts apps/web/src/lib/views/BuildView.svelte apps/web/src/lib/views/BuildView.test.ts
git commit -m "Move project selection into Build"
```

### Task 7: Systematic desktop control consistency

**Files:**
- Modify: `apps/web/src/app.css`
- Modify: `apps/web/src/lib/components/Icon.svelte`
- Create or modify: `apps/web/src/lib/components/IconButtonGroup.svelte`
- Modify: `apps/web/src/lib/views/BrainView.svelte`
- Modify: `apps/web/src/lib/components/BuildSidePanel.svelte`
- Modify: `apps/web/src/lib/components/FileInspector.svelte`
- Modify: `apps/web/src/lib/components/HostControl.svelte`
- Modify: `apps/web/src/lib/components/ImageViewport.svelte`
- Modify: `apps/web/src/lib/components/MessageActions.svelte`
- Modify: `apps/web/src/lib/components/ModelPricingPanel.svelte`
- Modify: `apps/web/src/lib/components/ProviderMatrix.svelte`
- Modify: `apps/web/src/lib/components/RepoConnector.svelte`
- Modify: `apps/web/src/lib/components/SessionMenu.svelte`
- Modify: `apps/web/src/lib/components/StopSwitch.svelte`
- Modify: `apps/web/src/lib/views/ActivityView.svelte`
- Modify: `apps/web/src/lib/views/ApprovalsView.svelte`
- Modify: `apps/web/src/lib/views/CapabilitiesView.svelte`
- Modify: `apps/web/src/lib/views/ConnectionsView.svelte`
- Modify: `apps/web/src/lib/views/ExtensionsView.svelte`
- Modify: `apps/web/src/lib/views/McpView.svelte`
- Modify: `apps/web/src/lib/views/ModelsView.svelte`
- Modify: `apps/web/src/lib/views/ObserveView.svelte`
- Modify: `apps/web/src/lib/views/SessionsView.svelte`
- Modify: `apps/web/src/lib/views/SkillsView.svelte`
- Modify: `apps/web/src/lib/views/TasksView.svelte`
- Modify: `apps/web/src/lib/views/WorkbenchView.svelte`
- Modify: `apps/web/src/lib/views/models/DownloadsPanel.svelte`
- Modify: `apps/web/src/lib/views/models/ProvidersPanel.svelte`
- Modify: `apps/web/src/lib/views/models/ProviderUsagePanel.svelte`
- Modify: `apps/web/src/lib/views/settings/Account.svelte`
- Modify: `apps/web/src/lib/views/settings/Runtime.svelte`
- Modify: `apps/web/src/lib/views/settings/SecurityLogin.svelte`
- Modify: relevant component tests.

**Interfaces:**
- Produces: shared 32/40/44 px control tokens and grouped non-destructive icon actions.

- [ ] **Step 1: Add failing geometry and accessibility assertions**

Assert grouped buttons retain individual accessible names, destructive actions are outside groups, and Brain/file/toolbars use shared classes instead of raw glyphs or local 34 px dimensions.

- [ ] **Step 2: Run affected view tests and capture failures**

Run: `cd apps/web && npm test -- BrainView.test.ts ProjectsView.test.ts MemoryView.test.ts`
Expected: FAIL on new shared-control expectations.

- [ ] **Step 3: Implement shared tokens and grouped controls**

Define compact/default/prominent control sizes, one icon-button radius/focus contract, segmented first/middle/last borders, consistent dropdown height, and hover/disabled styling using existing palette variables.

- [ ] **Step 4: Review every route for local exceptions**

Use the route catalogue to inspect each desktop view. Change only inconsistent geometry, icon rendering, grouping, hover, dropdown, spacing, or alignment; preserve route structure and page-specific density.

- [ ] **Step 5: Run all web checks**

Run: `cd apps/web && npm test && npm run check && npm run lint && npm run build`
Expected: PASS with no accessibility or type errors.

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/app.css apps/web/src/lib/components apps/web/src/lib/views
git commit -m "Standardize desktop controls and icon groups"
```

### Task 8: End-to-end verification, screenshots, review, and delivery

**Files:**
- Modify: `apps/web/e2e/ui-sweep-responsive-live.spec.ts`
- Replace: `docs/plans/screenshots/pages/**`
- Modify: `docs/plans/screenshots/README.md`

**Interfaces:**
- Consumes: complete managed knowledge and desktop UI feature.
- Produces: current desktop screenshot catalogue and final verification evidence.

- [ ] **Step 1: Add E2E coverage for Memory, Projects, Chat, Build, Settings, and shell controls**

Cover file/folder affordances, Build's required project, absent top-bar controls, System theme default, sidebar hide/show, route titles, and 1440/2560/3840 width bounds.

- [ ] **Step 2: Run focused E2E and fix only evidenced defects**

Run: `cd apps/web && npm run test:e2e:mocked -- ui-sweep-responsive-live.spec.ts`
Expected: PASS.

- [ ] **Step 3: Run backend and frontend verification**

Run: `python -m pytest tests/test_managed_knowledge_files.py tests/test_project_root_migration.py tests/test_managed_file_indexing.py tests/test_managed_file_api.py tests/test_context_surface_scoping.py tests/test_projects.py tests/test_project_scoping.py tests/test_hybrid_memory_retrieval.py -q`

Run: `cd apps/web && npm test && npm run check && npm run lint && npm run build`

Expected: all commands PASS.

- [ ] **Step 4: Regenerate and inspect desktop screenshots**

Resolve `docs/plans/screenshots/pages` to an absolute path and verify it is beneath the repository before replacement. Run the established authenticated screenshot sweep. Inspect representative operational, reading, Chat, Build, Memory, Projects, Settings, light, dark, sidebar-open, and sidebar-hidden captures at original resolution.

- [ ] **Step 5: Request sub-agent review**

Ask a fresh reviewer to compare the implementation and tests with the design specification, focusing on containment, owner/project isolation, migration safety, untrusted content, accessibility, and visual consistency. Address every confirmed issue and rerun affected checks.

- [ ] **Step 6: Run final clean-state verification**

Run: `git diff --check`

Run: `git status --short`

Confirm only intended source, tests, plan/spec, screenshot catalogue, and screenshot documentation are changed.

- [ ] **Step 7: Commit and push main**

```bash
git add -A
git commit -m "Add managed knowledge libraries and scoped retrieval"
git push origin main
```
