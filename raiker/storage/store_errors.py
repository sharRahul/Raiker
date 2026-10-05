"""The named conditions under which the encrypted store will not open.

Kept apart from :mod:`raiker.storage.sqlite` so that the application key — which
the store depends on, and which must refuse to be re-minted over a database it
did not create (DEC-24 step 6) — can raise the same condition without importing
the store.
"""

from __future__ import annotations


class StoreUnavailableError(RuntimeError):
    """The encrypted store could not be opened. ``reason`` is a stable code.

    Raised instead of letting a platform-level failure — a locked-memory
    allowance the process cannot satisfy, most of all — surface as a bare
    ``MemoryError`` from inside a request handler. Callers turn it into a named
    condition the owner can act on rather than a generic failure.
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(detail or reason)
        self.reason = reason
        self.detail = detail or reason


#: The workspace's key file is gone while the database it unlocks is still
#: there. A fresh key would open nothing and would sit in the old key's place.
STORE_KEY_MISSING = "store_key_missing"

#: The database exists and this key does not open it — it was made with another
#: key, or the file is damaged. Nothing is written over it.
STORE_UNREADABLE = "store_unreadable"

#: DEC-17 step 8 — the database was shaped by a newer Raiker than this one.
#: Opening it would be a downgrade the migrations cannot undo, so nothing is
#: written; the lock screen offers the backups this build can open.
STORE_SCHEMA_NEWER = "store_schema_newer"


class AppKeyMissingError(StoreUnavailableError):
    """Refused to mint an application key over an existing encrypted store."""

    def __init__(self) -> None:
        super().__init__(
            STORE_KEY_MISSING,
            "The workspace key (.raiker/app.key) is missing, but the database it "
            "unlocks is still here. Raiker will not make a new key, because a new "
            "key cannot open this data and would take the old key's place. Put "
            "the original app.key back from your backup and restart Raiker. "
            "Nothing in the workspace has been changed.",
        )
