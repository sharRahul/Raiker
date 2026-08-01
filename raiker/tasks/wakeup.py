"""The nudge that turns an approved scheduled run from *waiting* into *running*.

BUG-39. A scheduled run that parks on an approval is continued by the host's own
scheduler pass, and that pass used to happen only on the 15-second tick. A
decision granted one moment after a tick therefore sat for the rest of the
interval showing *waiting for approval*, while the identical decision made in
Chat continued within a second — because a Chat tab is watching and resolving an
approval there nudges that watcher directly.

This is the scheduler's equivalent of that watcher. Resolving an approval sets
the event; the host's continuation worker is waiting on it and starts the
continuation immediately. The periodic tick still runs, unchanged, which is
exactly the arrangement the fix asks for: the signal is the fast path and the
tick is the recovery path, so a decision that arrives while the worker is busy —
or through a route that never reaches this process at all — is still picked up.

Two things this deliberately is *not*:

* **It is not the exactly-once mechanism.** That remains
  ``claim_suspended_turn``: a nudge and a tick racing on the same parked turn
  cannot both replay it, and neither can a browser tab racing with both.
* **It is not a queue.** The event says only "some approval was decided, look
  now". Coalescing several decisions into one pass is correct — the pass scans
  every parked task anyway — and it means a burst of approvals costs one sweep
  rather than one sweep each.

The event is bound to the loop that waits on it, which is the API host's own
loop. ``request`` is therefore safe to call from a request handler on that loop
and from a worker thread alike: the thread-safe path is used whenever the
calling thread is not the loop's.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress


class SchedulerWakeup:
    """An awaitable "an approval was decided" signal for the scheduler worker.

    Created before the event loop exists (``create_app`` builds one per app), so
    the loop is bound on the first ``wait`` rather than in ``__init__``.
    """

    def __init__(self) -> None:
        self._event = asyncio.Event()
        self._loop: asyncio.AbstractEventLoop | None = None

    def request(self) -> None:
        """Ask the continuation worker to look now. Never raises.

        A nudge is best-effort by construction: if nothing is waiting yet, or the
        host is shutting down, the tick still finds the work. Failing a user's
        approval because the optimisation could not be signalled would be a
        strictly worse outcome than being 15 seconds late.
        """
        loop = self._loop
        if loop is None or loop.is_closed():
            # Nothing has waited yet: set it directly so the first wait returns
            # immediately rather than losing a decision made during startup.
            self._event.set()
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            self._event.set()
            return
        with suppress(RuntimeError):
            loop.call_soon_threadsafe(self._event.set)

    async def wait(self, timeout: float) -> bool:
        """Block until nudged or *timeout* elapses. True when it was a nudge.

        The flag is cleared before returning, so a nudge that lands while the
        continuation pass is running is not lost — it simply causes the next
        wait to return immediately, and the pass that follows sees it.
        """
        self._loop = asyncio.get_running_loop()
        try:
            await asyncio.wait_for(self._event.wait(), timeout=timeout)
        except TimeoutError:
            return False
        self._event.clear()
        return True
