# Nested Projects/Folders Design

**Date:** 2026-07-14
**Status:** Approved
**Slice:** Conversation organisation remainder (nested projects/folders)

---

## Scope

Add arbitrary-depth folder nesting to the existing `projects` table. Folders are governance-neutral organizing scopes (like current projects) — they grant no authority and change no gate/policy. Sessions are assigned to a folder/project and inherit context from ancestors. Two deletion modes: **archive** (AI autonomous, soft) and **delete** (human-only, hard with orphanage cascade).

---

## Non-Goals

- No new capability gates, policies, or executors
- No changes to session-level permissions
- No project/folder templates or preset structures
- No drag-and-drop reordering (MVP: create/select/move via API)

---

## Architecture

### Storage (Hybrid: Adjacency List + Materialized Path)

Extend `projects` table:

```sql
-- New columns on projects
ALTER TABLE projects ADD COLUMN parent_id TEXT REFERENCES projects(project_id) ON DELETE SET NULL;
ALTER TABLE projects ADD COLUMN path TEXT NOT NULL DEFAULT '/'; -- e.g. '/1/4/12/'
ALTER TABLE projects ADD COLUMN is_archived INTEGER NOT NULL DEFAULT 0;
ALTER TABLE projects ADD COLUMN archived_at TEXT;

-- Trigger: auto-sync path on parent_id change
CREATE TRIGGER sync_project_path_after_update
AFTER UPDATE OF parent_id ON projects
BEGIN
  UPDATE projects SET path = (
    SELECT COALESCE(p.path || new.parent_id || '/', '/')
    FROM projects p WHERE p.project_id = new.parent_id
  ) WHERE project_id = new.project_id;
  -- Recursive update for descendants
  UPDATE projects SET path = (
    SELECT COALESCE(pp.path || projects.parent_id || '/', '/')
    FROM projects pp WHERE pp.project_id = projects.parent_id
  ) WHERE path LIKE (SELECT path FROM projects WHERE project_id = new.project_id) || '%' AND project_id != new.project_id;
END;

-- Indexes
CREATE INDEX idx_projects_parent ON projects(parent_id);
CREATE INDEX idx_active_projects_path ON projects(path) WHERE is_archived = 0;
CREATE INDEX idx_all_projects_path ON projects(path);
```

- `parent_id` = source of truth for structure; `ON DELETE SET NULL` so children survive parent deletion
- `path` = materialized path for fast ancestor/subtree reads
- `is_archived` = soft delete flag; `archived_at` = timestamp
- Sessions unchanged: `project_id` FK to any node (root or nested)

### Context Inheritance

- Any node (root project or folder) can have `project_contexts` (instructions, attachment_ids, memory_enabled)
- On session startup for project/folder `:pid`: single query fetches all ancestors
  ```sql
  SELECT * FROM project_contexts pc
  JOIN projects p ON p.project_id = pc.project_id
  WHERE (SELECT path FROM projects WHERE project_id = :pid) LIKE '%' || pc.project_id || '/%'
  ORDER BY LENGTH(p.path) ASC;  -- root → leaf
  ```
- Merge strategy (application layer):
  - `instructions`: prepend/append (root first, leaf last — leaf wins on conflict)
  - `attachment_ids`: union (all ancestors' attachments available)
  - `memory_enabled`: boolean override — if any ancestor has `FALSE`, descendant is `FALSE` unless explicitly `TRUE`

### Delete/Archive (Soft-Cascading Orphanage)

| Action | Authority | Mechanism |
|--------|-----------|-----------|
| **Archive** | AI autonomous | `UPDATE projects SET is_archived=1, archived_at=utc_now() WHERE path LIKE (SELECT path FROM projects WHERE project_id=:target) || '%'` |
| **Delete** | Human-only (UI confirmation) | Transaction: (1) archive descendants: `UPDATE projects SET is_archived=1, archived_at=utc_now(), parent_id=NULL, path='orphaned/'||project_id||'/' WHERE path LIKE (SELECT path FROM projects WHERE project_id=:target) || '%' AND project_id!=:target`; (2) `DELETE FROM projects WHERE project_id=:target` |

- `ON DELETE SET NULL` on `parent_id` ensures children survive hard delete
- Archived/orphaned nodes excluded from active tree via partial index
- Sessions under deleted project: `project_id` FK remains valid (pointing to orphaned archived node), context lookup naturally finds no active ancestors

### UI

- `ProjectsView` tree: expand/collapse, archive button per row, delete button (confirmation modal)
- Active project switcher (topbar): shows tree, allows selecting any node
- Archive = AI tool (`archive_project`); Delete = human confirmation route

---

## Failure-Mode Check

| Failure Mode | Severity | Resolution |
|--------------|----------|------------|
| Path sync trigger fails on concurrent moves | Minor | SQLite serializes writes; path is derived, not authoritative. Can rebuild on demand via `list_projects` traversal. |
| Deep tree (100+ levels) query performance | Minor | SQLite recursive CTE handles 1000+ depth; personal assistant scale is << 10. Document max 50. |
| Orphaned sessions lose context after parent delete | Acceptable | By design: deleting a container archives children; sessions remain but lose inherited context. User can reassign. |
| Archive + delete race (AI archives, human deletes same node) | Minor | `is_archored` flag + transaction isolation; delete is human-gated with confirmation modal. |

---

## Migration Notes

- Existing projects: `parent_id=NULL`, `path='/'`, `is_archived=0`
- `project_contexts` unchanged; context lookup works for root projects
- No data migration needed for sessions

---

## Testing Strategy

- `tests/test_nested_projects.py`: CRUD, tree queries, context merge, archive, delete, isolation
- `ProjectsView.test.ts`: tree render, expand/collapse, archive/delete actions
- `test_api_contract_schemas.py`: guard new fields on `ProjectDetail`
- Validators: `ruff`, `mypy`, `pytest`, web `check`/`lint`/`test`/`build`

---

## Rollout

Single commit with:
1. Migration (`PROJECTS_NESTING_MIGRATION_ID`)
2. Storage methods (`list_project_tree`, `move_project`, `archive_project`, `delete_project_with_orphanage`, `get_ancestor_contexts`)
3. DashboardService methods (human-only archive/delete with visibility checks)
4. API routes (`POST /api/projects/move`, `PUT /api/projects/{id}/archive`, `DELETE /api/projects/{id}`)
5. ProjectsView tree UI + tests