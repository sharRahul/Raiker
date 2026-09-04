"""Whether a local model runtime actually exists on this machine (BUG-270).

A brand-new workspace reported ``gemma4:31b-cloud`` as its selected model on a
host with no ``ollama`` binary and nothing listening on 11434.  The profile that
names it already declares ``default_state: disabled_until_provider_detected``;
nothing detected the provider, so the declaration had no effect and every
surface — the setup meter, the Global model control, both composer chips —
printed a model string for a runtime nobody had.

This module is the missing detector, and it is deliberately narrow:

* **Detection is a PATH lookup, never a connection.** ``shutil.which`` answers
  "is this runtime installed on this host". It does not start a process, open a
  socket, or read a credential. That matters because
  :doc:`FIXED-357 </plans/FIXED_ITEMS>` established that a *status read must not
  perform a connection*, and the cheapest way to honour that rule is for the
  detector to have no way of breaking it.
* **The result is cached durably.** A status read never runs the detector: it
  reads the row the detector wrote. :func:`detect` refreshes rows that are
  missing or older than :data:`DETECTION_TTL_SECONDS`, and is called from the
  places where the answer can genuinely have changed — a readiness check, a
  local deployment, a first-run setup read, or the owner pressing re-detect.
* **"Unknown" is a real answer.** A runtime nothing has looked for yet is not
  reported as absent. :func:`presence` returns ``None`` for it, and the callers
  that decide what a surface may claim treat unknown as *do not claim*, which is
  the fail-closed direction for a promise about someone else's machine.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from raiker.contracts.ids import utc_now

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

#: The executables that prove a runtime is installed, in the order they are
#: tried. The key is the ``provider`` field a model profile carries, so a
#: profile maps to a detector without a second table to keep in step.
RUNTIME_EXECUTABLES: dict[str, tuple[str, ...]] = {
    "ollama": ("ollama",),
    "llama.cpp": ("llama-server",),
    "mlx": ("mlx_lm.server", "mlx_lm"),
    "vllm": ("vllm",),
}

#: How long a detection result stands before :func:`detect` looks again. An
#: install or an uninstall is a rare event and a stale answer for an hour is
#: cheaper than a PATH scan on every read; nothing here expires into *absent*,
#: only into *look again*.
DETECTION_TTL_SECONDS = 3600


@dataclass(frozen=True)
class RuntimePresence:
    """One detection result, and when it was taken."""

    runtime: str
    present: bool
    executable: str | None
    detected_at: str


def _stale(detected_at: str, *, now: datetime) -> bool:
    try:
        taken = datetime.fromisoformat(detected_at)
    except ValueError:
        return True
    if taken.tzinfo is None:
        return True
    return now - taken > timedelta(seconds=DETECTION_TTL_SECONDS)


def probe(runtime: str) -> tuple[bool, str | None]:
    """Look for ``runtime``'s executable on this host. No connection is made."""
    for name in RUNTIME_EXECUTABLES.get(runtime, ()):
        found = shutil.which(name)
        if found:
            return True, found
    return False, None


def detect(
    store: SQLiteStore, *, runtimes: tuple[str, ...] | None = None, force: bool = False
) -> dict[str, RuntimePresence]:
    """Refresh and return detection results for the named runtimes.

    Only rows that are missing or stale are re-probed unless ``force`` is set, so
    calling this on a route that runs often costs one row read per runtime.
    """
    wanted = runtimes if runtimes is not None else tuple(RUNTIME_EXECUTABLES)
    stored = store.load_local_runtime_presence()
    now = datetime.fromisoformat(utc_now())
    results: dict[str, RuntimePresence] = {}
    for runtime in wanted:
        row = stored.get(runtime)
        if not force and row is not None and not _stale(str(row["detected_at"]), now=now):
            results[runtime] = RuntimePresence(
                runtime=runtime,
                present=bool(row["present"]),
                executable=row["executable"],
                detected_at=str(row["detected_at"]),
            )
            continue
        present, executable = probe(runtime)
        store.save_local_runtime_presence(runtime, present=present, executable=executable)
        results[runtime] = RuntimePresence(
            runtime=runtime, present=present, executable=executable, detected_at=utc_now()
        )
    return results


def cached(store: SQLiteStore) -> dict[str, RuntimePresence]:
    """Every detection result on record. Reads rows; probes nothing."""
    return {
        runtime: RuntimePresence(
            runtime=runtime,
            present=bool(row["present"]),
            executable=row["executable"],
            detected_at=str(row["detected_at"]),
        )
        for runtime, row in store.load_local_runtime_presence().items()
    }


def presence(store: SQLiteStore, provider: str) -> bool | None:
    """Whether ``provider``'s runtime is installed here, or ``None`` if unknown.

    ``None`` is returned both for a provider nothing has detected yet and for one
    this module has no detector for — in either case the honest answer is that
    Raiker does not know, and a surface must not claim on its behalf.
    """
    if provider not in RUNTIME_EXECUTABLES:
        return None
    row = store.load_local_runtime_presence().get(provider)
    return None if row is None else bool(row["present"])
