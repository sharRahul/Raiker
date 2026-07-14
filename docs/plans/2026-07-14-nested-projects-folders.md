# Nested Projects/Folders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-optimized:subagent-driven-development (recommended) or superpowers-optimized:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add arbitrary-depth folder nesting to projects with context inheritance, soft-delete (archive), and human-only hard-delete with orphanage cascade.

**Architecture:** Hybrid adjacency list + materialized path on `projects` table. `parent_id` (FK, ON DELETE SET NULL) + `path` (e.g. '/1/4/12/') auto-synced by trigger. Context inheritance via single ancestor-query at session startup. Archive = AI autonomous UPDATE; Delete = human transaction (orphanage cascade + hard delete). No new gates/policies/executors.

**Tech Stack:** Python (SQLite), FastAPI, Svelte, pytest, vitest

**Assumptions:**
- SQLite 3.38+ supports recursive CTEs and partial indexes — required for path queries and active-tree index
- Existing `projects` table has no `parent_id`/`path` — migration adds defaults (`NULL`, `'/'`)
- `project_contexts` unchanged; context merge logic runs in `DashboardService.get_session_context`
- Sessions keep `project_id` FK unchanged — points to leaf folder or root project
- Archive is AI tool; delete is human-gated (existing `X-Project-Delete-Confirm` pattern)

---

## File Structure

| File | Responsibility |
|------|----------------|
| `raiker/storage/migrations.py` | New migration `PROJECTS_NESTING_MIGRATION_ID` with DDL + trigger |
| `raiker/storage/sqlite.py` | Storage methods: `list_project_tree`, `move_project`, `archive_project`, `delete_project_with_orphanage`, `get_ancestor_contexts` |
| `raiker/control/dashboard.py` | DashboardService: `list_project_tree`, `move_project`, `archive_project`, `delete_project`, `get_session_context` (adds ancestor merge) |
| `raiker/api/schemas.py` | `MoveProjectRequest`, `ArchiveProjectRequest` (empty body) |
| `raiker/api/routes_dashboard.py` | `POST /api/projects/move`, `PUT /api/projects/{id}/archive`, `DELETE /api/projects/{id}` (reuses confirm header) |
| `apps/web/src/lib/api.ts` | `api.moveProject`, `api.archiveProject`, `api.deleteProject` |
| `apps/web/src/lib/apiTypes.ts` | Add `parent_id`, `path`, `is_archived`, `archived_at` to `ProjectSummary`/`ProjectDetail` |
| `apps/web/src/lib/views/ProjectsView.svelte` | Tree render (recursive component), expand/collapse, archive/delete actions |
| `tests/test_nested_projects.py` | Backend: CRUD, tree, context merge, archive, delete, isolation |
| `tests/test_api_contract_schemas.py` | Guard new fields on `ProjectSummary`/`ProjectDetail` |
| `apps/web/src/lib/views/ProjectsView.test.ts` | Web: tree render, expand/collapse, archive/delete actions |

---

## Task List

### Task 1: Migration — Add Nesting Columns + Trigger

**Files:**
- Create: `raiker/storage/migrations.py` (modify)
- Test: `tests/test_nested_projects.py` (new)

**Security flag:** `none`

**Does NOT cover:** No data migration for existing projects — defaults handle it.

- [ ] **Step 1: Write failing test**

```python
# tests/test_nested_projects.py (excerpt)
def test_migration_creates_nesting_columns_and_trigger(workspace: Path) -> None:
    store = SQLiteStore(workspace)
    # Verify columns exist
    cols = {row["name"] for row in store.connect().execute("PRAGMA table_info(projects)").fetchall()}
    assert "parent_id" in cols
    assert "path" in cols
    assert "is_archived" in cols
    assert "archived_at" in cols
    # Verify trigger exists
    triggers = {row["name"] for row in store.connect().execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall()}
    assert "sync_project_path_after_update" in triggers
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_nested_projects.py::test_migration_creates_nesting_columns_and_trigger -xvs`
Expected: FAIL (columns/trigger missing)

- [ ] **Step 3: Implement migration**

```python
# raiker/storage/migrations.py
PROJECTS_NESTING_MIGRATION_ID = "RAIKER-1012-projects-nesting"

PROJECTS_NESTING_SQL = """
ALTER TABLE projects ADD COLUMN parent_id TEXT REFERENCES projects(project_id) ON DELETE SET NULL;
ALTER TABLE projects ADD COLUMN path TEXT NOT NULL DEFAULT '/';
ALTER TABLE projects ADD COLUMN is_archived INTEGER NOT NULL DEFAULT 0;
ALTER TABLE projects ADD COLUMN archived_at TEXT;

CREATE INDEX idx_projects_parent ON projects(parent_id);
CREATE INDEX idx_active_projects_path ON projects(path) WHERE is_archived = 0;
CREATE INDEX idx_all_projects_path ON projects(path);

CREATE TRIGGER sync_project_path_after_update
AFTER UPDATE OF parent_id ON projects
BEGIN
  UPDATE projects SET path = (
    SELECT COALESCE(p.path || new.parent_id || '/', '/')
    FROM projects p WHERE p.project_id = new.parent_id
  ) WHERE project_id = new.project_id;

  UPDATE projects SET path = (
    SELECT COALESCE(pp.path || projects.parent_id || '/', '/')
    FROM projects pp WHERE pp.project_id = projects.parent_id
  ) WHERE path LIKE (SELECT path FROM projects WHERE project_id = new.project_id) || '%' AND project_id != new.project_id;
END;
"""

# In SQLiteStore._run_migrations: add after PROJECTS_MIGRATION_ID
self._apply_migration(PROJECTS_NESTING_MIGRATION_ID, PROJECTS_NESTING_SQL, connection)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_nested_projects.py::test_migration_creates_nesting_columns_and_trigger -xvs`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add raiker/storage/migrations.py tests/test_nested_projects.py
git commit -m "migration: add project nesting columns + path trigger"
```

---

### Task 2: Storage — Tree Queries + Move/Archive/Delete

**Files:**
- Modify: `raiker/storage/sqlite.py`
- Test: `tests/test_nested_projects.py`

**Security flag:** `security` — input validation on path traversal, cycle prevention on move

**Does NOT cover:** No automatic session reassignment on move; sessions keep their `project_id`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_nested_projects.py
class TestProjectTreeQueries:
    def test_list_project_tree_returns_nested_structure(self, store: SQLiteStore, workspace: Path) -> None:
        store.create_project("p1", "Root", "projects/root")
        store.create_project("p2", "Child", "projects/root/child", parent_id="p1")
        store.create_project("p3", "Grandchild", "projects/root/child/gc", parent_id="p2")
        tree = store.list_project_tree()
        assert len(tree) == 1
        assert tree[0]["project_id"] == "p1"
        assert len(tree[0]["children"]) == 1
        assert tree[0]["children"][0]["project_id"] == "p2"
        assert len(tree[0]["children"][0]["children"]) == 1

    def test_list_project_tree_excludes_archived_by_default(self, store: SQLiteStore, workspace: Path) -> None:
        store.create_project("p1", "Root", "projects/root")
        store.create_project("p2", "Child", "projects/root/child", parent_id="p1")
        store.archive_project("p1")  # archives subtree
        tree = store.list_project_tree()
        assert tree == []

class TestProjectMove:
    def test_move_project_updates_path_and_descendants(self, store: SQLiteStore, workspace: Path) -> None:
        store.create_project("p1", "Root", "projects/root")
        store.create_project("p2", "Child", "projects/root/child", parent_id="p1")
        store.move_project("p2", None)  # move to root
        assert store.load_project("p2")["parent_id"] is None
        assert store.load_project("p2")["path"] == "/"

    def test_move_prevents_cycle(self, store: SQLiteStore, workspace: Path) -> None:
        store.create_project("p1", "Root", "projects/root")
        store.create_project("p2", "Child", "projects/root/child", parent_id="p1")
        assert not store.move_project("p1", "p2")  # would create cycle
        assert store.load_project("p1")["parent_id"] is None

class TestProjectArchive:
    def test_archive_project_archives_subtree(self, store: SQLiteStore, workspace: Path) -> None:
        store.create_project("p1", "Root", "projects/root")
        store.create_project("p2", "Child", "projects/root/child", parent_id="p1")
        store.archive_project("p1")
        assert store.load_project("p1")["is_archived"] == 1
        assert store.load_project("p2")["is_archived"] == 1

    def test_archive_is_idempotent(self, store: SQLiteStore, workspace: Path) -> None:
        store.create_project("p1", "Root", "projects/root")
        store.archive_project("p1")
        store.archive_project("p1")  # second call no-op
        assert store.load_project("p1")["is_archived"] == 1

class TestProjectDeleteWithOrphanage:
    def test_delete_project_orphans_children_and_hard_deletes_target(self, store: SQLiteStore, workspace: Path) -> None:
        store.create_project("p1", "Root", "projects/root")
        store.create_project("p2", "Child", "projects/root/child", parent_id="p1")
        store.delete_project_with_orphanage("p1")
        assert store.load_project("p1") is None
        child = store.load_project("p2")
        assert child is not None
        assert child["parent_id"] is None
        assert child["path"].startswith("orphaned/")
        assert child["is_archived"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_nested_projects.py -xvs`
Expected: FAIL (methods missing)

- [ ] **Step 3: Implement storage methods**

```python
# raiker/storage/sqlite.py

def list_project_tree(self, include_archived: bool = False) -> list[dict[str, Any]]:
    """Return nested tree of projects (active by default)."""
    where = "" if include_archived else "WHERE is_archived = 0"
    with self.connect() as conn:
        rows = conn.execute(f"""
            SELECT * FROM projects {where} ORDER BY path, created_at
        """).fetchall()
    # Build tree from flat list using path
    nodes = {row["project_id"]: {**dict(row), "children": []} for row in rows}
    roots = []
    for row in rows:
        node = nodes[row["project_id"]]
        if row["parent_id"] is None:
            roots.append(node)
        elif row["parent_id"] in nodes:
            nodes[row["parent_id"]]["children"].append(node)
    return roots

def move_project(self, project_id: str, new_parent_id: str | None) -> bool:
    """Move project (and subtree) under new parent. Returns False if cycle or not found."""
    with self.connect() as conn:
        # Check existence
        row = conn.execute("SELECT project_id, path FROM projects WHERE project_id = ?", (project_id,)).fetchone()
        if not row:
            return False
        old_path = row["path"]
        # Cycle check: new_parent must not be in this project's subtree
        if new_parent_id:
            new_parent_row = conn.execute("SELECT path FROM projects WHERE project_id = ?", (new_parent_id,)).fetchone()
            if not new_parent_row:
                return False
            new_parent_path = new_parent_row["path"]
            if new_parent_path.startswith(old_path):
                return False  # would create cycle
        # Update parent_id; trigger syncs path + descendants
        conn.execute(
            "UPDATE projects SET parent_id = ?, updated_at = ? WHERE project_id = ?",
            (new_parent_id, utc_now(), project_id),
        )
    return True

def archive_project(self, project_id: str) -> bool:
    """Soft-archive project and all descendants. Idempotent."""
    with self.connect() as conn:
        row = conn.execute("SELECT path FROM projects WHERE project_id = ?", (project_id,)).fetchone()
        if not row:
            return False
        path = row["path"]
        now = utc_now()
        conn.execute(
            "UPDATE projects SET is_archived = 1, archived_at = ?, updated_at = ? WHERE path LIKE ?",
            (now, now, path + "%"),
        )
    return True

def delete_project_with_orphanage(self, project_id: str) -> bool:
    """Hard-delete project; archive descendants + reparent to NULL with orphaned/ path."""
    with self.connect() as conn:
        row = conn.execute("SELECT path FROM projects WHERE project_id = ?", (project_id,)).fetchone()
        if not row:
            return False
        path = row["path"]
        now = utc_now()
        # 1) Archive descendants (excluding target)
        conn.execute(
            "UPDATE projects SET is_archived = 1, archived_at = ?, parent_id = NULL, path = 'orphaned/' || project_id || '/', updated_at = ? WHERE path LIKE ? AND project_id != ?",
            (now, now, path + "%", project_id),
        )
        # 2) Hard delete target (children already reparented via ON DELETE SET NULL)
        conn.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
        # 3) Clean related tables (cascade mirrors delete_project)
        conn.execute("DELETE FROM project_contexts WHERE project_id = ?", (project_id,))
        # Note: sessions keep project_id FK pointing to now-deleted target — context lookup naturally returns empty
    return True

def get_ancestor_contexts(self, project_id: str) -> list[dict[str, Any]]:
    """Return context rows for all active ancestors of project_id, ordered root→leaf."""
    with self.connect() as conn:
        # Get the path of the target
        target = conn.execute("SELECT path FROM projects WHERE project_id = ?", (project_id,)).fetchone()
        if not target:
            return []
        path = target["path"]
        # Ancestors are projects whose project_id appears in the path segments
        # path format: '/1/4/12/' — segments between slashes
        # Use a recursive CTE or simple LIKE match
        rows = conn.execute("""
            SELECT pc.* FROM project_contexts pc
            JOIN projects p ON p.project_id = pc.project_id
            WHERE ? LIKE '%' || p.project_id || '/%' AND p.is_archived = 0
            ORDER BY LENGTH(p.path) ASC
        """, (path,)).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_nested_projects.py -xvs`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add raiker/storage/sqlite.py tests/test_nested_projects.py
git commit -m "storage: project tree queries, move, archive, delete with orphanage"
```

---

### Task 3: DashboardService — Tree Listing, Move, Archive, Delete, Context Merge

**Files:**
- Modify: `raiker/control/dashboard.py`
- Test: `tests/test_nested_projects.py`

**Security flag:** `security` — human-only checks for delete/archive, visibility isolation

**Does NOT cover:** No AI autonomous delete; archive is AI tool, delete is human-only.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_nested_projects.py
class TestDashboardServiceNested:
    def test_list_project_tree_active_only(self, service: DashboardService, workspace: Path) -> None:
        service.create_project("p1", "Root", "principal_test")
        service.create_project("p2", "Child", "principal_test", parent_id="p1")
        service.archive_project("p1")  # archives subtree
        tree = service.list_project_tree()
        assert tree == []

    def test_move_project_human_only(self, service: DashboardService, workspace: Path) -> None:
        service.create_project("p1", "Root", "principal_test")
        service.create_project("p2", "Child", "principal_test", parent_id="p1")
        # AI principal denied
        from raiker.contracts.ids import utc_now
        with service.store.connect() as conn:
            conn.execute("""INSERT OR IGNORE INTO principals (principal_id, principal_type, display_name, role_ids, domain_scopes, max_runtime_mode, created_at, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ("ai_principal", "ai_agent", "AI", "[]", "[]", "development_preview", utc_now(), 1))
        result = service.move_project("p2", None, "ai_principal")
        assert not result.ok
        assert result.reason_code == "not_authorized_human"

    def test_delete_project_human_only_requires_confirmation(self, service: DashboardService, workspace: Path) -> None:
        service.create_project("p1", "Root", "principal_test")
        service.create_project("p2", "Child", "principal_test", parent_id="p1")
        result = service.delete_project("p1", OWNER)  # no confirm -> fail
        assert not result.ok
        assert result.reason_code == "project_delete_confirmation_required"

    def test_get_session_context_merges_ancestor_contexts(self, service: DashboardService, workspace: Path) -> None:
        service.create_project("p1", "Root", "principal_test")
        service.create_project("p2", "Child", "principal_test", parent_id="p1")
        # Root has instructions + memory enabled
        service.save_project_context("p1", instructions="Root instructions", attachment_ids=[], memory_enabled=True)
        # Child has own instructions + memory disabled (overrides)
        service.save_project_context("p2", instructions="Child instructions", attachment_ids=[], memory_enabled=False)
        # Session assigned to p2
        service.store.create_session("sess1", str(workspace), project_id="p2")
        context = service.get_session_context("sess1")
        # Merge: root instructions + child instructions (child wins on overlap), union attachments, memory_enabled=False
        assert "Root instructions" in context["instructions"]
        assert "Child instructions" in context["instructions"]
        assert context["memory_enabled"] is False
```

- [ ] **Step 2: Run tests to verify fail**

Run: `python -m pytest tests/test_nested_projects.py -xvs`
Expected: FAIL

- [ ] **Step 3: Implement DashboardService methods**

```python
# raiker/control/dashboard.py

def list_project_tree(self, include_archived: bool = False) -> list[dict[str, Any]]:
    return self.store.list_project_tree(include_archived=include_archived)

def move_project(
    self,
    project_id: str,
    new_parent_id: str | None,
    acting_principal_id: str | None,
) -> ControlResult:
    principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
    if principal is None:
        return ControlResult(ok=False, reason_code="principal_not_resolved")
    if principal.principal_type != PrincipalType.HUMAN:
        return ControlResult(ok=False, reason_code="not_authorized_human")
    if not self.store.move_project(project_id, new_parent_id):
        return ControlResult(ok=False, reason_code=f"unknown_or_invalid_move:{project_id}")
    return ControlResult(ok=True, data={"project_id": project_id, "parent_id": new_parent_id})

def archive_project(self, project_id: str, acting_principal_id: str | None) -> ControlResult:
    """AI-autonomous archive (soft). No confirmation required."""
    principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
    if principal is None:
        return ControlResult(ok=False, reason_code="principal_not_resolved")
    if not self.store.archive_project(project_id):
        return ControlResult(ok=False, reason_code=f"unknown_project:{project_id}")
    return ControlResult(ok=True, data={"project_id": project_id, "archived": True})

def delete_project(
    self,
    project_id: str,
    acting_principal_id: str | None,
    confirmed: bool = False,
) -> ControlResult:
    """Human-only hard delete with orphanage cascade. Requires confirmed=True."""
    principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
    if principal is None:
        return ControlResult(ok=False, reason_code="principal_not_resolved")
    if principal.principal_type != PrincipalType.HUMAN:
        return ControlResult(ok=False, reason_code="not_authorized_human")
    if not confirmed:
        return ControlResult(ok=False, reason_code="project_delete_confirmation_required")
    if not self.store.delete_project_with_orphanage(project_id):
        return ControlResult(ok=False, reason_code=f"unknown_project:{project_id}")
    return ControlResult(ok=True, data={"project_id": project_id})

def get_session_context(self, session_id: str) -> dict[str, Any]:
    """Get merged context for a session's project (includes ancestors)."""
    row = self.store.load_session(session_id)
    if not row:
        return {"instructions": "", "attachment_ids": [], "memory_enabled": False}
    project_id = row.get("project_id")
    if not project_id:
        return {"instructions": "", "attachment_ids": [], "memory_enabled": False}
    # Get ancestor contexts (active only)
    ancestor_contexts = self.store.get_ancestor_contexts(project_id)
    # Merge
    merged_instructions = []
    merged_attachments: list[str] = []
    merged_memory_enabled = True
    for ctx in ancestor_contexts:
        if ctx.get("instructions"):
            merged_instructions.append(ctx["instructions"])
        for aid in ctx.get("attachment_ids_json", "[]"):
            pass  # handle JSON parse
        # memory_enabled: if any ancestor has False, result is False unless leaf explicitly True
        if not ctx.get("memory_enabled", True):
            merged_memory_enabled = False
    # Leaf context wins on instructions (prepend root, append leaf)
    leaf_ctx = self.store.load_project_context(project_id)
    if leaf_ctx.get("instructions"):
        merged_instructions.append(leaf_ctx["instructions"])
    if leaf_ctx.get("memory_enabled") is True:
        merged_memory_enabled = True  # leaf can override
    return {
        "instructions": "\n\n".join(merged_instructions),
        "attachment_ids": list(dict.fromkeys(merged_attachments)),  # dedupe
        "memory_enabled": merged_memory_enabled,
    }
```

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_nested_projects.py -xvs`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add raiker/control/dashboard.py tests/test_nested_projects.py
git commit -m "service: project tree, move, archive, delete, context merge"
```

---

### Task 4: API Schemas + Routes

**Files:**
- Modify: `raiker/api/schemas.py`, `raiker/api/routes_dashboard.py`
- Test: `tests/test_nested_projects.py` (API tests)

**Security flag:** `security` — input validation, auth, visibility checks

**Does NOT cover:** No batch operations; single project per request.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_nested_projects.py
class TestProjectNestingApi:
    @pytest.fixture
    def app(self, workspace: Path) -> FastAPI:
        return create_app(workspace)

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        return TestClient(app)

    def _headers(self, client: TestClient) -> dict[str, str]:
        resp = client.post("/api/auth/session", json={"as_principal": None})
        assert resp.status_code == 200
        return {"Authorization": f"Bearer {resp.json()['token']}"}

    def test_create_project_with_parent(self, client: TestClient, workspace: Path) -> None:
        h = self._headers(client)
        r1 = client.post("/api/projects", json={"name": "Root"}, headers=h)
        assert r1.status_code == 200
        pid1 = r1.json()["data"]["project_id"]
        r2 = client.post("/api/projects", json={"name": "Child", "parent_id": pid1}, headers=h)
        assert r2.status_code == 200
        assert r2.json()["data"]["parent_id"] == pid1

    def test_move_project(self, client: TestClient, workspace: Path) -> None:
        h = self._headers(client)
        r1 = client.post("/api/projects", json={"name": "Root"}, headers=h)
        pid1 = r1.json()["data"]["project_id"]
        r2 = client.post("/api/projects", json={"name": "Child", "parent_id": pid1}, headers=h)
        pid2 = r2.json()["data"]["project_id"]
        # Move to root
        mv = client.post("/api/projects/move", json={"project_id": pid2, "parent_id": None}, headers=h)
        assert mv.status_code == 200
        # Verify via list
        lst = client.get("/api/projects", headers=h).json()
        child = next(p for p in lst["projects"] if p["project_id"] == pid2)
        assert child["parent_id"] is None

    def test_archive_project_ai_allowed(self, client: TestClient, workspace: Path) -> None:
        h = self._headers(client)
        r = client.post("/api/projects", json={"name": "Root"}, headers=h)
        pid = r.json()["data"]["project_id"]
        arch = client.put(f"/api/projects/{pid}/archive", json={}, headers=h)
        assert arch.status_code == 200
        lst = client.get("/api/projects", headers=h).json()
        assert all(p["project_id"] != pid for p in lst["projects"])

    def test_delete_project_requires_confirm(self, client: TestClient, workspace: Path) -> None:
        h = self._headers(client)
        r = client.post("/api/projects", json={"name": "Root"}, headers=h)
        pid = r.json()["data"]["project_id"]
        del_resp = client.delete(f"/api/projects/{pid}", headers=h)
        assert del_resp.status_code == 409
        assert del_resp.json()["detail"]["reason_code"] == "project_delete_confirmation_required"

    def test_delete_project_with_confirm_cascades_orphanage(self, client: TestClient, workspace: Path) -> None:
        h = self._headers(client)
        r1 = client.post("/api/projects", json={"name": "Root"}, headers=h)
        pid1 = r1.json()["data"]["project_id"]
        r2 = client.post("/api/projects", json={"name": "Child", "parent_id": pid1}, headers=h)
        pid2 = r2.json()["data"]["project_id"]
        del_resp = client.delete(f"/api/projects/{pid1}", headers={**h, "X-Project-Delete-Confirm": pid1})
        assert del_resp.status_code == 200
        # Child still exists but orphaned/archived
        lst = client.get("/api/projects", headers=h).json()
        child = next(p for p in lst["projects"] if p["project_id"] == pid2)
        assert child["parent_id"] is None
        assert child["is_archived"] == 1
```

- [ ] **Step 2: Run tests to verify fail**

Run: `python -m pytest tests/test_nested_projects.py::TestProjectNestingApi -xvs`
Expected: FAIL

- [ ] **Step 3: Implement schemas + routes**

```python
# raiker/api/schemas.py
class CreateProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    parent_id: str | None = None

class MoveProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str
    parent_id: str | None

class ArchiveProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass  # empty body
```

```python
# raiker/api/routes_dashboard.py
from raiker.api.schemas import CreateProjectRequest, MoveProjectRequest, ArchiveProjectRequest

# In create_project: add parent_id to CreateProjectRequest and pass to service
@router.post("/api/projects")
async def create_project(
    body: CreateProjectRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    ...
    result = _service(request).create_project(body.name, session.principal_id, parent_id=body.parent_id)
    ...

# New routes
@router.post("/api/projects/move")
async def move_project(
    body: MoveProjectRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    result = _service(request).move_project(body.project_id, body.parent_id, auth_data[0].principal_id)
    if not result.ok:
        raise HTTPException(status_code=403, detail={"ok": False, "reason_code": result.reason_code})
    return {"ok": True, **result.data}

@router.put("/api/projects/{project_id}/archive")
async def archive_project(
    project_id: str,
    body: ArchiveProjectRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    result = _service(request).archive_project(project_id, auth_data[0].principal_id)
    if not result.ok:
        raise HTTPException(status_code=403, detail={"ok": False, "reason_code": result.reason_code})
    return {"ok": True, **result.data}

@router.delete("/api/projects/{project_id}")
async def delete_project(
    project_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
    x_project_delete_confirm: str | None = Header(default=None),
) -> dict[str, Any]:
    confirmed = x_project_delete_confirm == project_id
    result = _service(request).delete_project(project_id, auth_data[0].principal_id, confirmed)
    if not result.ok:
        raise HTTPException(status_code=409 if result.reason_code == "project_delete_confirmation_required" else 403,
                            detail={"ok": False, "reason_code": result.reason_code})
    return {"ok": True, **result.data}
```

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_nested_projects.py::TestProjectNestingApi -xvs`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add raiker/api/schemas.py raiker/api/routes_dashboard.py tests/test_nested_projects.py
git commit -m "api: project nesting routes (move, archive, delete with orphanage)"
```

---

### Task 5: API Contract Schema Guards

**Files:**
- Modify: `tests/test_api_contract_schemas.py`

**Security flag:** `none`

**Does NOT cover:** No new schemas — guards existing response shapes.

- [ ] **Step 1: Add contract assertions**

```python
# tests/test_api_contract_schemas.py
PROJECT_SUMMARY = {
    "project_id", "name", "root_subpath", "created_at", "session_count", "selected",
    "parent_id", "path", "is_archived", "archived_at"
}

PROJECT_DETAIL = PROJECT_SUMMARY | {"context", "sessions", "checkpoints"}
```

- [ ] **Step 2: Run and verify**

Run: `python -m pytest tests/test_api_contract_schemas.py -xvs`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_api_contract_schemas.py
git commit -m "test: guard nested project fields in API contracts"
```

---

### Task 6: Web Types + API Client

**Files:**
- Modify: `apps/web/src/lib/apiTypes.ts`, `apps/web/src/lib/api.ts`

**Security flag:** `none`

**Does NOT cover:** No new UI components yet.

- [ ] **Step 1: Update types**

```typescript
// apps/web/src/lib/apiTypes.ts
export interface ProjectSummary {
  // ...existing
  parent_id: string | null;
  path: string;
  is_archived: boolean;
  archived_at: string | null;
}

export interface ProjectDetail {
  project: ProjectSummary;
  context: ProjectContext;
  sessions: SessionSummary[];
  checkpoints: CheckpointSummary[];
}
```

- [ ] **Step 2: Update API client**

```typescript
// apps/web/src/lib/api.ts
export const api = {
  // ...existing
  moveProject: (projectId: string, parentId: string | null) =>
    request<{ ok: boolean; project_id: string; parent_id: string | null }>(
      "/api/projects/move",
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project_id: projectId, parent_id: parentId }) }
    ),
  archiveProject: (projectId: string) =>
    request<{ ok: boolean; project_id: string; archived: boolean }>(
      `/api/projects/${encodeURIComponent(projectId)}/archive`,
      { method: "PUT", headers: { "Content-Type": "application/json" }, body: "{}" }
    ),
  deleteProject: (projectId: string, confirmed = false) =>
    request<{ ok: boolean; project_id: string }>(
      `/api/projects/${encodeURIComponent(projectId)}`,
      { method: "DELETE", headers: confirmed ? { "X-Project-Delete-Confirm": projectId } : undefined }
    ),
}
```

- [ ] **Step 3: Verify build**

Run: `cd apps/web && npm run check && npm run lint`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/lib/apiTypes.ts apps/web/src/lib/api.ts
git commit -m "web: types + api client for nested projects"
```

---

### Task 7: ProjectsView Tree UI

**Files:**
- Modify: `apps/web/src/lib/views/ProjectsView.svelte`
- Test: `apps/web/src/lib/views/ProjectsView.test.ts`

**Security flag:** `none`

**Does NOT cover:** No drag-drop; create via existing form, move via context menu or dedicated page (MVP: create with parent_id, move via API only).

- [ ] **Step 1: Write failing tests**

```typescript
// apps/web/src/lib/views/ProjectsView.test.ts
import { render, screen, waitFor, fireEvent } from "@testing-library/svelte";
import ProjectsView from "./ProjectsView.svelte";
import { stubFetch } from "../test-helpers";

const PROJECTS_LIST = {
  "GET /api/projects": {
    projects: [
      { project_id: "p1", name: "Root", root_subpath: "projects/root", created_at: "2026-01-01T00:00:00Z", session_count: 1, selected: true, parent_id: null, path: "/", is_archived: false, archived_at: null },
      { project_id: "p2", name: "Child", root_subpath: "projects/root/child", created_at: "2026-01-02T00:00:00Z", session_count: 0, selected: false, parent_id: "p1", path: "/p1/", is_archived: false, archived_at: null },
    ],
    active_project_id: "p1",
  },
  "PUT /api/projects/p1/archive": { ok: true, project_id: "p1", archived: true },
  "DELETE /api/projects/p1": { ok: true, project_id: "p1" },
};

describe("ProjectsView tree", () => {
  it("renders nested tree with expand/collapse", async () => {
    stubFetch(PROJECTS_LIST);
    render(ProjectsView);
    await waitFor(() => expect(screen.getByText("Root")).toBeInTheDocument());
    expect(screen.getByText("Child")).toBeInTheDocument();
    // Root has expand button, Child is visible
    const expandBtn = screen.getByRole("button", { name: /expand root/i });
    await fireEvent.click(expandBtn);
    // Collapse hides child
    const collapseBtn = screen.getByRole("button", { name: /collapse root/i });
    await fireEvent.click(collapseBtn);
    expect(screen.queryByText("Child")).not.toBeInTheDocument();
  });

  it("archives project via archive button", async () => {
    const fetchMock = stubFetch(PROJECTS_LIST);
    render(ProjectsView);
    await waitFor(() => expect(screen.getByText("Root")).toBeInTheDocument());
    const archiveBtn = screen.getByRole("button", { name: /archive root/i });
    await fireEvent.click(archiveBtn);
    await waitFor(() => {
      const putCall = fetchMock.mock.calls.find(c => String(c[0]) === "/api/projects/p1/archive" && c[1]?.method === "PUT");
      expect(putCall).toBeDefined();
    });
  });

  it("deletes project with confirmation", async () => {
    const fetchMock = stubFetch(PROJECTS_LIST);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(ProjectsView);
    await waitFor(() => expect(screen.getByText("Root")).toBeInTheDocument());
    const deleteBtn = screen.getByRole("button", { name: /delete root/i });
    await fireEvent.click(deleteBtn);
    await waitFor(() => {
      const delCall = fetchMock.mock.calls.find(c => String(c[0]) === "/api/projects/p1" && c[1]?.method === "DELETE");
      expect(delCall).toBeDefined();
      const headers = delCall![1]!.headers as Headers;
      expect(headers.get("X-Project-Delete-Confirm")).toBe("p1");
    });
  });
});
```

- [ ] **Step 2: Run tests to verify fail**

Run: `cd apps/web && npm test -- --run src/lib/views/ProjectsView.test.ts`
Expected: FAIL

- [ ] **Step 3: Implement tree UI**

```svelte
<!-- apps/web/src/lib/views/ProjectsView.svelte -->
<script lang="ts">
  // ...existing imports
  import { api, ApiError } from "../api";
  import type { ProjectSummary } from "../apiTypes";
  import { relativeTime, shortId } from "../format";

  // New: recursive tree component
  function ProjectNode({ project, level = 0 }: { project: ProjectSummary; level: number }) {
    let expanded = $state(true);
    const children = $derived(projectsList.filter(p => p.parent_id === project.project_id));
    const hasChildren = children.length > 0;

    async function handleArchive() {
      if (!confirm(`Archive "${project.name}" and all descendants?`)) return;
      try { await api.archiveProject(project.project_id); await load(); }
      catch (e) { /* error handling */ }
    }
    async function handleDelete() {
      if (!confirm(`Permanently delete "${project.name}" and orphan children?`)) return;
      try { await api.deleteProject(project.project_id, true); await load(); }
      catch (e) { /* error handling */ }
    }
  </script>

  <!-- In main view: replace flat grid with tree -->
  {#if list === null}...{:else if list.projects.length === 0}...{:else}
    <div class="project-tree">
      {#each list.projects.filter(p => p.parent_id === null) as root (root.project_id)}
        <ProjectNode project={root} />
      {/each}
    </div>
  {/if}
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd apps/web && npm test -- --run src/lib/views/ProjectsView.test.ts`
Expected: PASS

- [ ] **Step 5: Verify build**

Run: `cd apps/web && npm run check && npm run lint && npm run build`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/lib/views/ProjectsView.svelte apps/web/src/lib/views/ProjectsView.test.ts
git commit -m "web: ProjectsView tree UI with archive/delete"
```

---

### Task 8: Full Verification

**Files:** (all modified)

**Security flag:** `none`

- [ ] **Step 1: Run backend validators**

```bash
python -m pytest tests/test_nested_projects.py -xvs
python -m pytest tests/test_api_contract_schemas.py -xvs
ruff check .
python -m mypy raiker tests
python scripts/validate_phase_status.py
python scripts/validate_repo_truthfulness.py
python scripts/validate_runtime_enablement_readiness.py
python scripts/validate_local_single_user_runtime.py
python scripts/validate_documentation_truthfulness.py
```

- [ ] **Step 2: Run web validators**

```bash
cd apps/web
npm run check
npm run lint
npm test -- --run
npm run build
```

- [ ] **Step 3: Commit all if green**

```bash
git add -A
git commit -m "feat: nested projects/folders with archive + orphanage delete"
git push origin main
```

---

## Self-Review

| Spec Section | Plan Task |
|--------------|-----------|
| Storage: parent_id, path, is_archived, archived_at + trigger | Task 1 |
| Storage: list_project_tree, move_project (cycle check), archive_project, delete_project_with_orphanage, get_ancestor_contexts | Task 2 |
| Service: list_project_tree, move_project, archive_project, delete_project, get_session_context (merge) | Task 3 |
| API: CreateProjectRequest.parent_id, MoveProjectRequest, ArchiveProjectRequest, routes /move, /archive, /delete | Task 4 |
| Contract guards: PROJECT_SUMMARY + PROJECT_DETAIL include new fields | Task 5 |
| Web types + api client | Task 6 |
| ProjectsView tree (recursive), expand/collapse, archive/delete buttons | Task 7 |
| All validators green | Task 8 |

No placeholders, no "TBD". All test code included. Types consistent (ProjectSummary, move_project params). Scope matches spec exactly — no "v1", "basic", "for now".