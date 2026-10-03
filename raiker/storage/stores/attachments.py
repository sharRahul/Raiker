# mypy: disable-error-code="misc"
"""Uploaded attachments and generated images (GCR-11).

One part of :class:`raiker.storage.sqlite.SQLiteStore`, which inherits it. Every method
is typed against the whole store (``self: SQLiteStore``), so a call into another
part is checked exactly as it was when every method lived in one class. mypy
reports that self-type as ``misc`` on a mixin, which is the one code this file
turns off.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from raiker.contracts.ids import utc_now

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore


class AttachmentStore:


    def save_attachment(
        self: SQLiteStore,
        *,
        attachment_id: str,
        kind: str,
        filename: str,
        media_type: str,
        sha256: str,
        data: bytes,
        owner_principal_id: str | None = None,
    ) -> None:
        """Persist validated attachment bytes. Validation is the caller's job
        (``raiker.runtime.attachments``) — this layer only stores what it is given."""
        self._execute(
            """
            INSERT OR REPLACE INTO attachments
            (attachment_id, kind, filename, media_type, byte_size, sha256, data, created_at, owner_principal_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attachment_id,
                kind,
                filename,
                media_type,
                len(data),
                sha256,
                data,
                utc_now(),
                owner_principal_id,
            ),
        )

    def load_attachment(
        self: SQLiteStore, attachment_id: str, *, owner_principal_id: str | None = None
    ) -> dict[str, Any] | None:
        """Return the stored attachment (metadata + raw bytes), or None if unknown."""
        # ``None`` means "no owner scoping requested"; an empty string is a
        # caller bug that must fail closed (match nothing), never drop the
        # predicate and expose every owner's bytes.
        scoped = owner_principal_id is not None
        row = self._row(
            "SELECT * FROM attachments WHERE attachment_id = ?"
            + (" AND owner_principal_id = ?" if scoped else ""),
            (attachment_id, *([owner_principal_id] if scoped else [])),
        )
        if row is None:
            return None
        record = dict(row)
        record["data"] = bytes(record["data"])
        return record

    def load_attachment_metadata(
        self: SQLiteStore, attachment_id: str, *, owner_principal_id: str | None = None
    ) -> dict[str, Any] | None:
        """Return attachment metadata only — the bytes never ride this path."""
        # ``None`` disables owner scoping; an empty string fails closed rather
        # than dropping the predicate (see ``load_attachment``).
        scoped = owner_principal_id is not None
        row = self._row(
            """
            SELECT attachment_id, kind, filename, media_type, byte_size, sha256, created_at
            FROM attachments WHERE attachment_id = ?
            """
            + (" AND owner_principal_id = ?" if scoped else ""),
            (attachment_id, *([owner_principal_id] if scoped else [])),
        )
        return dict(row) if row is not None else None


    def record_image_generation(
        self: SQLiteStore,
        *,
        generation_id: str,
        owner_principal_id: str | None,
        profile_id: str,
        provider: str,
        model: str,
        prompt: str,
        size: str,
        status: str,
        reason_code: str | None = None,
        attachment_id: str | None = None,
        media_type: str | None = None,
        byte_size: int = 0,
        source_generation_id: str | None = None,
        kind: str = "create",
        project_id: str | None = None,
        references_json: str | None = None,
    ) -> None:
        """Record one attempt, whether or not it produced an image.

        A refused generation is written with the same care as a successful one:
        the owner asked for something and the runtime said no, and a refusal
        nobody can see afterwards is the failure this product is written
        against.

        BUG-277 — `source_generation_id` and `kind` are what make a history out
        of a list. A refusal carries them too: an edit that was denied is still
        a thing the owner asked of a particular image, and dropping the subject
        from the record would leave the refusal unattributable to the asset it
        was about.
        """
        self._execute(
            """
            INSERT OR REPLACE INTO image_generations
            (generation_id, owner_principal_id, profile_id, provider, model, prompt,
             size, status, reason_code, attachment_id, media_type, byte_size, created_at,
             source_generation_id, kind, project_id, references_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                generation_id,
                owner_principal_id,
                profile_id,
                provider,
                model,
                prompt,
                size,
                status,
                reason_code,
                attachment_id,
                media_type,
                byte_size,
                utc_now(),
                source_generation_id,
                kind,
                project_id,
                references_json,
            ),
        )

    def list_image_generations(
        self: SQLiteStore,
        *,
        owner_principal_id: str | None = None,
        limit: int = 60,
        deleted: bool = False,
    ) -> list[dict[str, Any]]:
        """Newest first. ``None`` disables owner scoping; an empty string fails
        closed rather than dropping the predicate (see ``load_attachment``).

        UX-DESIGN-01 — ``deleted`` chooses which of the two lists: the gallery
        (``False``) or Recently deleted (``True``), newest deletion first. The
        two never mix, so a picture put away cannot reappear as a version or a
        sibling in the gallery it was taken out of.
        """
        scoped = owner_principal_id is not None
        clauses = (["owner_principal_id = ?"] if scoped else []) + [
            "deleted_at IS NOT NULL" if deleted else "deleted_at IS NULL"
        ]
        order = "deleted_at DESC, generation_id DESC" if deleted else "created_at DESC, generation_id DESC"
        rows = self._rows(
            "SELECT * FROM image_generations WHERE "
            + " AND ".join(clauses)
            + f" ORDER BY {order} LIMIT ?",
            (*([owner_principal_id] if scoped else []), int(limit)),
        )
        return [dict(row) for row in rows]

    def set_image_generation_deleted(
        self: SQLiteStore, generation_id: str, *, owner_principal_id: str, deleted: bool
    ) -> bool:
        """Put one picture away, or bring it back. Owner-scoped; False when the
        id is not this owner's or is already in the state asked for."""
        if not owner_principal_id:
            return False
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE image_generations SET deleted_at = ? "
                "WHERE generation_id = ? AND owner_principal_id = ? AND deleted_at IS "
                + ("NULL" if deleted else "NOT NULL"),
                (utc_now() if deleted else None, generation_id, owner_principal_id),
            )
            return cursor.rowcount == 1

    def purge_image_generation(
        self: SQLiteStore, generation_id: str, *, owner_principal_id: str
    ) -> bool:
        """Remove a picture that is already in Recently deleted, with its bytes.

        Only from Recently deleted: removing for good is the second of two
        deliberate steps, never the first. The row and its attachment go in one
        transaction, so a failure leaves both or neither — never a row pointing
        at bytes that are gone, or bytes nothing points at.
        """
        if not owner_principal_id:
            return False
        with self.connect() as connection:
            row = connection.execute(
                "SELECT attachment_id FROM image_generations WHERE generation_id = ? "
                "AND owner_principal_id = ? AND deleted_at IS NOT NULL",
                (generation_id, owner_principal_id),
            ).fetchone()
            if row is None:
                return False
            attachment_id = row[0]
            connection.execute(
                "DELETE FROM image_generations WHERE generation_id = ? AND owner_principal_id = ?",
                (generation_id, owner_principal_id),
            )
            if attachment_id:
                connection.execute(
                    "DELETE FROM attachments WHERE attachment_id = ? AND owner_principal_id = ?",
                    (attachment_id, owner_principal_id),
                )
            return True

    def get_image_generation(
        self: SQLiteStore, generation_id: str, *, owner_principal_id: str | None = None
    ) -> dict[str, Any] | None:
        scoped = owner_principal_id is not None
        row = self._row(
            "SELECT * FROM image_generations WHERE generation_id = ?"
            + (" AND owner_principal_id = ?" if scoped else ""),
            (generation_id, *([owner_principal_id] if scoped else [])),
        )
        return dict(row) if row is not None else None
