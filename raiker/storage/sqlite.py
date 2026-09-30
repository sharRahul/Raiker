from __future__ import annotations

import atexit
import contextlib
import hashlib
import itertools
import logging
import os
import threading
import weakref
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlcipher3 import dbapi2 as sqlite3  # type: ignore[import-untyped]

from raiker.auth.app_key import ensure_app_key
from raiker.contracts.ids import utc_now
from raiker.storage.internal_paths import internal_io_path
from raiker.storage.migrations import (
    TEXT_SEARCH_FTS4,
    TEXT_SEARCH_FTS5,
    TEXT_SEARCH_FTS5_MIGRATION_ID,
    conversation_fts_sql,
    managed_file_chunk_fts_sql,
    memory_sqlcipher_fts_sql,
)
from raiker.storage.sqlcipher_probe import MemorySecurityProbeResult, probe_memory_security

# ── The keyed-connection cache ───────────────────────────────────────────────
#
# SQLCipher derives its key when a connection opens, and routes build stores
# freely, so each workspace keeps one keyed connection per worker thread for the
# host's lifetime instead of paying the KDF per request. Invariants:
#
# * A connection runs queries only in the thread that owns it.
#   ``check_same_thread=False`` exists so shutdown can close handles centrally.
# * A thread closes only its own handles, or those of threads that have exited.
#   ``connect`` has no release point, so another live worker's handle may be
#   mid-query, and closing it would be a use-after-close.
# * The cache is bounded twice, least-recently-used: a per-thread limit, and an
#   absolute process ceiling on key-bearing connections, because each holds key
#   material that may be spent against a locked-memory allowance of a few
#   megabytes (BUG-50, BUG-86). A thread's allowance is whichever is smaller.

# BUG-243 — words a full-text AND must not be allowed to require.
#
# Deliberately short and deliberately closed-class: articles, pronouns,
# auxiliaries, prepositions and the question words. Every one of them is a word
# an owner types when asking rather than when naming, and none of them is a term
# anyone searches *for*. Nothing here is a domain word, so no query about
# Raiker's own subject matter loses a term it needed.
_SEARCH_STOPWORDS = frozenset({
    "about", "after", "again", "all", "already", "also", "and", "any", "anything",
    "are", "aren", "around", "because", "been", "before", "being", "but", "can",
    "cannot", "could", "did", "didn", "does", "doesn", "doing", "don", "each",
    "either", "else", "ever", "every", "for", "from", "get", "got", "had", "has",
    "have", "her", "here", "hers", "him", "his", "how", "into", "isn", "its",
    "just", "know", "let", "like", "made", "make", "many", "may", "me", "might",
    "mine", "more", "most", "much", "must", "need", "not", "now", "off", "one",
    "only", "onto", "our", "ours", "out", "over", "own", "please", "put", "same",
    "say", "see", "she", "should", "show", "since", "some", "something", "still",
    "such", "sure", "tell", "than", "that", "the", "their", "theirs", "them",
    "then", "there", "these", "they", "thing", "things", "this", "those",
    "through", "too", "under", "until", "upon", "use", "used", "using", "very",
    "want", "was", "wasn", "way", "well", "were", "what", "when", "where",
    "which", "while", "who", "whom", "whose", "why", "will", "with", "won",
    "would", "you", "your", "yours",
})

_CONNECTION_CACHE_LIMIT_ENV = "RAIKER_SQLITE_CONNECTION_CACHE_LIMIT"
_DEFAULT_CONNECTION_CACHE_LIMIT = 8
_CONNECTION_CACHE_CEILING_ENV = "RAIKER_SQLITE_CONNECTION_CACHE_CEILING"
_DEFAULT_CONNECTION_CACHE_CEILING = 16
_CONNECTIONS: OrderedDict[tuple[Path, int], sqlite3.Connection] = OrderedDict()
_CONNECTIONS_LOCK = threading.RLock()

# ── Who owns a cached connection (GCR-37) ────────────────────────────────────
#
# A token this module mints, held in thread-local storage — never the thread's
# identifier, which the platform recycles once a thread exits, so a new worker
# could otherwise adopt a retired worker's handle and session state. A weak
# reference to the owning ``Thread`` answers whether that owner is still alive.
_OWNER_TOKENS = threading.local()
_OWNER_SEQUENCE = itertools.count(1)
_OWNER_THREADS: dict[int, weakref.ReferenceType[threading.Thread]] = {}
# Handles invalidation took out of the cache while their owning thread was still
# running — a shutdown can arrive while a cancelled ``to_thread`` worker is
# still mid-statement, because cancelling the awaiting task does not stop the
# thread. Closing one there is a use-after-close in that worker, which SQLCipher
# answers with a segfault. So the owner closes its own on its next ``connect``,
# and a handle whose owner has since exited is closed by whoever notices.
_RETIRED: dict[int, list[sqlite3.Connection]] = {}
# Schema/FTS bootstrap uses multiple statements and must not race another store
# instance in this process. SQLite's busy timeout cannot resolve two deferred
# transactions that both try to upgrade to writers.
_BOOTSTRAP_LOCK = threading.RLock()
_LOG = logging.getLogger(__name__)
# The model-operation columns a lifecycle write may set. An allowlist, so a
# transition can never reach the owner, the kind, the recorded payload, or the
# creation time — the parts of the row that identify what the job *is*.
_OPERATION_COLUMNS = frozenset(
    {
        "state",
        "phase",
        "progress_bytes",
        "total_bytes",
        "progress_percent",
        "error_code",
        "error_detail",
    }
)


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


def connection_cache_limit() -> int:
    """How many keyed connections one worker thread may hold open at once."""
    raw = os.environ.get(_CONNECTION_CACHE_LIMIT_ENV, "").strip()
    if raw:
        with contextlib.suppress(ValueError):
            declared = int(raw)
            if declared > 0:
                return declared
    return _DEFAULT_CONNECTION_CACHE_LIMIT


def connection_cache_ceiling() -> int:
    """The most keyed connections this process will cache, across all threads.

    An absolute count, never a multiple of the thread count: it is what bounds
    the locked pages SQLCipher asks the platform for.
    """
    raw = os.environ.get(_CONNECTION_CACHE_CEILING_ENV, "").strip()
    declared = _DEFAULT_CONNECTION_CACHE_CEILING
    if raw:
        with contextlib.suppress(ValueError):
            parsed = int(raw)
            if parsed > 0:
                declared = parsed
    # A ceiling under the per-thread limit would be self-contradictory; the
    # per-thread limit is what one thread may hold, so it is the floor here.
    return max(connection_cache_limit(), declared)


def cached_connection_count() -> int:
    """Cached connections held by this process, across every worker thread."""
    with _CONNECTIONS_LOCK:
        return len(_CONNECTIONS)


# ── SQLCipher memory security (BUG-86, BUG-46) ───────────────────────────────
#
# SQLCipher can lock the pages that hold key material so they are never paged to
# disk. Locking draws on a per-process allowance the operating system sets, and
# that allowance is small by default — 8 MB on the Linux host where BUG-86 was
# reproduced, a working-set quota on Windows. When it is spent, opening a keyed
# connection fails with ``MemoryError`` and *every* request fails with it,
# because authentication opens the store.
#
# The decision, stated rather than left implicit: **the pragma is set on every
# connection, and it is off unless the owner asks for it.** Two facts decide it,
# and both were measured rather than assumed:
#
# * **Cost.** Memory security makes SQLCipher lock and wipe its buffers around
#   every operation. Opening a workspace and running two hundred reads takes
#   0.17 s with it off and 1.14 s with it on — about seven times. SQLCipher
#   itself defaults it off in 4.x for this reason.
# * **Failure mode.** When the platform's locked-memory allowance runs out the
#   failure is not degraded performance, it is `MemoryError` on *every* request,
#   because authentication opens the store. That is BUG-86, and BUG-46 before it.
#
# So Raiker does not lock key pages by default, and says so rather than leaving
# it to whatever SQLCipher was built with: `GET /api/health` reports the setting,
# the reason, and the allowance the platform would have given. An owner who wants
# the stronger posture sets ``RAIKER_SQLCIPHER_MEMORY_SECURITY=on``, and because
# that is their decision it is honoured exactly — a refused lock then fails
# **closed**, by name, instead of surfacing as a bare ``MemoryError``.
#
# BUG-205 — one property of the pragma is not a Raiker decision and has to be
# recorded rather than assumed: in the bundled SQLCipher build it is
# **process-global and latches one way**. Once any connection in the process has
# opened with it ON, every later connection reads back ON, whatever it was told.
# Measured directly:
#
#     resolve off → open                        → reads 0
#     resolve off → open → resolve on  → open   → reads 1   (the raise takes)
#     resolve on  → open → resolve off → open   → reads 1   (the drop does not)
#
# The latch only sticks in the *safe* direction — a run that asked for ``on``
# can never quietly end up ``off`` — so it costs performance, never protection.
# It is still a real divergence between what Raiker resolved and what the
# process is doing, so the process remembers whether it has ever enabled the
# pragma and says so on the health surface instead of letting intent stand in
# for fact.
_MEMORY_SECURITY_ENV = "RAIKER_SQLCIPHER_MEMORY_SECURITY"
_MEMORY_SECURITY_LOCK = threading.Lock()
_MEMORY_SECURITY: tuple[bool, str] | None = None
_MEMORY_SECURITY_PROBE: MemorySecurityProbeResult | None = None
_MEMORY_SECURITY_MODE = "auto"
_MEMORY_SECURITY_EVER_ENABLED = False


def memory_security_ever_enabled() -> bool:
    """Has any connection in *this process* opened with the pragma enabled?

    While this is false the resolved posture and the pragma in force are the
    same thing. Once it is true the pragma cannot be lowered again for the life
    of the process, so a later ``off`` resolution is an intent the build will
    not honour — which the posture reports rather than hides (BUG-205).
    """
    return _MEMORY_SECURITY_EVER_ENABLED


def memlock_allowance_bytes() -> int | None:
    """The process's locked-memory allowance, or ``None`` where unreadable.

    Reported so an owner deciding whether to turn memory security on can see
    what the platform would actually give them. ``-1`` from ``getrlimit`` means
    unlimited. Windows reports nothing here, which is itself worth showing.
    """
    try:
        import resource  # noqa: PLC0415 - POSIX only, imported where it is used
    except ImportError:
        return None
    getrlimit = getattr(resource, "getrlimit", None)
    memlock = getattr(resource, "RLIMIT_MEMLOCK", None)
    if not callable(getrlimit) or memlock is None:
        return None
    try:
        soft, _hard = getrlimit(memlock)
    except (OSError, ValueError):
        return None
    if soft < 0:
        return -1 if soft == -1 else None
    return int(soft)


def resolve_memory_security(
    workspace_root: str | Path | None = None, *, refresh: bool = False
) -> tuple[bool, str]:
    """``(enabled, reason)`` for ``PRAGMA cipher_memory_security``.

    Off unless the owner asks for it, for the two reasons in the note above:
    locking costs roughly seven times on every store operation, and when the
    platform's allowance runs out the failure is a total lockout rather than
    slow work. Resolved once per process and reported verbatim on the health
    endpoint. ``refresh`` re-resolves it, which only tests need.
    """
    global _MEMORY_SECURITY, _MEMORY_SECURITY_MODE, _MEMORY_SECURITY_PROBE
    with _MEMORY_SECURITY_LOCK:
        if _MEMORY_SECURITY is not None and not refresh:
            return _MEMORY_SECURITY
        declared = os.environ.get(_MEMORY_SECURITY_ENV, "").strip().casefold()
        if declared in {"off", "0", "false", "no"}:
            _MEMORY_SECURITY_MODE = "off"
            _MEMORY_SECURITY_PROBE = None
            resolved = (False, "requested_off")
        else:
            _MEMORY_SECURITY_MODE = "on" if declared in {"on", "1", "true", "yes"} else "auto"
            probe_root = Path(workspace_root or Path.cwd())
            _MEMORY_SECURITY_PROBE = probe_memory_security(probe_root)
            if _MEMORY_SECURITY_PROBE.supported:
                resolved = (
                    True,
                    "requested_on" if _MEMORY_SECURITY_MODE == "on" else "auto_probe_supported",
                )
            elif _MEMORY_SECURITY_MODE == "on":
                resolved = (
                    False,
                    f"required_but_unavailable_{_MEMORY_SECURITY_PROBE.reason_code}",
                )
            else:
                resolved = (False, f"auto_probe_{_MEMORY_SECURITY_PROBE.reason_code}")
        _MEMORY_SECURITY = resolved
        if not resolved[0]:
            # Recorded, not silent: running without locked key pages is a real
            # posture, and the owner is entitled to see which one they are on.
            _LOG.info(
                "SQLCipher memory security is off (%s); workspace key pages are "
                "not locked into RAM. Set %s=on to change that.",
                resolved[1],
                _MEMORY_SECURITY_ENV,
            )
        return resolved


def memory_security_posture(workspace_root: str | Path | None = None) -> dict[str, Any]:
    """What the health endpoint and the security posture page both read."""
    enabled, reason = resolve_memory_security(workspace_root)
    probe = _MEMORY_SECURITY_PROBE
    return {
        "cipher_memory_security": "on" if enabled else "off",
        # BUG-205 — what the *process* is actually doing, kept beside what was
        # resolved rather than replacing it. They are the same thing for any
        # normal run, and can differ in exactly one direction: a process that has
        # already enabled the pragma keeps it enabled for its lifetime, so an
        # `off` resolved after that is an intent the build will not honour. The
        # divergence costs performance, never protection — but reporting only the
        # intent would let health say `off` while every connection was `on`.
        "memory_security_in_force": ("on" if enabled or _MEMORY_SECURITY_EVER_ENABLED else "off"),
        # Deliberately not "reason": the store's own reason travels beside this
        # one on the health view, and two keys of the same name would let the
        # posture overwrite the failure — the kind of quiet contradiction this
        # bug is about.
        "memory_security_reason": reason,
        "memory_security_mode": _MEMORY_SECURITY_MODE,
        "memory_security_probe": (
            "not_run" if probe is None else "supported" if probe.supported else "failed"
        ),
        "memory_security_checked_at": probe.checked_at if probe is not None else None,
        "sqlcipher_version": probe.sqlcipher_version if probe is not None else None,
        # -1 means unlimited; null means the platform would not say.
        "memlock_allowance_bytes": memlock_allowance_bytes(),
        "connection_ceiling": connection_cache_ceiling(),
    }


def text_search_posture(store: SQLiteStore) -> dict[str, Any]:
    """Which text-search engine is really in force, and what it costs.

    Three keys rather than one, because "fts4" alone means nothing to a reader
    who has not read the migration: `text_search_ranking` says what they will
    actually notice, and `text_search_reason` says whether the fallback is a
    problem to fix or simply what this platform has.
    """
    engine = store.resolved_text_search_engine()
    ranked = engine == TEXT_SEARCH_FTS5
    return {
        "text_search_engine": engine,
        "text_search_ranking": "bm25_relevance" if ranked else "recency",
        "text_search_reason": (
            ""
            if ranked
            else "this SQLite build has no FTS5, so search ranks by recency rather "
            "than relevance (sqlcipher3-wheels 0.5.6 or newer provides it)"
        ),
    }


def store_health(workspace_root: str | Path) -> dict[str, Any]:
    """Whether the encrypted store can actually be opened and read, right now.

    BUG-86 — the health probe used to answer "ok" without touching the store,
    so the lock screen could report the runtime operational in the same breath
    as refusing every sign-in. This is the one probe both statements read.
    """
    posture = memory_security_posture(workspace_root)
    try:
        store = SQLiteStore(workspace_root)
        store.connect().execute("SELECT 1")
        # RAIKER-2025 — reported for the same reason `cipher_memory_security`
        # is: it is a property of the build this process loaded, not of any
        # configuration, and the degraded case is *silent*. An FTS4 fallback
        # breaks nothing and answers everything — it just ranks by recency
        # instead of relevance, which is indistinguishable from working unless
        # something says so.
        posture = {**posture, **text_search_posture(store)}
    except StoreUnavailableError as exc:
        return {"store": "unavailable", "reason": exc.reason, "detail": exc.detail, **posture}
    except MemoryError:
        return {
            "store": "unavailable",
            "reason": "store_memory_lock_unavailable",
            "detail": "This machine would not give SQLCipher the memory it needs to "
            "open the workspace database.",
            **posture,
        }
    except Exception as exc:  # noqa: BLE001 - any open failure is one condition here
        return {
            "store": "unavailable",
            "reason": "store_open_failed",
            "detail": type(exc).__name__,
            **posture,
        }
    return {"store": "ok", "reason": "", "detail": "", **posture}


def _owner_token() -> int:
    """This thread's ownership token, minted once and never reused.

    Unlike a thread identifier, the token is not returned to a pool when the
    thread exits, so a later thread can never be mistaken for this one.
    """
    token: int | None = getattr(_OWNER_TOKENS, "value", None)
    if token is None:
        token = next(_OWNER_SEQUENCE)
        _OWNER_TOKENS.value = token
        with _CONNECTIONS_LOCK:
            _OWNER_THREADS[token] = weakref.ref(threading.current_thread())
    return token


def _live_owners_locked() -> set[int]:
    """The tokens whose owning thread is still running.

    A token whose thread has exited and whose connections are already gone is
    forgotten here, so the registry does not outgrow the cache it describes.
    Called with ``_CONNECTIONS_LOCK`` held.
    """
    live: set[int] = set()
    retired: list[int] = []
    for token, reference in _OWNER_THREADS.items():
        thread = reference()
        if thread is not None and thread.is_alive():
            live.add(token)
        else:
            retired.append(token)
    held = {key[1] for key in _CONNECTIONS} | set(_RETIRED)
    for token in retired:
        if token not in held:
            _OWNER_THREADS.pop(token, None)
    return live


def _evictable_locked(owner: int) -> list[sqlite3.Connection]:
    """Handles this thread may close: its own stalest, plus any dead thread's.

    Called with ``_CONNECTIONS_LOCK`` held; the caller closes what it returns
    outside the lock, exactly as invalidation does.
    """
    live = _live_owners_locked()
    evicted: list[sqlite3.Connection] = []
    orphans = [key for key in _CONNECTIONS if key[1] != owner and key[1] not in live]
    for key in orphans:
        evicted.append(_CONNECTIONS.pop(key))
    owners = {key[1] for key in _CONNECTIONS} | {owner}
    allowance = max(1, min(connection_cache_limit(), connection_cache_ceiling() // len(owners)))
    # ``_CONNECTIONS`` is ordered least-recently-used first, so walking it in
    # order drops this thread's stalest workspaces before its warm ones.
    mine = [key for key in _CONNECTIONS if key[1] == owner]
    for key in mine[: max(len(mine) - allowance, 0)]:
        evicted.append(_CONNECTIONS.pop(key))
    return evicted


def _releasable_locked(owner: int) -> list[sqlite3.Connection]:
    """Every handle this thread is allowed to close, under memory pressure.

    Its own — it holds none of them mid-query, since it is here — plus any
    belonging to a thread that has exited. Another live worker's handle is
    still never touched: closing one would be a use-after-close in that worker.
    Called with ``_CONNECTIONS_LOCK`` held.
    """
    live = _live_owners_locked()
    doomed = [key for key in _CONNECTIONS if key[1] == owner or key[1] not in live]
    return [_CONNECTIONS.pop(key) for key in doomed]


def _reap_retired_locked(owner: int) -> list[sqlite3.Connection]:
    """Retired handles now safe to close: this thread's own, and any dead thread's.

    Called with ``_CONNECTIONS_LOCK`` held; the caller closes what it returns.
    """
    live = _live_owners_locked()
    due = [token for token in _RETIRED if token == owner or token not in live]
    return [connection for token in due for connection in _RETIRED.pop(token)]


def invalidate_workspace_connections(workspace_root: str | Path) -> None:
    """Take every cached SQLCipher connection for one workspace out of use.

    Every handle leaves the cache at once, so nothing reuses one afterwards.
    Only this thread's own and those of threads that have exited are closed
    here; a live worker's is retired, to be closed by that worker on its next
    ``connect`` — never under it (see ``_RETIRED``).
    """
    root = Path(workspace_root).resolve()
    owner = _owner_token()
    with _CONNECTIONS_LOCK:
        live = _live_owners_locked()
        doomed = [key for key in _CONNECTIONS if key[0] == root]
        connections: list[sqlite3.Connection] = []
        for key in doomed:
            connection = _CONNECTIONS.pop(key)
            if key[1] == owner or key[1] not in live:
                connections.append(connection)
            else:
                _RETIRED.setdefault(key[1], []).append(connection)
        connections += _reap_retired_locked(owner)
    for connection in connections:
        with contextlib.suppress(Exception):
            connection.close()


def close_cached_connections() -> None:
    """Close all keyed connections during process shutdown."""
    with _CONNECTIONS_LOCK:
        connections = list(_CONNECTIONS.values())
        connections += [handle for handles in _RETIRED.values() for handle in handles]
        _CONNECTIONS.clear()
        _RETIRED.clear()
        _OWNER_THREADS.clear()
    for connection in connections:
        with contextlib.suppress(Exception):
            connection.close()


atexit.register(close_cached_connections)


@dataclass(frozen=True)
class RuntimePaths:
    workspace_root: Path

    @property
    def runtime_dir(self) -> Path:
        return internal_io_path(self.workspace_root / ".raiker")

    @property
    def db_path(self) -> Path:
        return self.runtime_dir / "raiker.db"

    @property
    def events_dir(self) -> Path:
        return self.runtime_dir / "events"

    @property
    def checkpoints_dir(self) -> Path:
        return self.runtime_dir / "checkpoints"

    @property
    def artifacts_dir(self) -> Path:
        return self.runtime_dir / "artifacts"

    @property
    def indexes_dir(self) -> Path:
        return self.runtime_dir / "indexes"

    def ensure(self) -> None:
        for path in (
            self.runtime_dir,
            self.events_dir,
            self.checkpoints_dir,
            self.artifacts_dir,
            self.indexes_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


# GCR-11 — the store is one class assembled from one part per domain. The parts
# live in `raiker/storage/stores/` and import the connection helpers above, so
# they are imported here, after those helpers exist and before the class that
# inherits them. This module keeps what every part shares: the SQLCipher
# connection, its cache and memory-security posture, and the text-search engine.
from raiker.storage.stores.accounts import AccountStore  # noqa: E402
from raiker.storage.stores.approvals import ApprovalStore  # noqa: E402
from raiker.storage.stores.attachments import AttachmentStore  # noqa: E402
from raiker.storage.stores.code import CodeStore  # noqa: E402
from raiker.storage.stores.conversations import ConversationStore  # noqa: E402
from raiker.storage.stores.execution import ExecutionStore  # noqa: E402
from raiker.storage.stores.extensions import ExtensionStore  # noqa: E402
from raiker.storage.stores.governance import GovernanceStore  # noqa: E402
from raiker.storage.stores.knowledge import KnowledgeStore  # noqa: E402
from raiker.storage.stores.memory import MemoryStore  # noqa: E402
from raiker.storage.stores.migration_runner import MigrationRunner  # noqa: E402
from raiker.storage.stores.models import ModelStore  # noqa: E402
from raiker.storage.stores.monitoring import MonitoringStore  # noqa: E402
from raiker.storage.stores.projects import ProjectStore  # noqa: E402
from raiker.storage.stores.records import RecordStore  # noqa: E402
from raiker.storage.stores.tasks import TaskStore  # noqa: E402


class SQLiteStore(
    MigrationRunner,
    AccountStore,
    ApprovalStore,
    AttachmentStore,
    CodeStore,
    ConversationStore,
    ExecutionStore,
    ExtensionStore,
    GovernanceStore,
    KnowledgeStore,
    MemoryStore,
    ModelStore,
    MonitoringStore,
    ProjectStore,
    RecordStore,
    TaskStore,
):
    #: The migration ids this database already records, read once at the top of
    #: a :meth:`bootstrap` pass and ``None`` outside one, so a pass asks the
    #: ``migrations`` table once rather than once per migration (GCR-10).
    #:
    #: The pass itself still runs on every construction: it is the store's
    #: self-repair — a deleted marker's migration is re-applied, a legacy FTS4
    #: index converted, a legacy project path rebuilt — and
    #: ``test_repeated_store_facade_rechecks_deleted_migration_marker`` holds it.
    _applied: set[str] | None = None

    def __init__(self, workspace_root: str | Path) -> None:
        self.paths = RuntimePaths(Path(workspace_root).resolve())
        self.paths.ensure()
        self.db_path = self.paths.db_path
        with _BOOTSTRAP_LOCK:
            self.bootstrap()

    def _open_keyed(self) -> sqlite3.Connection:
        """Open one keyed connection under the resolved memory-security policy."""
        connection = sqlite3.connect(str(self.db_path), timeout=5.0, check_same_thread=False)
        try:
            memory_security, reason = resolve_memory_security(self.paths.workspace_root)
            if reason.startswith("required_but_unavailable_"):
                raise StoreUnavailableError(
                    "store_memory_lock_unavailable",
                    "This machine could not prove that SQLCipher can lock key-bearing "
                    "memory pages while RAIKER_SQLCIPHER_MEMORY_SECURITY=on is required.",
                )
            # Set before the key: the pragma governs how the key material about
            # to be derived is held, so afterwards would be too late.
            connection.execute(
                f"PRAGMA cipher_memory_security = {'ON' if memory_security else 'OFF'}"
            )
            if memory_security:
                # BUG-205 — from here on the process is latched ON and cannot be
                # lowered. Recorded so the posture reports the pragma in force
                # rather than the last thing that was resolved.
                global _MEMORY_SECURITY_EVER_ENABLED
                _MEMORY_SECURITY_EVER_ENABLED = True
            key_hex = hashlib.sha256(ensure_app_key(self.paths.workspace_root)).hexdigest()
            connection.execute(f"PRAGMA key = \"x'{key_hex}'\"")
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 5000")
        except BaseException:
            with contextlib.suppress(Exception):
                connection.close()
            raise
        return connection

    def connect(self) -> sqlite3.Connection:
        owner = _owner_token()
        cache_key = (self.paths.workspace_root, owner)
        with _CONNECTIONS_LOCK:
            retired = _reap_retired_locked(owner) if _RETIRED else []
        # This thread is not mid-statement on any of them — it is here.
        for stale in retired:
            with contextlib.suppress(Exception):
                stale.close()
        with _CONNECTIONS_LOCK:
            connection = _CONNECTIONS.get(cache_key)
            if connection is not None:
                try:
                    connection.execute("SELECT 1")
                    _CONNECTIONS.move_to_end(cache_key)
                    return connection
                except (sqlite3.Error, MemoryError):
                    # A cached handle whose key pages the platform has taken
                    # back answers this probe with MemoryError, not sqlite3.
                    # Either way it is unusable and is replaced, not returned.
                    _CONNECTIONS.pop(cache_key, None)
                    with contextlib.suppress(Exception):
                        connection.close()
            try:
                connection = self._open_keyed()
            except MemoryError as exc:
                # The platform refused the locked pages SQLCipher asked for. Give
                # back everything this thread may release and try once more; if
                # the policy was Raiker's own choice rather than the owner's,
                # fall back to running without memory security and record it.
                connection = self._reopen_after_memory_error(exc)
            # A fresh key, so this appends: the newest connection is the most
            # recently used one and the last thing eviction would reach for.
            _CONNECTIONS[cache_key] = connection
            evicted = _evictable_locked(owner)
        for stale in evicted:
            with contextlib.suppress(Exception):
                stale.close()
        return connection

    # OPT-06. One statement in its own transaction — commit on success,
    # rollback on error — which is what 330 hand-written `with self.connect()`
    # blocks around a single `execute` each were. A method that runs two
    # statements, or reads its cursor in between, still opens the block itself,
    # so a transaction boundary is never hidden behind a helper.

    def _rows(self, sql: str, params: Any = ()) -> list[sqlite3.Row]:
        with self.connect() as connection:
            return connection.execute(sql, params).fetchall()

    def _row(self, sql: str, params: Any = ()) -> sqlite3.Row | None:
        with self.connect() as connection:
            row: sqlite3.Row | None = connection.execute(sql, params).fetchone()
            return row

    def _execute(self, sql: str, params: Any = ()) -> int:
        """Run one statement and return how many rows it changed."""
        with self.connect() as connection:
            return connection.execute(sql, params).rowcount

    def _reopen_after_memory_error(self, error: MemoryError) -> sqlite3.Connection:
        """Recover a keyed connection after a memory refusal, or fail named.

        Give back every handle this thread may release — the population of
        key-bearing connections is the thing most likely to have exhausted the
        allowance — and try once more. If it still refuses, the condition is
        named rather than left as a bare ``MemoryError`` escaping a request
        handler. Called with ``_CONNECTIONS_LOCK`` held.
        """
        for stale in _releasable_locked(_owner_token()):
            with contextlib.suppress(Exception):
                stale.close()
        with contextlib.suppress(MemoryError, sqlite3.Error):
            return self._open_keyed()
        enabled, _reason = resolve_memory_security(self.paths.workspace_root)
        detail = (
            "This machine would not lock the memory pages SQLCipher holds the "
            "workspace key in. Memory security is on because "
            f"{_MEMORY_SECURITY_ENV}=on was set; unset it to run without locked "
            "key pages."
            if enabled
            else "This machine would not give SQLCipher the memory it needs to "
            "open the workspace database."
        )
        raise StoreUnavailableError("store_memory_lock_unavailable", detail) from error

    # ── Text-search engine (RAIKER-2025) ─────────────────────────────────────

    #: Probed once per process. The answer is a property of the SQLite library
    #: this interpreter loaded, not of any one workspace, and creating a throwaway
    #: virtual table on every store construction would be a measurable cost on a
    #: process that opens many.
    _text_search_engine: str | None = None

    @classmethod
    def text_search_engine(cls, connection: sqlite3.Connection) -> str:
        """Which full-text engine this build actually has. Measured, not declared.

        ``PRAGMA compile_options`` is not consulted: a build can report
        ``ENABLE_FTS5`` and still refuse the module if it was linked without it,
        and the only question that matters here is whether the table can be
        created. So one is created, in ``temp``, and dropped again.
        """
        if cls._text_search_engine is not None:
            return cls._text_search_engine
        engine = TEXT_SEARCH_FTS4
        try:
            connection.execute("CREATE VIRTUAL TABLE temp.raiker_fts5_probe USING fts5(probe)")
        except sqlite3.Error:
            pass
        else:
            engine = TEXT_SEARCH_FTS5
            with contextlib.suppress(sqlite3.Error):
                connection.execute("DROP TABLE temp.raiker_fts5_probe")
        cls._text_search_engine = engine
        return engine

    def resolved_text_search_engine(self) -> str:
        """The engine, probing once if a search runs before any migration did."""
        if SQLiteStore._text_search_engine is None:
            with self.connect() as connection:
                return self.text_search_engine(connection)
        return SQLiteStore._text_search_engine

    def _snippet_expression(self, table: str, column: int) -> str:
        """`snippet()` for whichever engine holds *table*.

        The two engines take the same six arguments in a different order, and
        FTS4 numbers the column *after* the markers while FTS5 numbers it first.
        Getting that wrong does not raise — FTS4 would read `18` as the column
        index and return NULL for every row — so the order is derived from the
        probe rather than written once and assumed.
        """
        if self.resolved_text_search_engine() == TEXT_SEARCH_FTS5:
            return f"snippet({table}, {column}, '', '', '…', 18)"
        return f"snippet({table}, '', '', '…', {column}, 18)"

    @staticmethod
    def _index_engine(connection: sqlite3.Connection, table: str) -> str | None:
        """The engine an existing index was built on, read from its own DDL."""
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
        ).fetchone()
        if row is None or not row[0]:
            return None
        ddl = str(row[0]).lower()
        for engine in (TEXT_SEARCH_FTS5, TEXT_SEARCH_FTS4):
            if f"using {engine}" in ddl:
                return engine
        return None

    def _migrate_text_search_engine(self, connection: sqlite3.Connection) -> None:
        """Move both rebuildable text indexes onto FTS5 where the build has it.

        Written as a method rather than a SQL script because the decision is
        conditional on a probe and the rebuild reads the governed tables. Each
        index is converted independently and idempotently: a workspace that is
        interrupted halfway is completed on the next open, and one that is
        already FTS5 costs two `sqlite_master` reads.
        """
        if self.text_search_engine(connection) != TEXT_SEARCH_FTS5:
            return
        converted = False
        for table, rebuild in (
            ("approved_memory_fts", self._rebuild_memory_fts),
            ("conversation_fts", self._rebuild_conversation_fts),
            ("managed_file_chunk_fts", self._rebuild_managed_file_chunk_fts),
        ):
            if self._index_engine(connection, table) != TEXT_SEARCH_FTS4:
                continue
            # Dropping before creating is safe precisely because the index is a
            # projection: every row in it is recomputed from the table that owns
            # the content. Nothing the owner approved lives only here.
            connection.execute(f"DROP TABLE IF EXISTS {table}")
            # `memory_sqlcipher_fts_sql` rather than `memory_fts_sql`: the two
            # differ only in that the latter also seeds the index from
            # `approved_memory`, which `rebuild` does properly a line later —
            # with the archival, expiry and supersession filters this one omits.
            if table == "approved_memory_fts":
                script = memory_sqlcipher_fts_sql(TEXT_SEARCH_FTS5)
            elif table == "conversation_fts":
                script = conversation_fts_sql(TEXT_SEARCH_FTS5)
            else:
                script = managed_file_chunk_fts_sql(TEXT_SEARCH_FTS5)
            connection.executescript(script)
            rebuild(connection)
            converted = True
        if (
            converted
            or connection.execute(
                "SELECT 1 FROM migrations WHERE migration_id = ?", (TEXT_SEARCH_FTS5_MIGRATION_ID,)
            ).fetchone()
            is None
        ):
            connection.execute(
                "INSERT OR IGNORE INTO migrations (migration_id, applied_at) VALUES (?, ?)",
                (TEXT_SEARCH_FTS5_MIGRATION_ID, utc_now()),
            )

    @staticmethod
    def _original_owner_from_connection(connection: sqlite3.Connection) -> str | None:
        """The live principal that owns this instance's unattributed data.

        The guard row is the authority: it names the instance's sole account and
        recovery repoints it, so it survives an owner replacement. The role scan
        is the fallback for databases predating the guard, and only ever
        considers *active* principals — recovery deactivates the old owner but
        leaves its ``rl_owner`` role and its earlier ``created_at``, so an
        unfiltered scan would keep resolving to the dead principal and file all
        new data against it.
        """
        # The backfills call this during bootstrap, before the migration that
        # creates the guard has run, so its absence is expected here.
        guard_exists = (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'instance_account_guard'"
            ).fetchone()
            is not None
        )
        row = (
            connection.execute(
                "SELECT g.principal_id FROM instance_account_guard g "
                "JOIN principals p ON p.principal_id = g.principal_id "
                "WHERE g.singleton = 1 AND p.is_active = 1"
            ).fetchone()
            if guard_exists
            else None
        )
        if row is None:
            row = connection.execute(
                "SELECT principal_id FROM principals WHERE role_ids LIKE '%rl_owner%' "
                "AND is_active = 1 ORDER BY created_at, principal_id LIMIT 1"
            ).fetchone()
        if row is None:
            row = connection.execute(
                "SELECT c.principal_id FROM account_credentials c "
                "JOIN principals p ON p.principal_id = c.principal_id "
                "WHERE p.is_active = 1 ORDER BY c.created_at, c.principal_id LIMIT 1"
            ).fetchone()
        return str(row["principal_id"]) if row is not None else None

    def assign_legacy_data_to_original_owner(self) -> None:
        with self.connect() as connection:
            self._backfill_legacy_account_data_owner(connection)
            self._backfill_owned_context_data(connection)
            self._backfill_owned_memory_metadata(connection)

    def table_names(self) -> set[str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        return {str(row["name"]) for row in rows}

    # ── Conversation recall (RAIKER-2020) ────────────────────────────────────
    #
    # `conversation_fts` is a projection of `turns`, rebuilt from it and never
    # read as an authority. Every search below carries its hits back to the
    # `turns`/`sessions` rows so ownership is still decided by `sessions.user_id`
    # — the index narrows the candidate set, it does not widen who may see one.

    @staticmethod
    def _sync_conversation_fts(connection: sqlite3.Connection, turn_id: str) -> None:
        with contextlib.suppress(sqlite3.OperationalError):
            connection.execute("DELETE FROM conversation_fts WHERE turn_id = ?", (turn_id,))
            connection.execute(
                """INSERT INTO conversation_fts(turn_id, session_id, role, text)
                   SELECT turn_id, session_id, 'prompt', prompt_text FROM turns
                   WHERE turn_id = ? AND prompt_text IS NOT NULL AND TRIM(prompt_text) != ''""",
                (turn_id,),
            )
            connection.execute(
                """INSERT INTO conversation_fts(turn_id, session_id, role, text)
                   SELECT turn_id, session_id, 'answer', summary FROM turns
                   WHERE turn_id = ? AND summary IS NOT NULL AND TRIM(summary) != ''""",
                (turn_id,),
            )

    @staticmethod
    def _backfill_conversation_fts(connection: sqlite3.Connection) -> None:
        """Populate the index once, for the turns that predate it.

        Deliberately *not* a rebuild on every open: a workspace carrying years of
        conversation would pay a full re-index to start the app. New turns keep
        themselves in sync through ``_sync_conversation_fts``; a workspace that
        needs a repair gets one from ``rebuild_conversation_fts`` on request.
        """
        with contextlib.suppress(sqlite3.OperationalError):
            # `LIMIT 1`, not `COUNT(*)`: counting an FTS4 table scans its whole
            # content table, and a workspace carrying years of conversation would
            # pay that on every start — the exact case this index exists for.
            if connection.execute("SELECT 1 FROM conversation_fts LIMIT 1").fetchone():
                return
            SQLiteStore._rebuild_conversation_fts(connection)

    @staticmethod
    def _rebuild_conversation_fts(connection: sqlite3.Connection) -> None:
        connection.execute("DELETE FROM conversation_fts")
        connection.execute(
            """INSERT INTO conversation_fts(turn_id, session_id, role, text)
               SELECT turn_id, session_id, 'prompt', prompt_text FROM turns
               WHERE prompt_text IS NOT NULL AND TRIM(prompt_text) != ''"""
        )
        connection.execute(
            """INSERT INTO conversation_fts(turn_id, session_id, role, text)
               SELECT turn_id, session_id, 'answer', summary FROM turns
               WHERE summary IS NOT NULL AND TRIM(summary) != ''"""
        )

    def rebuild_conversation_fts(self) -> int:
        """Owner-started repair. Returns the number of indexed rows."""
        with self.connect() as connection:
            self._rebuild_conversation_fts(connection)
            return int(
                connection.execute("SELECT COUNT(*) FROM conversation_fts").fetchone()[0] or 0
            )
