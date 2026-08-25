"""One coroutine, run from synchronous code, wherever that code is called from.

Raiker's executors are synchronous and every provider call underneath them is
`async`. `asyncio.run` bridges the two from the CLI and *raises* from the web
API, because the request is already on a loop — and the difference is invisible
at the call site.

That is not a hypothetical: it is how the only unmocked path into
``model_provider_runtime`` failed. `asyncio.run` raised before a provider was
ever contacted, the executor mapped the exception to
``model_provider_error:RuntimeError``, and the owner was shown what reads as a
provider fault for a bug that never left the process.
"""

from __future__ import annotations

import asyncio

import pytest

from raiker.runtime.async_bridge import run_coro


async def _answer() -> str:
    await asyncio.sleep(0)
    return "answered"


def test_runs_a_coroutine_with_no_loop_on_this_thread() -> None:
    assert run_coro(_answer()) == "answered"


def test_runs_a_coroutine_from_inside_a_running_loop() -> None:
    """The case `asyncio.run` cannot serve, and the one the web API is always in."""

    async def caller() -> str:
        result: str = run_coro(_answer())
        return result

    assert asyncio.run(caller()) == "answered"


def test_an_exception_reaches_the_caller_rather_than_the_worker_thread() -> None:
    """A failure that vanished into the worker would be worse than no bridge.

    The executor above maps whatever this raises to a reason code the owner
    sees, so the exception has to arrive with its own type intact.
    """

    async def boom() -> str:
        raise ValueError("provider said no")

    async def caller() -> None:
        run_coro(boom())

    with pytest.raises(ValueError, match="provider said no"):
        asyncio.run(caller())
    with pytest.raises(ValueError, match="provider said no"):
        run_coro(boom())


def test_the_advisor_still_reaches_the_same_bridge() -> None:
    """The advisor's private name is kept; only the implementation moved."""
    from raiker.runtime.advisor import _run_coro

    async def caller() -> str:
        result: str = _run_coro(_answer())
        return result

    assert asyncio.run(caller()) == "answered"
