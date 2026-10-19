"""BR-D05 — which commits Raiker made, said in the commit and read back from it.

A recipient of a change should be able to tell what produced it without taking a
model's word for it. A commit Raiker records on the owner's approval carries two
Git trailers, built only from runtime identifiers:

    Raiker-Session: sess_…
    Raiker-Turn: turn_…

They are **evidence, never authority.** Nothing reads a trailer to decide what
may run, and their absence is not a failure: a commit the owner made by hand has
none, and a repository whose policy strips trailers loses nothing but this
display. Anyone can type a trailer, so read-back distinguishes a trailer that
names a turn *this* owner's Raiker recorded (``recorded``) from one that merely
claims Raiker (``unrecorded``).

Only well-formed opaque identifiers are ever written — no path, branch, model
output or credential — so a trailer cannot leak what the commit message itself
would not.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Literal

SESSION_TRAILER = "Raiker-Session"
TURN_TRAILER = "Raiker-Turn"

_SESSION_ID = re.compile(r"^sess_[A-Za-z0-9-]{8,64}$")
_TURN_ID = re.compile(r"^turn_[A-Za-z0-9-]{8,64}$")

#: Commits one read-back reports, newest first.
MAX_PROVENANCE_COMMITS = 20

Provenance = Literal["recorded", "unrecorded", "none"]


def provenance_trailers(session_id: str | None, turn_id: str | None) -> list[tuple[str, str]]:
    """The trailers for a commit made in this turn, or none if the ids are not well formed."""
    session = str(session_id or "").strip()
    turn = str(turn_id or "").strip()
    if not _SESSION_ID.match(session):
        return []
    trailers = [(SESSION_TRAILER, session)]
    if _TURN_ID.match(turn):
        trailers.append((TURN_TRAILER, turn))
    return trailers


def with_trailers(message: str, trailers: list[tuple[str, str]]) -> str:
    """*message* with *trailers* as its final paragraph, Git's trailer convention."""
    if not trailers:
        return message
    block = "\n".join(f"{key}: {value}" for key, value in trailers)
    return f"{message.rstrip()}\n\n{block}\n"


#: Git's ``%G?`` letters, in words. ``good`` is a valid signature from a key the
#: machine trusts; ``untrusted`` is valid but from a key it does not; anything
#: Git could not check — no gpg/ssh verifier here, a missing key — is
#: ``unverifiable``, never ``good``.
_SIGNATURE_STATES = {
    "G": "good",
    "U": "untrusted",
    "B": "bad",
    "X": "expired",
    "Y": "expired",
    "R": "revoked",
    "E": "unverifiable",
    "N": "none",
}


def _log(root: Path, limit: int) -> list[dict[str, str]]:
    from raiker.tools.git import _git as git  # the credential-free, hook-free read path

    unit, record = "\x1f", "\x1e"
    fields = [
        "%h",
        "%s",
        "%aI",
        f"%(trailers:key={SESSION_TRAILER},valueonly,separator=%x2C)",
        f"%(trailers:key={TURN_TRAILER},valueonly,separator=%x2C)",
        # BR-D05 — Git's own verdict on the commit's signature. Raiker never
        # signs a commit itself; this reports the owner's signing, when there is any.
        "%G?",
    ]
    try:
        proc = git(root, ["log", f"-n{limit}", f"--format={unit.join(fields)}{record}"], timeout=10)
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    commits: list[dict[str, str]] = []
    for chunk in proc.stdout.split(record):
        parts = chunk.strip("\n").split(unit)
        if len(parts) != 6:
            continue
        commit, subject, when, session, turn, signature = (part.strip() for part in parts)
        commits.append(
            {
                "commit": commit,
                "subject": subject,
                "committed_at": when,
                "session_id": session.split(",")[0].strip(),
                "turn_id": turn.split(",")[0].strip(),
                "signature": _SIGNATURE_STATES.get(signature, "unverifiable"),
            }
        )
    return commits


def read_provenance(
    store: Any, root: Path, *, user_id: str | None, limit: int = MAX_PROVENANCE_COMMITS
) -> list[dict[str, Any]]:
    """Recent commits on *root*, each with what its trailers prove here.

    ``recorded`` only when the named session belongs to this account and holds
    the named turn. A malformed value is reported as ``unrecorded`` and never
    echoed beyond the identifier shape it failed.
    """
    rows: list[dict[str, Any]] = []
    for commit in _log(root, max(1, min(limit, MAX_PROVENANCE_COMMITS))):
        session, turn = commit["session_id"], commit["turn_id"]
        provenance: Provenance = "none"
        if session or turn:
            provenance = "unrecorded"
            if _SESSION_ID.match(session) and (not turn or _TURN_ID.match(turn)):
                provenance = "recorded" if _recorded(store, session, turn, user_id) else "unrecorded"
        rows.append(
            {
                "commit": commit["commit"],
                "subject": commit["subject"],
                "committed_at": commit["committed_at"],
                "provenance": provenance,
                "session_id": session if _SESSION_ID.match(session) else None,
                "turn_id": turn if _TURN_ID.match(turn) else None,
                "signature": commit["signature"],
            }
        )
    return rows


def _recorded(store: Any, session_id: str, turn_id: str, user_id: str | None) -> bool:
    try:
        session = store.load_session(session_id)
    except Exception:  # noqa: BLE001 — an unreadable record proves nothing
        return False
    if session is None:
        return False
    owner = session.get("user_id")
    if user_id is not None and owner is not None and str(owner) != user_id:
        return False
    if not turn_id:
        return True
    try:
        turn = store.load_turn(turn_id)
    except Exception:  # noqa: BLE001
        return False
    return turn is not None and str(turn.get("session_id")) == session_id
