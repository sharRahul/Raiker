"""BR-12 — what GitHub confirmed about a pull request Raiker opened.

The create call's response says a pull request exists. BR-12 asks for more
than that: *push output alone does not prove a PR exists*, and a reviewer needs
the branch, commit, number and URL from the provider itself. So after the
create call succeeds, the pull request is read back from GitHub — the same
host, the same owner credential, a separate GET — and the receipt records what
that read said:

* ``confirmed`` — GitHub returned the pull request, and its number, head
  branch and base branch are the ones Raiker asked for;
* ``mismatch`` — GitHub returned a pull request that differs (another head or
  base, a different number): something other than this request is at that URL;
* ``unconfirmed`` — the read-back failed, so only the create response is known.

The receipt is evidence and never authority: nothing reads it to allow a push,
a merge, or anything else, and merging stays the owner's. It holds identifiers
and branch names only — never a token, never the pull request's body.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from raiker.contracts.ids import new_id, utc_now

Confirmation = Literal["confirmed", "mismatch", "unconfirmed"]

_SHA = 40


def confirmation_of(
    readback: dict[str, Any] | None, *, number: int, head: str, base: str
) -> tuple[Confirmation, dict[str, Any]]:
    """Compare a ``GET /pulls/{number}`` answer with what was asked for."""
    if not isinstance(readback, dict) or not readback.get("number"):
        return "unconfirmed", {}
    raw_head = readback.get("head")
    raw_base = readback.get("base")
    head_info: dict[str, Any] = raw_head if isinstance(raw_head, dict) else {}
    base_info: dict[str, Any] = raw_base if isinstance(raw_base, dict) else {}
    observed = {
        "number": int(readback.get("number") or 0),
        "head_branch": str(head_info.get("ref") or ""),
        "base_branch": str(base_info.get("ref") or ""),
        "head_sha": str(head_info.get("sha") or "")[:_SHA],
        "state": str(readback.get("state") or ""),
        "url": str(readback.get("html_url") or ""),
    }
    matches = observed["number"] == number and observed["head_branch"] == head and observed["base_branch"] == base
    return ("confirmed" if matches else "mismatch"), observed


def record_receipt(
    store: Any,
    *,
    owner_principal_id: str,
    repository: str,
    number: int,
    url: str,
    head_branch: str,
    base_branch: str,
    head_sha: str,
    state: str,
    confirmation: Confirmation,
    session_id: str | None = None,
    turn_id: str | None = None,
    action_id: str | None = None,
) -> dict[str, Any]:
    """Store (or refresh) the receipt for one pull request, and return it."""
    now = utc_now()
    receipt_id = new_id("prr_")
    with store.connect() as connection:
        connection.execute(
            """INSERT INTO pull_request_receipts
               (receipt_id, owner_principal_id, repository, number, url, head_branch, base_branch,
                head_sha, state, confirmation, session_id, turn_id, action_id, created_at, confirmed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(owner_principal_id, repository, number) DO UPDATE SET
                 url = excluded.url, head_branch = excluded.head_branch,
                 base_branch = excluded.base_branch, head_sha = excluded.head_sha,
                 state = excluded.state, confirmation = excluded.confirmation,
                 confirmed_at = excluded.confirmed_at""",
            (
                receipt_id, owner_principal_id, repository, int(number), url, head_branch, base_branch,
                head_sha, state, confirmation, session_id, turn_id, action_id, now,
                now if confirmation == "confirmed" else None,
            ),
        )
        row = connection.execute(
            "SELECT * FROM pull_request_receipts WHERE owner_principal_id = ? AND repository = ? AND number = ?",
            (owner_principal_id, repository, int(number)),
        ).fetchone()
    return _view(dict(row))


def list_receipts(
    store: Any, owner_principal_id: str, *, repository: str | None = None, limit: int = 20
) -> list[dict[str, Any]]:
    query = "SELECT * FROM pull_request_receipts WHERE owner_principal_id = ?"
    params: list[Any] = [owner_principal_id]
    if repository:
        query += " AND lower(repository) = lower(?)"
        params.append(repository)
    query += " ORDER BY created_at DESC, rowid DESC LIMIT ?"
    params.append(max(1, min(int(limit), 100)))
    with store.connect() as connection:
        rows = connection.execute(query, params).fetchall()
    return [_view(dict(row)) for row in rows]


def _view(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "receipt_id": str(row["receipt_id"]),
        "repository": str(row["repository"]),
        "number": int(row["number"]),
        "url": str(row["url"]),
        "head_branch": str(row["head_branch"]),
        "base_branch": str(row["base_branch"]),
        "head_sha": str(row["head_sha"]),
        "state": str(row["state"]),
        "confirmation": str(row["confirmation"]),
        "session_id": row.get("session_id"),
        "turn_id": row.get("turn_id"),
        "created_at": str(row["created_at"]),
        "confirmed_at": row.get("confirmed_at"),
    }


def parse_readback(body_text: str) -> dict[str, Any] | None:
    try:
        value = json.loads(body_text)
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


__all__ = ["confirmation_of", "list_receipts", "parse_readback", "record_receipt"]
