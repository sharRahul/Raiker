# mypy: disable-error-code="misc"
"""Projects, their roots, context and hierarchy (GCR-11).

One part of :class:`raiker.storage.sqlite.SQLiteStore`, which inherits it. Every method
is typed against the whole store (``self: SQLiteStore``), so a call into another
part is checked exactly as it was when every method lived in one class. mypy
reports that self-type as ``misc`` on a mixin, which is the one code this file
turns off.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from raiker.contracts.ids import utc_now

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

#: A row inside the subtree whose materialised path is the second parameter;
#: the first is that path's length. A prefix comparison rather than ``LIKE``,
#: because project ids carry ``_``, which ``LIKE`` reads as "any character".
_IN_SUBTREE = "substr(path, 1, ?) = ?"


class ProjectStore:


    ACTIVE_PROJECT_SCOPE = "project_scope:"

    def create_project(
        self: SQLiteStore,
        project_id: str,
        name: str,
        root_subpath: str,
        parent_id: str | None = None,
        owner_user_id: str | None = None,
    ) -> None:
        if owner_user_id is None:
            original = self.original_account_principal_id()
            owner_user_id = self.principal_user_id(original) if original else None
        with self.connect() as connection:
            if parent_id:
                parent = connection.execute(
                    "SELECT path FROM projects WHERE project_id = ?", (parent_id,)
                ).fetchone()
                parent_path = parent["path"] if parent else "/"
                path = f"{parent_path}{project_id}/"
            else:
                path = f"/{project_id}/"
            connection.execute(
                "INSERT INTO projects (project_id, name, root_subpath, created_at, parent_id, path, is_archived, archived_at, owner_user_id) VALUES (?, ?, ?, ?, ?, ?, 0, NULL, ?)",
                (project_id, name, root_subpath, utc_now(), parent_id, path, owner_user_id),
            )

    def load_project(self: SQLiteStore, project_id: str, user_id: str | None = None) -> dict[str, Any] | None:
        row = self._row(
            "SELECT * FROM projects WHERE project_id = ?"
            + (" AND owner_user_id = ?" if user_id else ""),
            (project_id, user_id) if user_id else (project_id,),
        )
        return dict(row) if row else None

    def attach_project_root(
        self: SQLiteStore, project_id: str, root_grant_id: str, *, user_id: str | None = None
    ) -> bool:
        """Point a project at a folder the owner granted.

        `root_subpath` is cleared rather than kept: an attached project has no
        workspace-relative root, and leaving a stale one behind would give the
        resolver two answers to choose between.
        """
        if self.load_project(project_id, user_id) is None:
            return False
        updated = self._execute(
            "UPDATE projects SET root_kind = 'attached', root_grant_id = ?, root_subpath = '' "
            "WHERE project_id = ?",
            (root_grant_id, project_id),
        )
        return updated == 1

    def detach_project_root(self: SQLiteStore, project_id: str, *, user_id: str | None = None) -> bool:
        """Release the grant a project was attached to, leaving it rootless.

        Deliberately keeps `root_kind = 'attached'`. Turning the project back
        into a managed one would invent a root under `.raiker/projects/` that
        the owner never asked for and that holds none of their work.
        """
        if self.load_project(project_id, user_id) is None:
            return False
        updated = self._execute(
            "UPDATE projects SET root_grant_id = NULL WHERE project_id = ?",
            (project_id,),
        )
        return updated == 1

    def project_for_grant(
        self: SQLiteStore, owner_principal_id: str, root_grant_id: str
    ) -> dict[str, Any] | None:
        """The project attached to one grant, if the caller owns it."""
        user_id = self.principal_user_id(owner_principal_id)
        row = self._row("SELECT * FROM projects WHERE root_grant_id = ?", (root_grant_id,))
        if row is None:
            return None
        owner = row["owner_user_id"]
        if user_id is not None and owner is not None and owner != user_id:
            return None
        return dict(row)

    def load_project_by_name(self: SQLiteStore, name: str) -> dict[str, Any] | None:
        row = self._row("SELECT * FROM projects WHERE name = ?", (name,))
        return dict(row) if row else None

    def update_project_root(
        self: SQLiteStore,
        project_id: str,
        root_subpath: str,
        *,
        expected_root_subpath: str | None = None,
    ) -> bool:
        """Change one project's root without changing its identity or ownership.

        ``expected_root_subpath`` lets a filesystem migration refuse to replace
        a concurrent change to the project row.
        """
        query = "UPDATE projects SET root_subpath = ? WHERE project_id = ?"
        params: list[Any] = [root_subpath, project_id]
        if expected_root_subpath is not None:
            query += " AND root_subpath = ?"
            params.append(expected_root_subpath)
        updated = self._execute(query, params)
        return updated == 1

    def publish_project_root_atomic(
        self: SQLiteStore,
        project_id: str,
        expected_root_subpath: str,
        root_subpath: str,
        publish: Callable[[], None],
    ) -> bool:
        """Publish a claimed project directory and its row under one DB lock."""
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    "SELECT root_subpath FROM projects WHERE project_id = ?", (project_id,)
                ).fetchone()
                if row is None or str(row["root_subpath"]) != expected_root_subpath:
                    connection.rollback()
                    return False
                publish()
                updated = connection.execute(
                    "UPDATE projects SET root_subpath = ? WHERE project_id = ? AND root_subpath = ?",
                    (root_subpath, project_id, expected_root_subpath),
                )
                if updated.rowcount != 1:
                    raise RuntimeError("project_root_update_lost")
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return True

    def load_project_context(
        self: SQLiteStore, project_id: str, *, user_id: str | None = None
    ) -> dict[str, Any]:
        if user_id is not None and self.load_project(project_id, user_id=user_id) is None:
            return {
                "instructions": "",
                "attachment_ids": [],
                "memory_enabled": False,
                "memory_mode": "inherit",
            }
        row = self._row(
            "SELECT instructions, attachment_ids_json, memory_enabled, memory_mode FROM project_contexts WHERE project_id = ?",
            (project_id,),
        )
        if row is None:
            return {
                "instructions": "",
                "attachment_ids": [],
                "memory_enabled": False,
                "memory_mode": "inherit",
            }
        try:
            attachment_ids = json.loads(str(row["attachment_ids_json"]))
        except (TypeError, ValueError):
            attachment_ids = []
        return {
            "instructions": str(row["instructions"]),
            "attachment_ids": [str(item) for item in attachment_ids if isinstance(item, str)],
            "memory_enabled": bool(row["memory_enabled"]),
            "memory_mode": str(row["memory_mode"]),
        }

    def save_project_context(
        self: SQLiteStore,
        project_id: str,
        *,
        instructions: str,
        attachment_ids: list[str],
        memory_enabled: bool | None = None,
        memory_mode: str | None = None,
        owner_principal_id: str | None = None,
    ) -> None:
        mode = memory_mode or ("enabled" if memory_enabled else "disabled")
        if mode not in {"inherit", "enabled", "disabled"}:
            raise ValueError("invalid_memory_mode")
        if owner_principal_id is not None and any(
            self.load_attachment_metadata(attachment_id, owner_principal_id=owner_principal_id)
            is None
            for attachment_id in attachment_ids
        ):
            raise ValueError("unknown_project_attachment")
        self._execute(
            """
            INSERT INTO project_contexts (project_id, instructions, attachment_ids_json, memory_enabled, memory_mode, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id) DO UPDATE SET
              instructions = excluded.instructions,
              attachment_ids_json = excluded.attachment_ids_json,
              memory_enabled = excluded.memory_enabled,
              memory_mode = excluded.memory_mode,
              updated_at = excluded.updated_at
            """,
            (
                project_id,
                instructions,
                json.dumps(attachment_ids),
                int(mode == "enabled"),
                mode,
                utc_now(),
            ),
        )

    def list_projects(self: SQLiteStore, user_id: str | None = None) -> list[dict[str, Any]]:
        rows = self._rows(
            """
            SELECT projects.*, COUNT(sessions.session_id) AS session_count,
                   MAX(sessions.updated_at) AS last_activity_at,
                   grants.path AS root_grant_path
            FROM projects
            LEFT JOIN sessions ON sessions.project_id = projects.project_id
            -- An attached project's folder lives on its grant, so the list
            -- can name it without one extra query per row.
            LEFT JOIN brain_source_grants AS grants
                   ON grants.root_id = projects.root_grant_id
            """
            + (" WHERE projects.owner_user_id = ? " if user_id else "")
            + """
            GROUP BY projects.project_id
            ORDER BY projects.created_at DESC
            """,
            (user_id,) if user_id else (),
        )
        return [dict(row) for row in rows]

    def get_active_project(self: SQLiteStore, user_id: str | None = None) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT project_id FROM active_project WHERE scope_id = ?",
                (f"{self.ACTIVE_PROJECT_SCOPE}{user_id or 'legacy'}",),
            ).fetchone()
            if row is None and user_id is None:
                owner = self._original_owner_from_connection(connection)
                if owner is not None:
                    principal = connection.execute(
                        "SELECT delegated_by_user_id FROM principals WHERE principal_id = ?",
                        (owner,),
                    ).fetchone()
                    owner_user_id = (
                        str(principal["delegated_by_user_id"] or owner.removeprefix("principal_"))
                        if principal
                        else ""
                    )
                    if owner_user_id:
                        row = connection.execute(
                            "SELECT project_id FROM active_project WHERE scope_id = ?",
                            (f"{self.ACTIVE_PROJECT_SCOPE}{owner_user_id}",),
                        ).fetchone()
        project_id = str(row["project_id"]) if row is not None and row["project_id"] else None
        if (
            project_id is not None
            and user_id is not None
            and self.load_project(project_id, user_id) is None
        ):
            return None
        return project_id

    def save_active_project(self: SQLiteStore, project_id: str | None, user_id: str | None = None) -> None:
        self._execute(
            """
            INSERT INTO active_project (scope_id, project_id, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(scope_id) DO UPDATE SET project_id = excluded.project_id, updated_at = excluded.updated_at
            """,
            (f"{self.ACTIVE_PROJECT_SCOPE}{user_id or 'legacy'}", project_id, utc_now()),
        )

    def delete_project(self: SQLiteStore, project_id: str) -> bool:
        with self.connect() as connection:
            session_ids = [
                r[0]
                for r in connection.execute(
                    "SELECT session_id FROM sessions WHERE project_id = ?", (project_id,)
                )
            ]
            if (
                connection.execute(
                    "SELECT 1 FROM projects WHERE project_id = ?", (project_id,)
                ).fetchone()
                is None
            ):
                return False
            if session_ids:
                marks = ",".join("?" for _ in session_ids)
                action_ids = f"SELECT action_id FROM tool_actions WHERE session_id IN ({marks})"
                connection.execute(
                    f"DELETE FROM policy_decisions WHERE action_id IN ({action_ids})", session_ids
                )
                for table in (
                    "events_index",
                    "tool_actions",
                    "checkpoints",
                    "tasks",
                    "turns",
                    "model_session_state",
                    "model_fallback_sequence",
                    "model_advisor",
                    "session_tags",
                ):
                    connection.execute(
                        f"DELETE FROM {table} WHERE session_id IN ({marks})", session_ids
                    )
                connection.execute(
                    f"DELETE FROM sessions WHERE session_id IN ({marks})", session_ids
                )
            connection.execute(
                "UPDATE active_project SET project_id = NULL WHERE project_id = ?", (project_id,)
            )
            connection.execute("DELETE FROM project_contexts WHERE project_id = ?", (project_id,))
            connection.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
        return True

    # Arbitrary-depth folder hierarchy via hybrid adjacency list + materialized
    # path. Parent reference uses ON DELETE SET NULL so children survive parent
    # hard-delete. Path trigger auto-syncs on parent_id change. Partial index
    # on active tree for fast daily queries.

    def list_project_tree(
        self: SQLiteStore, include_archived: bool = False, user_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Return nested tree of projects (active by default)."""
        conditions = [] if include_archived else ["is_archived = 0"]
        params: list[Any] = []
        if user_id is not None:
            conditions.append("owner_user_id = ?")
            params.append(user_id)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM projects {where} ORDER BY path, created_at
            """,
                params,
            ).fetchall()
        nodes = {row["project_id"]: {**dict(row), "children": []} for row in rows}
        roots = []
        for row in rows:
            node = nodes[row["project_id"]]
            if row["parent_id"] is None:
                roots.append(node)
            elif row["parent_id"] in nodes:
                nodes[row["parent_id"]]["children"].append(node)
        return roots

    def move_project(self: SQLiteStore, project_id: str, new_parent_id: str | None) -> bool:
        """Move a project and its subtree under a new parent, in one transaction.

        Returns False for an unknown project or parent, a self-parent, or a
        parent inside the moving subtree (a cycle). The service names which of
        those it was before calling; this refusal is the one that holds even
        when a caller skips the service.
        """
        with self.connect() as conn:
            row = conn.execute(
                "SELECT project_id, path FROM projects WHERE project_id = ?", (project_id,)
            ).fetchone()
            if not row:
                return False
            old_path = row["path"]
            new_path = f"/{project_id}/"
            if new_parent_id:
                new_parent_row = conn.execute(
                    "SELECT path FROM projects WHERE project_id = ?", (new_parent_id,)
                ).fetchone()
                if not new_parent_row:
                    return False
                new_parent_path = new_parent_row["path"]
                if new_parent_path.startswith(old_path):
                    return False  # the parent is this project or one of its descendants
                new_path = f"{new_parent_path}{project_id}/"
            now = utc_now()
            conn.execute(
                "UPDATE projects SET path = ? || substr(path, ?), updated_at = ? "
                f"WHERE {_IN_SUBTREE}",
                (new_path, len(old_path) + 1, now, len(old_path), old_path),
            )
            conn.execute(
                "UPDATE projects SET parent_id = ?, updated_at = ? WHERE project_id = ?",
                (new_parent_id, now, project_id),
            )
        return True

    def subtree_project_ids(self: SQLiteStore, project_id: str) -> list[str]:
        """The project and every descendant, by materialised path. Empty if unknown."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT path FROM projects WHERE project_id = ?", (project_id,)
            ).fetchone()
            if not row:
                return []
            path = str(row["path"])
            rows = conn.execute(
                f"SELECT project_id FROM projects WHERE {_IN_SUBTREE} ORDER BY path",
                (len(path), path),
            ).fetchall()
        return [str(r["project_id"]) for r in rows]

    def archive_project(self: SQLiteStore, project_id: str) -> bool:
        """Soft-archive project and all descendants. Idempotent.

        A descendant archived earlier keeps its own ``archived_at``, so a
        restore of this project brings back what this archive took and leaves
        what was archived on its own.
        """
        with self.connect() as conn:
            row = conn.execute(
                "SELECT path FROM projects WHERE project_id = ?", (project_id,)
            ).fetchone()
            if not row:
                return False
            path = row["path"]
            now = utc_now()
            conn.execute(
                "UPDATE projects SET is_archived = 1, archived_at = ?, updated_at = ? "
                f"WHERE {_IN_SUBTREE} AND is_archived = 0",
                (now, now, len(path), path),
            )
            # An archived project receives no new work, so it stops being the
            # account-level filing target for anything in the subtree.
            conn.execute(
                "UPDATE active_project SET project_id = NULL WHERE project_id IN "
                f"(SELECT project_id FROM projects WHERE {_IN_SUBTREE})",
                (len(path), path),
            )
        return True

    def restore_project(self: SQLiteStore, project_id: str) -> bool:
        """Undo one archive: the project and the descendants archived with it.

        Matching on ``archived_at`` is what makes this the inverse of
        :meth:`archive_project` rather than "unarchive everything below": a
        child the owner archived on its own, earlier, stays archived.
        """
        with self.connect() as conn:
            row = conn.execute(
                "SELECT path, is_archived, archived_at FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            if not row:
                return False
            if not row["is_archived"]:
                return True
            path = row["path"]
            conn.execute(
                "UPDATE projects SET is_archived = 0, archived_at = NULL, updated_at = ? "
                f"WHERE {_IN_SUBTREE} AND is_archived = 1 AND archived_at IS ?",
                (utc_now(), len(path), path, row["archived_at"]),
            )
        return True

    def project_deletion_counts(self: SQLiteStore, project_id: str) -> dict[str, int]:
        """What deleting this project removes from the database, counted.

        The same session set :meth:`delete_project_with_orphanage` deletes, so
        the preview and the delete cannot disagree about what a chat is.
        """
        row = self._row(
            """
            SELECT
              (SELECT COUNT(*) FROM sessions WHERE project_id = :p) AS sessions,
              (SELECT COUNT(*) FROM turns WHERE session_id IN
                 (SELECT session_id FROM sessions WHERE project_id = :p)) AS turns,
              (SELECT COUNT(*) FROM tasks WHERE session_id IN
                 (SELECT session_id FROM sessions WHERE project_id = :p)) AS tasks,
              (SELECT COUNT(*) FROM checkpoints WHERE session_id IN
                 (SELECT session_id FROM sessions WHERE project_id = :p)) AS checkpoints,
              (SELECT COUNT(*) FROM managed_files WHERE project_id = :p) AS managed_files
            """,
            {"p": project_id},
        )
        fields = ("sessions", "turns", "tasks", "checkpoints", "managed_files")
        counts = {key: int(row[key] or 0) if row is not None else 0 for key in fields}
        counts["descendants"] = max(len(self.subtree_project_ids(project_id)) - 1, 0)
        return counts

    def delete_project_with_orphanage(self: SQLiteStore, project_id: str) -> bool:
        """Hard-delete project; archive descendants + reparent to NULL with orphaned/ path."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT path FROM projects WHERE project_id = ?", (project_id,)
            ).fetchone()
            if not row:
                return False
            path = row["path"]
            now = utc_now()
            # Delete sessions for target project (FK: ON DELETE NO ACTION)
            session_ids = [
                r[0]
                for r in conn.execute(
                    "SELECT session_id FROM sessions WHERE project_id = ?", (project_id,)
                )
            ]
            if session_ids:
                marks = ",".join("?" for _ in session_ids)
                action_ids = f"SELECT action_id FROM tool_actions WHERE session_id IN ({marks})"
                conn.execute(
                    f"DELETE FROM policy_decisions WHERE action_id IN ({action_ids})", session_ids
                )
                for table in (
                    "events_index",
                    "tool_actions",
                    "checkpoints",
                    "tasks",
                    "turns",
                    "model_session_state",
                    "model_fallback_sequence",
                    "model_advisor",
                    "session_tags",
                ):
                    conn.execute(f"DELETE FROM {table} WHERE session_id IN ({marks})", session_ids)
                conn.execute(f"DELETE FROM sessions WHERE session_id IN ({marks})", session_ids)
            # 1) Archive descendants (excluding target)
            conn.execute(
                "UPDATE projects SET is_archived = 1, archived_at = ?, parent_id = CASE WHEN parent_id = ? THEN NULL ELSE parent_id END, path = '/orphaned/' || ? || '/' || substr(path, ?), updated_at = ? "
                f"WHERE {_IN_SUBTREE} AND project_id != ?",
                (now, project_id, project_id, len(path) + 1, now, len(path), path, project_id),
            )
            conn.execute(
                "UPDATE active_project SET project_id = NULL WHERE project_id = ?", (project_id,)
            )
            # 2) Clear the project's catalogue. `managed_files.project_id`
            # references `projects` with no ON DELETE, so a project with any
            # indexed file could not be deleted at all -- the whole delete failed
            # on a foreign key. This removes rows and projections only; the bytes
            # are handled by the caller, which knows whether Raiker owns them.
            for file_row in conn.execute(
                "SELECT file_id FROM managed_files WHERE project_id = ?", (project_id,)
            ).fetchall():
                self._delete_managed_file_chunks(conn, str(file_row["file_id"]))
            conn.execute("DELETE FROM managed_files WHERE project_id = ?", (project_id,))
            # 3) Hard delete target (project_contexts cascades via ON DELETE CASCADE)
            conn.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
        return True

    def get_ancestor_contexts(
        self: SQLiteStore, project_id: str, *, user_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Return context rows for all active ancestors of project_id, ordered root→leaf."""
        with self.connect() as conn:
            target = conn.execute(
                "SELECT path FROM projects WHERE project_id = ?", (project_id,)
            ).fetchone()
            if not target:
                return []
            path = target["path"]
            rows = conn.execute(
                """
                SELECT pc.* FROM project_contexts pc
                JOIN projects p ON p.project_id = pc.project_id
                WHERE substr(?, 1, length(p.path)) = p.path
                  AND p.project_id != ? AND p.is_archived = 0
                """
                + (" AND p.owner_user_id = ?" if user_id is not None else "")
                + """
                ORDER BY LENGTH(p.path) ASC
            """,
                (path, project_id, *([user_id] if user_id is not None else [])),
            ).fetchall()
        return [dict(r) for r in rows]

    def load_effective_project_context(
        self: SQLiteStore, project_id: str, *, user_id: str | None = None
    ) -> dict[str, Any]:
        """Return the project's context merged with every active ancestor's.

        Instructions concatenate root→leaf so the nearest folder speaks last;
        attachment ids union in the same order; ``memory_enabled`` is the
        leaf's own value (an ancestor cannot opt a child into project memory).
        Archived ancestors contribute nothing. This is the single merge used by
        both the live context gatherer and the dashboard read path.
        """
        own = self.load_project_context(project_id, user_id=user_id)
        instructions: list[str] = []
        attachment_ids: list[str] = []
        memory_mode = "inherit"
        for ancestor in self.get_ancestor_contexts(project_id, user_id=user_id):
            text = str(ancestor.get("instructions") or "").strip()
            if text:
                instructions.append(text)
            raw = ancestor.get("attachment_ids_json")
            if raw:
                with contextlib.suppress(TypeError, ValueError):
                    attachment_ids.extend(
                        str(item) for item in json.loads(str(raw)) if isinstance(item, str)
                    )
            if ancestor.get("memory_mode") in {"enabled", "disabled"}:
                memory_mode = str(ancestor["memory_mode"])
        own_instructions = str(own.get("instructions") or "").strip()
        if own_instructions:
            instructions.append(own_instructions)
        attachment_ids.extend(own.get("attachment_ids", []))
        if own.get("memory_mode") in {"enabled", "disabled"}:
            memory_mode = str(own["memory_mode"])
        return {
            "instructions": "\n\n".join(instructions),
            "attachment_ids": list(dict.fromkeys(attachment_ids)),
            "memory_enabled": memory_mode == "enabled",
            "memory_mode": memory_mode,
        }
