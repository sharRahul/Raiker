"""Running one coroutine from synchronous code, wherever that code is called.

Raiker's tool execution is synchronous by design — the broker walks a batch of
governed actions one at a time and each executor returns a result — while every
provider call underneath it is `async`. Bridging the two with `asyncio.run` works
from the CLI and raises from the web API, because the API request is *already*
running on a loop.

That difference is invisible at the call site and expensive when it is wrong: a
`RuntimeError` raised before the provider was ever contacted reads, in an
executor that maps every exception to a reason code, as a provider fault. This
module exists so the answer is written once and every caller gets the same one.

**GCR-05 — the fallback is correct and is not where this should happen.** When a
caller reaches here with a loop already running, the coroutine is moved to a
worker thread so it cannot conflict with that loop — but the calling thread then
blocks until it finishes, and the thread it blocks is the ASGI event loop. A
provider call is not a fast operation; for the length of one, every other request
on the server waits. The recommendation GCR-05 makes is the one this module now
holds a counter for: keep the sync bridge at a genuinely synchronous process
boundary, and get off the loop *before* the synchronous work starts, rather than
inside it.
"""
from __future__ import annotations

import asyncio
import threading
from typing import Any

#: How many times a caller reached :func:`run_coro` with a loop already running.
#:
#: Every one of those is a blocked event loop. It is a counter rather than a
#: refusal because refusing would turn a slow path into a broken one, and
#: because the CLI and the turn path reach here correctly — with no loop — and
#: must keep working. A test asserts it stays at zero across the request paths
#: that execute a governed action, so the hop off the loop cannot be removed
#: again without something saying so.
_blocked_loop_calls = 0
_counter_lock = threading.Lock()


def blocked_loop_calls() -> int:
    """How many calls have blocked a running event loop since the last reset."""
    return _blocked_loop_calls


def reset_blocked_loop_calls() -> None:
    """Zero the counter. For tests, which assert against a known starting point."""
    global _blocked_loop_calls
    with _counter_lock:
        _blocked_loop_calls = 0


def run_coro(coro: Any) -> Any:
    """Run *coro* to completion from synchronous code.

    Uses :func:`asyncio.run` when this thread has no running loop, and a worker
    thread with its own loop when it does. The coroutine is awaited exactly once
    either way: a coroutine that is created and never awaited is a silent
    no-result, which is the failure mode this replaces.
    """
    global _blocked_loop_calls
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures

    with _counter_lock:
        _blocked_loop_calls += 1
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()
