# Nested Projects/Folders Design

**Date:** 2026-07-14
**Status:** Approved — Implemented
**Slice:** Conversation organisation remainder (nested projects/folders)
**Commit:** `f1dd82c` — `feat: nested projects/folders with archive + orphanage delete`

---

## Scope

Add arbitrary-depth folder nesting to the existing `projects` table. Folders are governance-neutral organizing scopes (like current projects) — they grant no authority and change no gate/policy. Sessions are assigned to a folder/project and inherit context from ancestors. Two deletion modes: **archive** (AI-autonomous, soft) and **delete** (human-only, hard with orphanage cascade).

---

## Non-Goals

- No new capability gates, policies, or executors
- No changes to session-level permissions
- No project/folder templates or preset structures
- No drag-and-drop reordering (MVP: create/select/move via API)

---

## Architecture

### Storage (Hybrid: Adjacency List + Materialized Path)

Extend `projects` table with four new columns and three indexes. **Path management is done in Python, not a DB trigger** — the original trigger approach caused `NOT NULL constraint` failures when explicit Python updates ran alongside trigger logic. Removing the trigger and handling path computation in `SQLiteStore.move_project()` and `SQLiteStore.create_project()` is simpler and more reliable.

```sql
-- New columns on projects (migration RAIKER-1012-projects-nesting)
ALTER TABLE projects ADD COLUMN parent_id TEXT REFERENCES projects(project_id) ON DELETE SET NULL;
ALTER TABLE projects ADD COLUMN path TEXT NOT NULL DEFAULT '/'; -- e.g. '/p1/p4/p12/'
ALTER TABLE projects ADD COLUMN is_archived INTEGER NOT NULL DEFAULT 0;
ALTER TABLE projects ADD COLUMN archived_at TEXT;

-- Indexes
CREATE INDEX idx_projects_parent ON projects(parent_id);
CREATE INDEX idx_active_projects_path ON projects(path) WHERE is_archived = 0;
CREATE INDEX idx_all_projects_path ON projects(path);
```

- `parent_id` = source of truth for structure; `ON DELETE SET NULL` so children survive parent deletion
- `path` = materialized path for fast ancestor/subtree reads; computed in Python on create/move
- `is_archived` = soft delete flag; `archived_at` = timestamp
- Sessions unchanged: `project_id` FK to any node (root or nested); `ON DELETE NO ACTION` (sessions for deleted project are cleaned up by `delete_project_with_orphanage`)

### Path Computation (Python, not trigger)

```python
# create_project: initial path
if parent_id:
    parent_path = conn.execute("SELECT path FROM projects WHERE project_id=?", (parent_id,)).fetchone()["path"]
    path = f"{parent_path}{parent_id}/"
else:
    path = "/"

# move_project: update target path + all descendants via REPLACE
old_path = row["path"]
new_path = "/" if not new_parent_id else f"{new_parent_path}{new_parent_id}/"
conn.execute("UPDATE projects SET parent_id=?, path=?, updated_at=? WHERE project_id=?",
             (new_parent_id, new_path, utc_now(), project_id))
conn.execute("UPDATE projects SET path=REPLACE(path, ?, ?), updated_at=? WHERE path LIKE ?",
             (old_path, new_path, utc_now(), old_path + "%"))
```

### Context Inheritance

- Any node (root project or folder) can have `project_contexts` (instructions, attachment_ids, memory_enabled)
- On session startup for project/folder `:pid`: single query fetches all ancestors
  ```sql
  SELECT pc.* FROM project_contexts pc
  JOIN projects p ON p.project_id = pc.project_id
  WHERE (SELECT path FROM projects WHERE project_id = :pid) LIKE '%' || p.project_id || '/%'
    AND p.is_archived = 0
  ORDER BY LENGTH(p.path) ASC;  -- root → leaf
  ```
- Merge strategy (application layer, `DashboardService.get_session_context`):
  - Start with the leaf's own context (own `instructions`, `attachment_ids`, `memory_enabled`)
  - Walk ancestor contexts (root→leaf order) and prepend each ancestor's instructions
  - `instructions`: ancestor instructions prepended, leaf's own appended last (leaf wins)
  - `attachment_ids`: union of all ancestors' attachments (deduplicated)
  - `memory_enabled`: the leaf's own value wins (not an ancestor-AND merge)

### Delete/Archive (Soft-Cascading Orphanage)

| Action | Authority | Mechanism |
|--------|-----------|-----------|
| **Archive** | AI-autonomous (any authenticated principal) | `UPDATE projects SET is_archived=1, archived_at=?, updated_at=? WHERE path LIKE ?` (archives entire subtree) |
| **Delete** | Human-only (requires `confirm=True` always) | Transaction: (1) delete sessions for target project + cascaded rows (FK: ON DELETE NO ACTION); (2) archive descendants: `UPDATE ... SET is_archived=1, parent_id=NULL, path='orphaned/'||project_id||'/'`; (3) clear `active_project` if referencing target; (4) `DELETE FROM projects WHERE project_id=?` (project_contexts cascade via ON DELETE CASCADE) |

- `ON DELETE SET NULL` on `parent_id` ensures children survive hard delete (though descendants are already reparented to NULL in step 2)
- Archived/orphaned nodes excluded from active tree via partial index (`WHERE is_archived = 0`)
- `delete_project_with_orphanage` cleans up sessions for the **target** project only (descendants' sessions remain — descendants are archived, not deleted)
- Sessions under deleted project: their rows are hard-deleted (cascaded rows for events, turns, checkpoints, tasks, etc. also cleaned up)

### API

| Method | Path | Auth | Body |
|--------|------|------|------|
| `GET` | `/api/projects` | any | — |
| `GET` | `/api/projects/tree` | any | — |
| `GET` | `/api/projects/{id}` | any | — |
| `POST` | `/api/projects` | human | `{ name, parent_id? }` |
| `PUT` | `/api/projects/selection` | human | `{ project_id }` |
| `PUT` | `/api/projects/{id}/context` | human | `{ instructions, attachment_ids, memory_enabled }` |
| `PUT` | `/api/projects/{id}/move` | human | `{ parent_id }` |
| `PUT` | `/api/projects/{id}/archive` | any authenticated | — |
| `DELETE` | `/api/projects/{id}` | human | header `X-Project-Delete-Confirm: {id}` |

### UI

- `ProjectsView`: flat project grid (cards) with archive/move/delete actions + folder tree section
- `ProjectTreeNode.svelte`: recursive Svelte 5 component for tree rendering with expand/collapse
- Archive button per card; Move via dropdown dialog (select new parent); Delete with `window.confirm`
- Tree section at bottom shows hierarchy with expand/collapse chevrons

---

## Failure-Mode Check

| Failure Mode | Severity | Resolution |
|--------------|----------|------------|
| Path computation race on concurrent moves | Minor | SQLite serializes writes; path is derived in Python, not via trigger. Can rebuild on demand via `list_projects` traversal. |
| Deep tree (100+ levels) query performance | Minor | SQLite handles 1000+ depth; personal assistant scale is << 10. Document max 50. |
| Orphaned sessions lose context after parent delete | By design | Deleting a project hard-deletes its sessions; descendant projects are archived (not deleted) and their sessions remain. |
| Archive + delete race (AI archives, human deletes same node) | Minor | `is_archived` flag + transaction isolation; delete is human-gated with confirmation. |

---

## Migration Notes

- Existing projects: `parent_id=NULL`, `path='/'`, `is_archived=0`
- `project_contexts` unchanged; context lookup works for root projects
- No data migration needed for sessions
- Migration id: `RAIKER-1012-projects-nesting`

---

## Testing Strategy

- `tests/test_nested_projects.py`: 18 tests — migration, tree queries, move (cycle check), archive (idempotent, subtree), delete (orphanage, requires confirm), ancestor contexts, service layer (AI-autonomous archive, human-only move/delete, context merge)
- `tests/test_projects.py`: 11 API tests — tree list, move (happy path + 422 unknown field), archive (happy path), existing create/list/select/detail/delete/context roundtrip
- `tests/test_api_contract_schemas.py`: `PROJECT_VIEW` set + `PROJECTS_LIST` set — guards that backend response includes all client-read fields
- `apps/web/src/lib/views/ProjectsView.test.ts`: 5 tests — list, empty state, create + notify, select, server rejection
- Validators: `ruff`, `mypy`, `pytest`, `tsc --noEmit`, `vitest`

---

## Rollout

Single commit (`f1dd82c`):
1. Migration (`PROJECTS_NESTING_MIGRATION_ID`) — columns + indexes, **no trigger**
2. Storage methods (`create_project` with `parent_id`, `list_project_tree`, `move_project` with cycle check + REPLACE-based path update, `archive_project`, `delete_project_with_orphanage` with session cleanup, `get_ancestor_contexts`)
3. DashboardService methods (`list_project_tree`, `archive_project` AI-autonomous, `move_project` human-only, `delete_project` human-only + always requires `confirm=True`, `get_session_context` ancestor merge, `create_project` accepts `parent_id`)
4. API routes (`GET /api/projects/tree`, `PUT /api/projects/{id}/move`, `PUT /api/projects/{id}/archive`, `DELETE /api/projects/{id}` with confirm header, `POST /api/projects` with `parent_id`)
5. Web: `ProjectTreeNode` type + `ProjectTreeNode.svelte` recursive component, `projectTree`/`moveProject`/`archiveProject` API client, `ProjectsView` tree section + archive/move/delete actions, `ProjectView` includes nesting fields
6. Contract guards + tests
