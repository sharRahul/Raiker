"""Differential test harness: compare a fast implementation against a slow one.

Hand-picked tests check the cases you already thought of, which is exactly the
set that is already correct. Randomised inputs compared against an obviously
correct brute force find the case you did not think of — and they hand you the
*smallest* failing input, which is usually the whole diagnosis.

Copy this into the project (or import it) and call ``check`` with your two
implementations and a generator for the input.

    from oracle_check import check, ints

    check(fast=my_fast_median, oracle=lambda xs: sorted(xs)[len(xs) // 2],
          generate=ints(max_len=12, low=-20, high=20))

Run it directly to see the harness verify itself:

    python oracle_check.py
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from typing import Any


class OracleMismatch(AssertionError):
    """The two implementations disagreed. ``case`` is the shrunken input."""

    def __init__(self, case: Any, fast_result: Any, oracle_result: Any) -> None:
        super().__init__(
            f"disagreement on {case!r}: fast={fast_result!r} oracle={oracle_result!r}"
        )
        self.case = case
        self.fast_result = fast_result
        self.oracle_result = oracle_result


def ints(
    *, max_len: int = 12, low: int = -20, high: int = 20
) -> Callable[[random.Random], list[int]]:
    """Generate small integer lists.

    Small on purpose: a failure on a 6-element list is readable, a failure on a
    600-element one is a second debugging problem. Duplicates and negatives are
    in range because that is where most off-by-one and sign bugs live.
    """

    def generate(rng: random.Random) -> list[int]:
        return [rng.randint(low, high) for _ in range(rng.randint(0, max_len))]

    return generate


def _shrink(case: Any, disagrees: Callable[[Any], bool]) -> Any:
    """Reduce a failing case while it keeps failing.

    Only handles sequences, which covers the common shape. Anything else is
    returned untouched rather than mangled by a guess at its structure.
    """
    if not isinstance(case, Sequence) or isinstance(case, (str, bytes)):
        return case
    current = list(case)
    changed = True
    while changed and len(current) > 0:
        changed = False
        for index in range(len(current)):
            candidate = current[:index] + current[index + 1 :]
            if disagrees(candidate):
                current = candidate
                changed = True
                break
    return current


def check(
    *,
    fast: Callable[[Any], Any],
    oracle: Callable[[Any], Any],
    generate: Callable[[random.Random], Any],
    trials: int = 500,
    seed: int = 0,
) -> None:
    """Run both implementations over generated inputs and assert they agree.

    The seed is fixed so a failure is reproducible — a differential test that
    fails once and never again is worse than no test, because it trains you to
    ignore it. Raises :class:`OracleMismatch` with the shrunken input.
    """
    rng = random.Random(seed)

    def disagrees(case: Any) -> bool:
        try:
            return fast(case) != oracle(case)
        except Exception:
            # An exception on one side is a disagreement too — often the most
            # interesting one, since it is usually the empty or single-element
            # case the fast path forgot.
            return True

    for _ in range(trials):
        case = generate(rng)
        if disagrees(case):
            minimal = _shrink(case, disagrees)
            raise OracleMismatch(minimal, _safe(fast, minimal), _safe(oracle, minimal))


def _safe(function: Callable[[Any], Any], case: Any) -> Any:
    try:
        return function(case)
    except Exception as exc:  # noqa: BLE001 - reporting, not control flow
        return f"<raised {type(exc).__name__}>"


if __name__ == "__main__":
    # A correct pair agrees.
    check(fast=lambda xs: sum(xs), oracle=lambda xs: sum(reversed(xs)), generate=ints())

    # A pair with the classic empty-input bug disagrees, and shrinks to [].
    def buggy_max(xs: list[int]) -> int | None:
        return max(xs)  # raises on []

    try:
        check(fast=buggy_max, oracle=lambda xs: max(xs) if xs else None, generate=ints())
    except OracleMismatch as mismatch:
        assert mismatch.case == [], mismatch.case
        print(f"caught as expected: {mismatch}")
    else:
        raise AssertionError("the harness failed to catch a known bug")

    print("oracle_check self-test passed")
