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
"""
from __future__ import annotations

import asyncio
from typing import Any


def run_coro(coro: Any) -> Any:
    """Run *coro* to completion from synchronous code.

    Uses :func:`asyncio.run` when this thread has no running loop, and a worker
    thread with its own loop when it does. The coroutine is awaited exactly once
    either way: a coroutine that is created and never awaited is a silent
    no-result, which is the failure mode this replaces.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()
