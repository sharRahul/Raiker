"""The work index: one thread of the owner's work, and a page of them."""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass

from raiker.contracts.views import View


@dataclass(frozen=True)
class WorkThreadView(View):
    """One thread of the owner's work, whatever started it (GAP-CHAT C18).

    Chat search covered titles and message text, which answers *"where did I say
    that"* and not *"what am I working on"*. Those are different questions: the
    second one spans conversations the owner typed **and** the threads a routine
    is advancing on its own (C11), it wants the project each sits in, and it
    wants to know which of them is blocked on the owner.

    Every field here is read from a row that already existed. This view invents
    no state; it is the join nothing was performing.
    """

    session_id: str
    title: str
    #: ``chat`` for a conversation the owner started, ``routine`` for a thread a
    #: task is advancing. The distinction is what makes "resume the thread a
    #: routine is advancing" possible at all — it used to be unreachable.
    kind: str
    updated_at: str
    turn_count: int
    #: REM-THREAD-03 — which surface owns this work: ``chat``, ``build`` or
    #: ``design``. A thread is resumed *where it was done*; offering "open in
    #: chat" for a conversation whose repository, diffs and approvals live in
    #: Build sends the owner to a surface that cannot show any of them. Read
    #: from the session row rather than guessed, and ``chat`` for a row written
    #: before sessions recorded it.
    origin: str = "chat"
    project_id: str | None = None
    project_name: str | None = None
    #: Set only on a ``routine`` thread: the task advancing it.
    task_id: str | None = None
    task_status: str | None = None
    cadence: str | None = None
    next_run_at: str | None = None
    #: What this thread is waiting on, in the owner's language, or None when it
    #: is not waiting on anything. Only ever states a blocker the runtime
    #: actually holds — never a guess about staleness.
    waiting_on: str | None = None
    # ── BUG-303: what the library needs to organise a thread ─────────────────
    #
    # These three were already stored on the session row and read only by
    # Sessions, which is the page whose job is *audit*. So the everyday library
    # controls — pin, archive, tags — lived in the evidence inspector, while the
    # page work is actually resumed from could not express any of them. Moving
    # the controls needed the index to be able to carry their state first, and
    # this is that state. Nothing new is invented: a pin, an archive flag and a
    # tag set are organizing labels that grant nothing.
    #
    # A routine thread is a task's own conversation. It is not in the owner's
    # library and cannot be pinned, archived or tagged, so it reports the
    # defaults and the interface offers it no such control.
    pinned: bool = False
    archived: bool = False
    tags: tuple[str, ...] = ()


# ── The work index (NEW-THREAD-01) ───────────────────────────────────────────
#
# Threads derived its Project choices *and* its results from one unpaginated
# read of a hundred rows. Three things followed, and all three read as facts
# about the workspace rather than about the read:
#
# * a project whose newest thread fell outside the first hundred was **not
#   offered as a filter at all**, which is indistinguishable from a project with
#   nothing in it;
# * the window looked like the whole inventory, because nothing said otherwise;
# * typing a query called an unscoped search and hid the filters, so narrowing
#   something down silently widened it.
#
# The browser was being used as the index. These are the bounds that let the
# server be one: filter, then facet over everything that matched, then page.

#: Default rows per page, and the most a caller may ask for.
WORK_THREAD_PAGE_LIMIT = 50


WORK_THREAD_MAX_PAGE_LIMIT = 200


#: How many of the owner's threads the index will consider. Generous enough
#: that an ordinary workspace is answered completely, bounded because an index
#: that reads everything is the defect with a larger number. When it binds, the
#: answer says so rather than quietly describing a slice.
WORK_THREAD_SCAN_LIMIT = 2000


@dataclass(frozen=True)
class WorkThreadFacet(View):
    """One filter choice, with how many threads it would select."""

    value: str
    label: str
    count: int


@dataclass(frozen=True)
class WorkThreadPage(View):
    """One page of the work index, and the filters that produced it."""

    threads: list[WorkThreadView]
    #: Opaque, and bound to the owner and the filters. A cursor from one scope
    #: is refused in another rather than paging through a different question.
    next_cursor: str | None
    #: How many threads matched the filters, within the scan bound.
    total: int
    #: Every project the owner has work in — computed with the *project* filter
    #: lifted, so choosing a different one is possible from any page. This is
    #: the finding: a facet computed over the current page can only ever offer
    #: what is already on screen.
    projects: list[WorkThreadFacet]
    #: Same, with the *kind* filter lifted.
    kinds: list[WorkThreadFacet]
    #: BUG-303 — how many threads the *other* archive scope holds, so archiving
    #: from this page is undoable from this page. A control whose effect the
    #: owner cannot reverse on the surface they used is worse than one that has
    #: not moved, which is exactly why Archive stayed in Sessions until now.
    #:
    #: Bounded by the same scan as ``total``, and qualified by the same
    #: ``scan_truncated``: both are counts of what the index looked at.
    archived_count: int
    active_count: int
    #: True when the scan bound was reached, so the counts above describe the
    #: most recent `WORK_THREAD_SCAN_LIMIT` threads rather than all of them.
    scan_truncated: bool


def _work_thread_scope(
    user_id: str | None,
    project_id: str | None,
    kind: str | None,
    query: str,
    archived: bool = False,
) -> str:
    """A short digest of the question a cursor was issued for.

    Carried inside the cursor so a cursor cannot be replayed against a different
    owner or a different filter set — paging is a position in one ordered
    answer, and the position means nothing in another.
    """
    material = "\x1f".join(
        [user_id or "", project_id or "", kind or "", query, "archived" if archived else ""]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def encode_work_thread_cursor(thread: WorkThreadView, scope: str) -> str:
    """Where the next page starts: the last row of this one, plus its scope."""
    raw = "\x1f".join([scope, thread.updated_at, thread.session_id])
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def decode_work_thread_cursor(cursor: str, scope: str) -> tuple[str, str] | None:
    """``(updated_at, session_id)`` the next page follows, or ``None``.

    ``None`` for anything that is not a cursor this scope issued — a corrupted
    string, and a valid cursor from a different filter set alike. A refused
    cursor restarts the listing rather than failing the read: the owner has
    changed the question, and the honest answer is its first page.
    """
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    parts = raw.split("\x1f")
    if len(parts) != 3 or parts[0] != scope:
        return None
    return parts[1], parts[2]
