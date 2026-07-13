# Chat Search and Project Deletion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Search saved chats by title/content, continue a selected chat, and permanently delete a project's chats and folder.

**Architecture:** Add SQLite-backed search and project-deletion operations to DashboardService, expose authenticated FastAPI routes, then consume those routes in the Svelte views.

**Tech Stack:** Python/FastAPI, SQLite, Svelte 5, pytest, Vitest.

## Global Constraints

- Use SQLite matching only; no dependency, fuzzy index, or background job.
- UI search results show titles/previews, never session IDs.
- Delete only the verified workspace-contained project root and its scoped chat records.
- Confirmation text: “This will permanently delete all project chats and files in this project folder. To save chats, move them to your chat list or another project before deleting.”

---

### Task 1: Backend search and deletion

**Files:** Modify `raiker/storage/sqlite.py`, `raiker/control/dashboard.py`, `raiker/api/routes_dashboard.py`, `tests/test_projects.py`; create `tests/test_chat_search.py`.

**Interfaces:** `DashboardService.search_sessions(query, user_id) -> tuple[SessionView, ...]`; `DashboardService.delete_project(project_id, acting_principal_id) -> ControlResult`; `GET /api/chat-search?q=`; `DELETE /api/projects/{project_id}`.

- [ ] **Step 1: Write failing tests**

```python
def test_search_matches_turn_text(service, workspace):
    service.store.create_session("sess_alpha", str(workspace), title="Release notes")
    service.store.create_turn("turn_alpha", "sess_alpha", "prompt", "completed", prompt_text="Find migration plan")
    assert [s.title for s in service.search_sessions("migration", None)] == ["Release notes"]

def test_delete_project_removes_scoped_records_and_folder(service, workspace):
    project_id = service.create_project("Alpha", OWNER).data["project_id"]
    service.select_project(project_id, OWNER)
    service.store.create_session("sess_alpha", str(workspace))
    _insert_checkpoint(service.store, "ckpt_alpha", "sess_alpha")
    assert service.delete_project(project_id, OWNER).ok
    assert service.store.load_session("sess_alpha") is None
    assert not (workspace / "projects" / "alpha").exists()
```

- [ ] **Step 2: Run red tests**

Run: `python -m pytest tests/test_chat_search.py tests/test_projects.py -q`

Expected: FAIL because the methods do not exist.

- [ ] **Step 3: Implement the smallest backend change**

`SQLiteStore.search_sessions` joins sessions to turns and returns distinct matching sessions when title, prompt text, or summary contains the query; constrain by user when supplied. `SQLiteStore.delete_project` removes dependent rows for sessions in the project in one transaction, clears active selection, and removes the project. `DashboardService.delete_project` authorises the caller, containment-checks the resolved root, calls the store operation, then runs `shutil.rmtree` on the root. Add the authenticated routes with honest 403/404 failures.

- [ ] **Step 4: Run green tests and commit**

Run: `python -m pytest tests/test_chat_search.py tests/test_projects.py -q`

Expected: PASS.

Commit: `git add raiker/storage/sqlite.py raiker/control/dashboard.py raiker/api/routes_dashboard.py tests/test_chat_search.py tests/test_projects.py && git commit -m "feat: search chats and delete projects"`

### Task 2: Search and continue chats

**Files:** Modify `apps/web/src/lib/nav.ts`, `apps/web/src/lib/api.ts`, `apps/web/src/lib/views/SearchChatView.svelte`, `apps/web/src/lib/views/ChatView.svelte`, `apps/web/src/App.svelte`, `apps/web/src/lib/nav.test.ts`; create `apps/web/src/lib/views/SearchChatView.test.ts`.

**Interfaces:** `api.searchChats(q: string) -> Promise<SessionSummary[]>`; `#/new-chat?session=<id>` passes an internal ID to ChatView, which loads it through `api.session(id)` and supplies it to later `streamPrompt` calls.

- [ ] **Step 1: Write failing UI tests**

```ts
it("uses the magnifying-glass icon for Search Chat", () => {
  expect(navItem("search-chat").icon).toBe("search");
});

it("shows matching conversation titles and continuation links", async () => {
  // Stub GET /api/chat-search?q=migration and assert a title-only result.
});
```

- [ ] **Step 2: Run red tests**

Run: `npm test -- --run src/lib/nav.test.ts src/lib/views/SearchChatView.test.ts`

Expected: FAIL because Search Chat still uses the Sessions icon and list API.

- [ ] **Step 3: Implement the smallest UI change**

Set the nav icon to `search`. Add `api.searchChats`. SearchChatView only calls it after non-empty input and renders a flat title/preview list that links internally to New Chat. App parses the hash query and passes the session ID to ChatView. ChatView rehydrates stored turns, retains the ID internally, and never prints it.

- [ ] **Step 4: Run green tests and commit**

Run: `npm test -- --run src/lib/nav.test.ts src/lib/views/SearchChatView.test.ts src/App.test.ts`

Expected: PASS.

Commit: `git add apps/web/src/lib/nav.ts apps/web/src/lib/api.ts apps/web/src/lib/views/SearchChatView.svelte apps/web/src/lib/views/ChatView.svelte apps/web/src/App.svelte apps/web/src/lib/nav.test.ts apps/web/src/lib/views/SearchChatView.test.ts && git commit -m "feat: continue chats from search"`

### Task 3: Confirm project deletion in the UI

**Files:** Modify `apps/web/src/lib/api.ts`, `apps/web/src/lib/views/ProjectsView.svelte`; create `apps/web/src/lib/views/ProjectsView.test.ts`.

**Interfaces:** `api.deleteProject(id: string) -> Promise<{ ok: boolean }>`.

- [ ] **Step 1: Write the failing test**

```ts
it("confirms and deletes a project", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
  // Click Delete; assert exact warning and DELETE /api/projects/proj_alpha.
});
```

- [ ] **Step 2: Run red test**

Run: `npm test -- --run src/lib/views/ProjectsView.test.ts`

Expected: FAIL because no deletion control exists.

- [ ] **Step 3: Implement, verify, and commit**

Add `api.deleteProject`; add a Delete button that uses the exact confirmation copy, calls DELETE only after confirmation, then reloads the list and calls `onchanged`. Render server errors using the existing error style.

Run: `npm test -- --run src/lib/views/ProjectsView.test.ts src/lib/views/SearchChatView.test.ts src/lib/nav.test.ts`

Expected: PASS.

Run: `npm run build`

Expected: exits 0.

Run: `python -m pytest tests/test_chat_search.py tests/test_projects.py tests/test_api_dashboard.py -q`

Expected: PASS.

Commit: `git add apps/web/src/lib/api.ts apps/web/src/lib/views/ProjectsView.svelte apps/web/src/lib/views/ProjectsView.test.ts && git commit -m "feat: delete project chats and files"`
