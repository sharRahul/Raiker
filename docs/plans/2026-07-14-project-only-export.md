# Project-Only Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-optimized:subagent-driven-development (recommended) or superpowers-optimized:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an authenticated human download the redacted audit timeline for one directly assigned project.

**Architecture:** Extend the existing event-index lookup and JSONL exporter with an exact `project_id` filter, resolved through `sessions.project_id`. `DashboardService` authorizes a human caller and returns the existing export manifest. The API streams that manifest as a download and the Projects UI exposes an explicit control.

**Tech Stack:** Python 3.11, SQLite, FastAPI, pytest, Svelte 5, TypeScript, Vitest.

**Assumptions:**
- Assumes a project export is an audit-timeline export — will NOT include attachments, memory, files, or chat transcript records outside the event log.
- Assumes project membership is direct — will NOT include child or archived descendant projects.
- Assumes the local bearer-authenticated human is authorized for project operations — will NOT provide cross-account project isolation beyond the existing project model.

---

## File Structure

- `raiker/storage/sqlite.py` - Add exact project filtering to the existing event-index query.
- `raiker/events/export.py` - Pass the project scope through existing manifest and JSONL generation.
- `raiker/control/dashboard.py` - Authorize human project export requests and invoke the existing exporter.
- `raiker/api/routes_dashboard.py` - Stream a generated export without returning its workspace path.
- `tests/test_phase_5_audit_export.py` - Prove direct-project filtering and redaction survive export.
- `tests/test_projects.py` - Prove project export authorization and download semantics.
- `apps/web/src/lib/api.ts` - Download the authenticated JSONL response.
- `apps/web/src/lib/views/ProjectsView.svelte` - Add the explicit export button and failure state.
- `apps/web/src/lib/views/ProjectsView.test.ts` - Prove the view initiates the scoped export request.
- `docs/HANDOFF.md` and `docs/IMPLEMENTATION_STATUS.md` - Record the verified capability accurately.

### Task 1: Add Exact Project Filtering To The Existing Exporter

**Files:**
- Modify: `raiker/storage/sqlite.py`
- Modify: `raiker/events/export.py`
- Test: `tests/test_phase_5_audit_export.py`

**Security flag:** `security`

**Does NOT cover:** Child projects, attachments, memory, filesystem data, or unredacted exports.

- [ ] **Step 1: Write failing tests**

```python
def test_generate_export_filters_to_exact_project(store: SQLiteStore, writer: EventLogWriter) -> None:
    store.create_project("proj_alpha", "Alpha", "projects/alpha")
    store.create_project("proj_child", "Child", "projects/child", parent_id="proj_alpha")
    store.save_active_project("proj_alpha")
    store.create_session("sess_alpha", ".")
    store.save_active_project("proj_child")
    store.create_session("sess_child", ".")
    _write_events(writer, count=1, session="sess_alpha")
    _write_events(writer, count=1, session="sess_child")

    manifest = generate_export(store, project_id="proj_alpha")

    assert manifest.event_count == 1
    assert manifest.export_path is not None
    assert json.loads(manifest.scope_json)["project_id"] == "proj_alpha"
    with Path(manifest.export_path).open(encoding="utf-8") as exported:
        assert json.loads(exported.readline())["session_id"] == "sess_alpha"
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `python -m pytest tests/test_phase_5_audit_export.py -q`

Expected: FAIL because `generate_export()` does not accept `project_id`.

- [ ] **Step 3: Implement the minimal scoped query and export plumbing**

```python
# raiker/storage/sqlite.py
def list_event_index(..., project_id: str | None = None) -> list[dict]:
    # Existing filters remain unchanged.
    if project_id is not None:
        conditions.append("session_id IN (SELECT session_id FROM sessions WHERE project_id = ?)")
        params.append(project_id)

# raiker/events/export.py
def generate_export(..., project_id: str | None = None) -> ExportManifest:
    manifest = build_export_manifest(
        store, session_id, project_id=project_id, redact=redact, exported_by=exported_by
    )
```

Update `build_export_manifest()` and the JSONL row lookup to pass `project_id`; add `"project_id": project_id` to `scope` only when it is not `None`.

- [ ] **Step 4: Run focused tests to verify they pass**

Run: `python -m pytest tests/test_phase_5_audit_export.py -q`

Expected: PASS; an exact project excludes its child project event.

- [ ] **Step 5: Commit**

```bash
git add raiker/storage/sqlite.py raiker/events/export.py tests/test_phase_5_audit_export.py
```

### Task 2: Authorize And Stream Project Export Downloads

**Files:**
- Modify: `raiker/control/dashboard.py`
- Modify: `raiker/api/routes_dashboard.py`
- Test: `tests/test_projects.py`

**Security flag:** `security`

**Does NOT cover:** AI-initiated exports, unauthenticated downloads, project descendants, or returned filesystem paths.

- [ ] **Step 1: Write failing API tests**

```python
def test_authenticated_human_downloads_only_its_project_timeline(
    self, client: TestClient, workspace: Path
) -> None:
    headers = self._headers(client)
    project_id = client.post("/api/projects", json={"name": "Alpha"}, headers=headers).json()["project_id"]
    client.put("/api/projects/selection", json={"project_id": project_id}, headers=headers)
    SQLiteStore(workspace).create_session("sess_alpha", str(workspace))

    response = client.post(f"/api/projects/{project_id}/export", headers=headers)

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert "attachment;" in response.headers["content-disposition"]
    assert "/exports/" not in response.text

def test_project_export_requires_auth(self, client: TestClient) -> None:
    assert client.post("/api/projects/proj_missing/export").status_code == 401
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `python -m pytest tests/test_projects.py -q`

Expected: FAIL with `404` because the export route does not exist.

- [ ] **Step 3: Implement human-only service authorization and file streaming**

```python
# raiker/control/dashboard.py
def export_project(self, project_id: str, acting_principal_id: str | None) -> ControlResult:
    principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
    if principal is None:
        return ControlResult(ok=False, reason_code="principal_not_resolved")
    if principal.principal_type != PrincipalType.HUMAN:
        return ControlResult(ok=False, reason_code="not_authorized_human")
    if self.store.load_project(project_id) is None:
        return ControlResult(ok=False, reason_code=f"unknown_project:{project_id}")
    return ControlResult(ok=True, data={"manifest": generate_export(self.store, project_id=project_id)})

# raiker/api/routes_dashboard.py
@router.post("/api/projects/{project_id}/export")
async def export_project(...):
    result = _service(request).export_project(project_id, auth_data[0].principal_id)
    if not result.ok:
        raise HTTPException(status_code=404 if result.reason_code.startswith("unknown_project:") else 403, detail={"ok": False, "reason_code": result.reason_code})
    manifest = result.data["manifest"]
    if manifest.export_path is None:
        return Response(content=b"", media_type="application/x-ndjson", headers={"Content-Disposition": f'attachment; filename="{project_id}.jsonl"'})
    return FileResponse(manifest.export_path, media_type="application/x-ndjson", filename=f"{project_id}.jsonl")
```

Import `FileResponse` and `Response`; do not serialize or return `manifest.export_path`.

- [ ] **Step 4: Run focused tests to verify they pass**

Run: `python -m pytest tests/test_projects.py tests/test_phase_5_audit_export.py -q`

Expected: PASS; authenticated requests download JSONL, unknown projects return 404, and the response does not disclose a workspace path.

- [ ] **Step 5: Commit**

```bash
git add raiker/control/dashboard.py raiker/api/routes_dashboard.py tests/test_projects.py
```

### Task 3: Expose The Explicit Project Export Control

**Files:**
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/lib/views/ProjectsView.svelte`
- Test: `apps/web/src/lib/views/ProjectsView.test.ts`

**Security flag:** `security`

**Does NOT cover:** Browser persistence of exports, automatic export, or an unredacted mode.

- [ ] **Step 1: Write a failing view test**

```typescript
it("requests a project-only export from the detail view", async () => {
  const mock = stubFetch({
    "GET /api/projects": { projects: [project({})], active_project_id: null },
    "GET /api/projects/tree": [],
    "GET /api/projects/proj_1": { project: project({}), sessions: [], checkpoints: [], context: { instructions: "", attachment_ids: [], memory_enabled: false } },
    "POST /api/projects/proj_1/export": new Blob([""], { type: "application/x-ndjson" }),
  });
  render(ProjectsView);
  await screen.findByText("Details");
  await fireEvent.click(screen.getByText("Details"));
  await fireEvent.click(await screen.findByText("Export project"));
  await waitFor(() => expect(mock.mock.calls.some((call) => String(call[0]).includes("/api/projects/proj_1/export") && call[1]?.method === "POST")).toBe(true));
});
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `npm test -- --run src/lib/views/ProjectsView.test.ts`

Working directory: `apps/web`

Expected: FAIL because the export control is absent.

- [ ] **Step 3: Implement the authenticated download and explicit control**

```typescript
// apps/web/src/lib/api.ts
async function downloadProjectExport(id: string): Promise<void> {
  const response = await fetch(`/api/projects/${encodeURIComponent(id)}/export`, {
    method: "POST",
    headers: token === null ? undefined : { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new ApiError(response.status, null, `Request failed: ${response.status}`);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = `${id}.jsonl`;
  link.click();
  URL.revokeObjectURL(url);
}

// apps/web/src/lib/views/ProjectsView.svelte
<button type="button" class="btn btn-ghost btn-sm" onclick={() => void exportProject(detail.project.project_id)}>
  Export project
</button>
```

Add an `exportError` state and render it with `role="alert"`; configure the test with `URL.createObjectURL`, `URL.revokeObjectURL`, and an anchor-click stub.

- [ ] **Step 4: Run focused web checks to verify they pass**

Run: `npm run check; npm test -- --run src/lib/views/ProjectsView.test.ts`

Working directory: `apps/web`

Expected: PASS with no Svelte type errors and the export button issues one authenticated POST.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/lib/api.ts apps/web/src/lib/views/ProjectsView.svelte apps/web/src/lib/views/ProjectsView.test.ts
```

### Task 4: Record The Delivered Slice And Verify The Repository

**Files:**
- Modify: `docs/HANDOFF.md`
- Modify: `docs/IMPLEMENTATION_STATUS.md`
- Modify: `project-map.md`

**Security flag:** `none`

- [ ] **Step 1: Update documentation to say project-only export is a redacted, direct-project audit export and reminders remain deferred.**

- [ ] **Step 2: Refresh `project-map.md` with the final commit hash and new export hot files.**

- [ ] **Step 3: Run the required verification suite**

Run: `python -m pytest; ruff check .; python scripts/validate_repo_truthfulness.py; python scripts/validate_documentation_truthfulness.py`

Run: `npm run check; npm run lint; npm test -- --run; npm run build`

Working directory for web commands: `apps/web`

Expected: every command exits 0.

- [ ] **Step 4: Review the final change set and commit the documentation**

```bash
git status --short
```

## Self-Review

- Spec coverage: Tasks 1-3 implement exact direct-project scope, mandatory redaction, human authentication, download behavior, and the explicit UI. Task 4 records the delivered state and runs all handoff-required checks.
- Completeness scan: no deferred implementation or test steps remain.
- Type consistency: all layers use `project_id`; the service returns a `ControlResult` containing the existing `ExportManifest` only for route-local use.
- Scope check: scheduled reminders, descendants, attachments, memory, and generic archive import remain excluded.
