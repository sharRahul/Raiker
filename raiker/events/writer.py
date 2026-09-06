from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from raiker.contracts.models import AgentEvent
from raiker.storage.sqlite import SQLiteStore

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl


_SESSION_LOCKS = tuple(threading.RLock() for _ in range(64))


def _striped_lock(path: Path) -> threading.RLock:
    digest = hashlib.sha256(str(path.resolve()).encode("utf-8")).digest()
    return _SESSION_LOCKS[int.from_bytes(digest[:8], "big") % len(_SESSION_LOCKS)]


@contextmanager
def _locked_session(path: Path) -> Iterator[None]:
    """Serialize a session's JSONL append, hash lookup, and index write.

    The fixed process-local stripes keep thread count bounded. A tiny sibling
    lock file also covers a terminal and web host that share one workspace.
    """
    lock_path = path.parent / ".locks" / f"{hashlib.sha256(path.name.encode()).hexdigest()}.lock"
    with _striped_lock(path):
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+b") as handle:
            if handle.seek(0, os.SEEK_END) == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            if sys.platform == "win32":
                deadline = time.monotonic() + 10.0
                while True:
                    try:
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise
                        time.sleep(0.01)
                try:
                    yield
                finally:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class EventLogWriter:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store
        self.events_dir = store.paths.events_dir
        self.events_dir.mkdir(parents=True, exist_ok=True)
        self.last_event_id: str | None = None

    def path_for_session(self, session_id: str) -> Path:
        return self.events_dir / f"{session_id}.jsonl"

    def append(self, event: AgentEvent) -> tuple[Path, int]:
        AgentEvent(**event.to_dict())
        path = self.path_for_session(event.session_id)
        serialised = json.dumps(event.to_dict(), sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(serialised.encode("utf-8")).hexdigest()
        path.parent.mkdir(parents=True, exist_ok=True)
        with _locked_session(path):
            prev_hash = self.store.get_last_event_sha256(event.session_id)
            with path.open("a", encoding="utf-8") as handle:
                offset = handle.tell()
                handle.write(serialised + "\n")
                handle.flush()
            try:
                self.store.index_event(
                    event, str(path), offset, digest, prev_event_sha256=prev_hash
                )
            except Exception:
                # GCR-40 - the file append and the index write are two
                # different stores, and this is the gap between them. An
                # index write that failed used to leave the line behind: a
                # JSONL line the database has never heard of, which the
                # integrity verifier could not see (it starts from the
                # index) and which the *next* append would chain straight
                # past, because `prev_hash` also comes from the database.
                # The physical log and the indexed hash chain then
                # disagreed permanently.
                #
                # The append is undone instead. That is safe precisely
                # here: the session lock is still held, so nothing else has
                # appended, and `offset` is where this line starts, so
                # truncating to it restores the file to what the index
                # still describes. A truncation that itself fails leaves an
                # orphan, which is why `verify_session_events` now scans
                # for lines the index does not know about rather than
                # trusting the index to be complete.
                self._undo_append(path, offset)
                raise
        self.last_event_id = event.event_id
        return path, offset

    @staticmethod
    def _undo_append(path: Path, offset: int) -> None:
        """Cut the log back to ``offset``. Only ever called holding the session lock."""
        try:
            with path.open("r+b") as handle:
                handle.truncate(offset)
                handle.flush()
                os.fsync(handle.fileno())
        except OSError:
            # Reported by the integrity scan rather than raised over the top
            # of the failure that brought us here.
            return
