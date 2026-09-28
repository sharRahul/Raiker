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
        with self.connect() as connection:
            connection.execute(
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
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM attachments WHERE attachment_id = ?"
                + (" AND owner_principal_id = ?" if scoped else ""),
                (attachment_id, *([owner_principal_id] if scoped else [])),
            ).fetchone()
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
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT attachment_id, kind, filename, media_type, byte_size, sha256, created_at
                FROM attachments WHERE attachment_id = ?
                """
                + (" AND owner_principal_id = ?" if scoped else ""),
                (attachment_id, *([owner_principal_id] if scoped else [])),
            ).fetchone()
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
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO image_generations
                (generation_id, owner_principal_id, profile_id, provider, model, prompt,
                 size, status, reason_code, attachment_id, media_type, byte_size, created_at,
                 source_generation_id, kind, project_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )

    def list_image_generations(
        self: SQLiteStore, *, owner_principal_id: str | None = None, limit: int = 60
    ) -> list[dict[str, Any]]:
        """Newest first. ``None`` disables owner scoping; an empty string fails
        closed rather than dropping the predicate (see ``load_attachment``)."""
        scoped = owner_principal_id is not None
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM image_generations"
                + (" WHERE owner_principal_id = ?" if scoped else "")
                + " ORDER BY created_at DESC, generation_id DESC LIMIT ?",
                (*([owner_principal_id] if scoped else []), int(limit)),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_image_generation(
        self: SQLiteStore, generation_id: str, *, owner_principal_id: str | None = None
    ) -> dict[str, Any] | None:
        scoped = owner_principal_id is not None
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM image_generations WHERE generation_id = ?"
                + (" AND owner_principal_id = ?" if scoped else ""),
                (generation_id, *([owner_principal_id] if scoped else [])),
            ).fetchone()
        return dict(row) if row is not None else None
