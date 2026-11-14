# SPDX-License-Identifier: Apache-2.0
"""Keep the semantic recall space current in the background, on this computer.

The governed ``index_memories`` action (MEM-10) embeds every approved memory
and managed-file chunk that has no vector in the chosen space. It ran only when
the owner pressed **Index** in Memory, so a new memory or a newly added file
was invisible to semantic recall until someone remembered to press it.

This worker runs that same action on a quiet cadence with Raiker's built-in
embedding model (:mod:`raiker.models.builtin_embedding`, ``nomic-embed-text``
on the owner's local Ollama). It changes nothing about what is allowed:

* it runs only when ``model_provider_runtime`` is on and set to **Always
  allow** or **Auto**, the same rule semantic search reads by — it never parks
  an approval nobody asked for;
* the action goes through :class:`RuntimeAuthority` with the same principal,
  gate read, policy review and audit record a button press makes;
* the model is local and its profile is ``local_only``, so nothing leaves the
  computer; Ollama verifies the model's digest when it fetches it.

``RAIKER_BACKGROUND_INDEX=off`` turns the worker off. The last outcome is kept
at ``<workspace>/logs/background-index.json`` for Diagnostics.
"""

from __future__ import annotations

import contextlib
import json
import os
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from raiker.contracts.ids import utc_now
from raiker.models import builtin_embedding

DISABLE_ENV = "RAIKER_BACKGROUND_INDEX"
#: Between runs. Indexing is incremental, so a quiet cadence costs little.
INTERVAL_SECONDS = 600.0
_EXECUTING_MODES = frozenset({"allow", "auto"})


@dataclass(frozen=True)
class IndexOutcome:
    """One run, in a shape Diagnostics can show as it is."""

    #: ``indexed`` · ``up_to_date`` · ``waiting_for_permission`` ·
    #: ``model_missing`` · ``ollama_unreachable`` · ``no_owner`` · ``failed``
    state: str
    at: str
    model: str = builtin_embedding.MODEL
    indexed: int = 0
    reason_code: str | None = None


def disabled() -> bool:
    return os.environ.get(DISABLE_ENV, "").strip().lower() in {"off", "0", "false"}


def status_path(workspace_root: str | Path) -> Path:
    return Path(workspace_root) / "logs" / "background-index.json"


def read_status(workspace_root: str | Path) -> dict[str, Any] | None:
    try:
        loaded = json.loads(status_path(workspace_root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _write_status(workspace_root: str | Path, outcome: IndexOutcome) -> None:
    path = status_path(workspace_root)
    with contextlib.suppress(OSError):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(outcome)), encoding="utf-8")


def _owner(store: Any) -> str | None:
    try:
        accounts = store.list_accounts()
    except Exception:  # noqa: BLE001 - an unreadable store has no owner to act for
        return None
    return str(accounts[0]["principal_id"]) if accounts else None


def _may_run(store: Any, owner: str) -> bool:
    from raiker.runtime.authority.admission import capability_admission

    admission = capability_admission(store, owner, "model_provider_runtime")
    mode = getattr(admission.decision_mode, "value", admission.decision_mode)
    return bool(admission.gate_enabled) and str(mode) in _EXECUTING_MODES


def _route_index(store: Any, owner: str) -> tuple[bool, int, str | None]:
    """Run one governed ``index_memories`` batch. (ok, indexed, reason)."""
    from raiker.contracts.ids import new_id
    from raiker.events.writer import EventLogWriter
    from raiker.memory.query_embedding import _principal
    from raiker.runtime.authority.models import RiskLevelValue
    from raiker.runtime.authority.router import GovernedAction, RuntimeAuthority
    from raiker.runtime.executors import build_default_executor_registry

    principal = _principal(store, owner)
    if principal is None:
        return False, 0, "principal_not_resolved"
    workspace_root = Path(store.paths.workspace_root)
    authority = RuntimeAuthority(
        store,
        EventLogWriter(store),
        executor_registry=build_default_executor_registry(workspace_root, store),
    )
    result = authority.route_action(
        GovernedAction(
            action_id=new_id("act_"),
            principal_id=principal.principal_id,
            action_type="model_provider",
            tool_or_service_name="model_provider",
            arguments={
                "operation": "index_memories",
                "provider": builtin_embedding.PROVIDER,
                "model": builtin_embedding.MODEL,
            },
            risk_level=RiskLevelValue.LOW,
            session_id="background-index",
        ),
        principal,
    )
    artifacts = dict(result.artifacts or {})
    indexed = int(artifacts.get("indexed_count") or 0) + int(artifacts.get("indexed_file_chunk_count") or 0)
    ok = result.decision == "allow" and not result.error
    reason = result.error or artifacts.get("reason_code") or (None if ok else result.decision)
    return ok, indexed, None if ok else str(reason)


def run_once(
    workspace_root: str | Path,
    *,
    status: Callable[[], builtin_embedding.LocalEmbeddingStatus] = builtin_embedding.local_status,
    pull: Callable[[], bool] = builtin_embedding.pull,
    route: Callable[[Any, str], tuple[bool, int, str | None]] = _route_index,
) -> IndexOutcome:
    """One pass: make sure the model is there, then index what is new."""
    from raiker.storage.sqlite import SQLiteStore

    store = SQLiteStore(workspace_root)
    owner = _owner(store)
    if owner is None:
        outcome = IndexOutcome("no_owner", utc_now())
    elif not _may_run(store, owner):
        outcome = IndexOutcome("waiting_for_permission", utc_now(), reason_code="model_provider_runtime_not_auto")
    else:
        local = status()
        if local.state == "model_missing" and pull():
            local = status()
        if not local.ready:
            outcome = IndexOutcome(local.state, utc_now())
        else:
            ok, indexed, reason = route(store, owner)
            if ok:
                outcome = IndexOutcome("indexed", utc_now(), indexed=indexed)
            elif reason == "no_memories_to_index":
                outcome = IndexOutcome("up_to_date", utc_now())
            else:
                outcome = IndexOutcome("failed", utc_now(), reason_code=reason)
    _write_status(workspace_root, outcome)
    return outcome


#: The first run waits for startup to settle (migrations, the first page load).
FIRST_RUN_DELAY_SECONDS = 60.0


def start(
    workspace_root: str | Path,
    *,
    interval: float = INTERVAL_SECONDS,
    first_delay: float = FIRST_RUN_DELAY_SECONDS,
) -> threading.Event | None:
    """Run :func:`run_once` after ``first_delay``, then every ``interval``; returns its stop event."""
    if disabled():
        return None
    stop = threading.Event()

    def loop() -> None:
        stop.wait(first_delay)
        while not stop.is_set():
            with contextlib.suppress(Exception):
                run_once(workspace_root)
            stop.wait(interval)

    threading.Thread(target=loop, name="raiker-background-index", daemon=True).start()
    return stop
