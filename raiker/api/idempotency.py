"""Owner-scoped, payload-bound idempotency keys for requests that create (§13.2 item 6).

A creating request that is sent twice — a double click, a retry after a dropped
connection, a tab that resubmitted — made two of whatever it created. For a
task that is two routines, each running on its own schedule and each able to
send a message. §13.2 item 6 asks for idempotency keys that are *owner-scoped*
and *payload-bound*, with a reused key on changed arguments refused.

So a request may carry ``Idempotency-Key``:

* **Same owner, same key, same body** → the first answer, again, and nothing
  is created a second time.
* **Same key, different body** → ``409 idempotency_key_reused``. The key names
  one request; reusing it for another is a client error, not a new request.
* **Same key while the first is still running** → ``409
  idempotency_key_in_progress``, rather than racing it.
* **Another owner's key** is a different key: the scope includes the principal.

Keys live for :data:`KEY_TTL_HOURS`; a key is a retry handle, not a record. A
request without the header behaves exactly as before.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import status

from raiker.api.refusals import refusal
from raiker.contracts.ids import utc_now
from raiker.storage.sqlite import SQLiteStore

KEY_TTL_HOURS = 24
_KEY = re.compile(r"^[A-Za-z0-9_.:-]{8,128}$")


def payload_digest(payload: Any) -> str:
    """A stable digest of a request body: key order and whitespace do not matter."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class IdempotencyGuard:
    """One creating request's claim on its key, from reservation to answer."""

    def __init__(self, store: SQLiteStore, owner_principal_id: str, scope: str, key: str | None) -> None:
        self.store = store
        self.owner = owner_principal_id
        self.scope = scope
        self.key = key
        self._reserved = False

    def begin(self, payload: Any) -> dict[str, Any] | None:
        """Reserve the key, or return the answer a matching earlier request already got.

        Raises the 409 refusals above. Returns ``None`` when this request should
        go ahead and create.
        """
        if self.key is None:
            return None
        if not _KEY.fullmatch(self.key):
            raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, "idempotency_key_invalid")
        digest = payload_digest(payload)
        cutoff = (datetime.now(UTC) - timedelta(hours=KEY_TTL_HOURS)).isoformat().replace("+00:00", "Z")
        with self.store.connect() as connection:
            connection.execute("DELETE FROM idempotency_keys WHERE created_at < ?", (cutoff,))
            row = connection.execute(
                "SELECT payload_sha256, response_json FROM idempotency_keys "
                "WHERE owner_principal_id = ? AND scope = ? AND idempotency_key = ?",
                (self.owner, self.scope, self.key),
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO idempotency_keys (owner_principal_id, scope, idempotency_key, "
                    "payload_sha256, response_json, created_at) VALUES (?, ?, ?, ?, NULL, ?)",
                    (self.owner, self.scope, self.key, digest, utc_now()),
                )
                self._reserved = True
                return None
        if str(row["payload_sha256"]) != digest:
            raise refusal(status.HTTP_409_CONFLICT, "idempotency_key_reused")
        if row["response_json"] is None:
            raise refusal(status.HTTP_409_CONFLICT, "idempotency_key_in_progress")
        answer: dict[str, Any] = json.loads(str(row["response_json"]))
        return answer

    def complete(self, answer: dict[str, Any]) -> None:
        """Record the answer a retry of this request will be given."""
        if not self._reserved:
            return
        with self.store.connect() as connection:
            connection.execute(
                "UPDATE idempotency_keys SET response_json = ? "
                "WHERE owner_principal_id = ? AND scope = ? AND idempotency_key = ?",
                (json.dumps(answer, default=str), self.owner, self.scope, self.key),
            )

    def abandon(self) -> None:
        """Release the key after a refusal, so a corrected retry is not held."""
        if not self._reserved:
            return
        with self.store.connect() as connection:
            connection.execute(
                "DELETE FROM idempotency_keys WHERE owner_principal_id = ? AND scope = ? "
                "AND idempotency_key = ? AND response_json IS NULL",
                (self.owner, self.scope, self.key),
            )
        self._reserved = False
