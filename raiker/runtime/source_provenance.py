"""Opening the exact passage a memory or a generated file came from (BUG-27).

Every approved memory already carried where it came from — ``source_session_id``,
``source_turn_id``, ``source_type``, written once by the governed memory path and
never rewritten. What it did not carry was any way to *go there*: the Memory page
could print "chat — Weekly planning" and nothing in the product would open that
conversation at the sentence the memory was drawn from. The provenance was true
and useless, which is the worst kind of provenance, because a claim you cannot
check reads exactly like a claim you can.

This module resolves those stored coordinates into a passage the inspector can
show. Its rules:

* **Coordinates are read, never inferred.** Only what the memory record actually
  stores is followed. A record with no coordinates resolves to
  ``no_provenance`` — an explicit, stateable answer — rather than to a guess at
  which conversation "probably" produced it.
* **Authorisation is re-checked at read time, against the caller.** Owning the
  memory is not owning the source: the session behind the coordinates must
  belong to this account *now*. A memory that points at a conversation this
  account may not read resolves to ``not_authorized`` and reveals nothing about
  whether that conversation exists.
* **Every failure is a named state, never an empty pane.** Deleted sources,
  sources that no longer contain the passage, and source types with no reader
  each resolve to their own status, and the inspector says which.
* **Nothing here executes source content.** The excerpt is bounded plain text
  plus two integers naming the run to highlight; the client renders text, and
  the highlight is applied by slicing that text, not by emitting markup.

**What is *not* claimed.** The stored coordinates name a turn, not a byte range
inside it, so the passage is located by searching the source text for the
memory's own words. That is exact when the text is unchanged and honest when it
is not — a passage that cannot be found reports ``source_changed`` rather than
highlighting something near it. Byte-range coordinates written at capture time
would remove the search entirely; that is tracked, not pretended.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from raiker.storage.sqlite import SQLiteStore

# How much text the inspector receives around a located passage. A source turn
# can be very long; a reading pane wants the passage and its context, not a
# transcript, and shipping the whole thing would be a client-side denial of
# service for no reading benefit.
MAX_EXCERPT_CHARS = 4_000
CONTEXT_CHARS = 600

# Resolution outcomes. Each one is a state the inspector renders in words.
STATUS_RESOLVED = "resolved"
STATUS_NO_PROVENANCE = "no_provenance"
STATUS_SOURCE_DELETED = "source_deleted"
STATUS_SOURCE_CHANGED = "source_changed"
STATUS_UNSUPPORTED_SOURCE = "unsupported_source"
STATUS_NOT_AUTHORIZED = "not_authorized"


@dataclass(frozen=True)
class SourceExcerpt:
    """One resolved source passage, or the stated reason there is not one."""

    status: str
    kind: str = ""
    title: str = ""
    excerpt: str = ""
    #: Where the passage begins inside ``excerpt``, and how long it runs.
    #: ``-1`` means "this excerpt has no located passage" — the source is shown
    #: without a highlight rather than with a guessed one.
    highlight_start: int = -1
    highlight_length: int = 0
    session_id: str = ""
    turn_id: str = ""
    attachment_id: str = ""
    truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "kind": self.kind,
            "title": self.title,
            "excerpt": self.excerpt,
            "highlight_start": self.highlight_start,
            "highlight_length": self.highlight_length,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "attachment_id": self.attachment_id,
            "truncated": self.truncated,
        }


def _normalise(text: str) -> str:
    """Collapse whitespace so a passage matches across re-wrapping."""
    return re.sub(r"\s+", " ", text).strip()


def locate_passage(source: str, passage: str) -> tuple[int, int]:
    """Where *passage* sits inside *source*, as ``(start, length)``.

    ``(-1, 0)`` when it is not there. Matching is whitespace-insensitive and
    case-insensitive, because a memory is stored as the sentence it means, and a
    transcript may have wrapped or re-cased it. It is never fuzzy beyond that: a
    passage that has genuinely changed must not silently match something near it.
    """
    if not source or not passage:
        return (-1, 0)

    needle = _normalise(passage).lower()
    if not needle:
        return (-1, 0)

    # Walk the source once, building the normalised form and the map back to
    # original offsets, so a hit in normalised space is reported in real ones.
    normalised: list[str] = []
    offsets: list[int] = []
    previous_space = True
    for index, char in enumerate(source):
        if char.isspace():
            if previous_space:
                continue
            normalised.append(" ")
            offsets.append(index)
            previous_space = True
            continue
        normalised.append(char.lower())
        offsets.append(index)
        previous_space = False

    hay = "".join(normalised)
    found = hay.find(needle)
    if found == -1:
        return (-1, 0)
    start = offsets[found]
    last = offsets[min(found + len(needle) - 1, len(offsets) - 1)]
    return (start, last - start + 1)


def build_excerpt(source: str, passage: str) -> tuple[str, int, int, bool]:
    """A bounded window of *source* around *passage*.

    Returns ``(excerpt, highlight_start, highlight_length, truncated)``. When the
    passage cannot be found the window is the head of the source and the
    highlight is ``-1`` — the source is shown, plainly, with nothing pretending
    to be the passage.
    """
    start, length = locate_passage(source, passage)
    if start == -1:
        head = source[:MAX_EXCERPT_CHARS]
        return head, -1, 0, len(source) > len(head)

    window_start = max(0, start - CONTEXT_CHARS)
    window_end = min(len(source), start + length + CONTEXT_CHARS)
    if window_end - window_start > MAX_EXCERPT_CHARS:
        window_end = window_start + MAX_EXCERPT_CHARS
    excerpt = source[window_start:window_end]
    highlight_length = min(length, len(excerpt) - (start - window_start))
    return (
        excerpt,
        start - window_start,
        max(highlight_length, 0),
        window_start > 0 or window_end < len(source),
    )


class SourceProvenanceService:
    """Resolves stored source coordinates into a passage this caller may read."""

    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    def resolve(
        self, provenance: dict[str, Any], passage: str, owner_principal_id: str
    ) -> SourceExcerpt:
        """Resolve one record's coordinates, or state why they cannot be."""
        session_id = str(provenance.get("source_session_id") or "").strip()
        turn_id = str(provenance.get("source_turn_id") or "").strip()
        attachment_id = str(provenance.get("source_attachment_id") or "").strip()

        if attachment_id:
            return self._resolve_attachment(session_id, attachment_id, passage, owner_principal_id)
        if not session_id and not turn_id:
            return SourceExcerpt(status=STATUS_NO_PROVENANCE)
        return self._resolve_turn(session_id, turn_id, passage, owner_principal_id)

    # ── conversation turns ───────────────────────────────────────────────

    def _resolve_turn(
        self, session_id: str, turn_id: str, passage: str, owner_principal_id: str
    ) -> SourceExcerpt:
        turn = self._store.load_turn(turn_id) if turn_id else None
        resolved_session = session_id or (str(turn.get("session_id", "")) if turn else "")
        if not resolved_session:
            return SourceExcerpt(status=STATUS_NO_PROVENANCE)

        session = self._store.load_session(resolved_session)
        if session is None:
            # The conversation is gone. Saying so is the point: a memory whose
            # source was deleted is still a memory, and the owner is entitled to
            # know its source can no longer be checked.
            return SourceExcerpt(
                status=STATUS_SOURCE_DELETED, kind="conversation", session_id=resolved_session,
            )
        if not self._may_read_session(session, owner_principal_id):
            return SourceExcerpt(status=STATUS_NOT_AUTHORIZED)
        if turn is None:
            return SourceExcerpt(
                status=STATUS_SOURCE_DELETED,
                kind="conversation",
                title=str(session.get("title") or "Untitled conversation"),
                session_id=resolved_session,
                turn_id=turn_id,
            )

        # The turn as the owner would read it back: what they asked, and what
        # Raiker recorded for it.
        parts = [str(turn.get("prompt_text") or ""), str(turn.get("summary") or "")]
        source = "\n\n".join(part for part in parts if part.strip())
        excerpt, start, length, truncated = build_excerpt(source, passage)
        return SourceExcerpt(
            status=STATUS_RESOLVED if start >= 0 else STATUS_SOURCE_CHANGED,
            kind="conversation",
            title=str(session.get("title") or "Untitled conversation"),
            excerpt=excerpt,
            highlight_start=start,
            highlight_length=length,
            session_id=resolved_session,
            turn_id=str(turn.get("turn_id") or turn_id),
            truncated=truncated,
        )

    # ── attachments ──────────────────────────────────────────────────────

    def _resolve_attachment(
        self, session_id: str, attachment_id: str, passage: str, owner_principal_id: str
    ) -> SourceExcerpt:
        from raiker.runtime.attachment_preview import AttachmentPreviewService

        if not session_id:
            return SourceExcerpt(status=STATUS_NO_PROVENANCE)
        preview = AttachmentPreviewService(self._store).get(
            session_id, attachment_id, owner_principal_id
        )
        if preview is None:
            # Indistinguishable, on purpose, from "you may not read this": the
            # attachment reader answers `None` for both, and guessing between
            # them here would leak which one it was.
            return SourceExcerpt(status=STATUS_NOT_AUTHORIZED)
        if preview.kind in ("pdf", "image", "table", "unavailable"):
            # There is a file and this account may read it — there is just no
            # text offset to open it at. That is a different answer from "gone".
            return SourceExcerpt(
                status=STATUS_UNSUPPORTED_SOURCE,
                kind="file",
                title=preview.filename,
                session_id=session_id,
                attachment_id=attachment_id,
            )
        excerpt, start, length, truncated = build_excerpt(preview.text, passage)
        return SourceExcerpt(
            status=STATUS_RESOLVED if start >= 0 else STATUS_SOURCE_CHANGED,
            kind="file",
            title=preview.filename,
            excerpt=excerpt,
            highlight_start=start,
            highlight_length=length,
            session_id=session_id,
            attachment_id=attachment_id,
            truncated=truncated,
        )

    # ── authorisation ────────────────────────────────────────────────────

    def _may_read_session(self, session: dict[str, Any], owner_principal_id: str) -> bool:
        """Does this account own the conversation the coordinates point at?

        Fail closed: an unresolvable account is not a match. A legacy session
        row with no ``user_id`` predates per-account scoping and belongs to the
        single owner it was written for, so it stays readable rather than
        becoming permanently unopenable provenance.
        """
        owner_user_id = self._store.principal_user_id(owner_principal_id)
        session_user_id = session.get("user_id")
        if session_user_id in (None, ""):
            return True
        return owner_user_id is not None and str(session_user_id) == str(owner_user_id)
