"""Shared retry classification and ordered candidate planning."""
from __future__ import annotations

from collections.abc import Iterator

# Reason codes that mean "the request never reached a decision" — a closed or
# refused connection, a timeout, a provider 5xx, or a stream that ended in an
# exception nobody classified. One immediate re-attempt on the *same* model is
# the right answer to all of them and to none of the others: an expired key, an
# empty balance, a missing model and a rejected request are all decisions, and
# asking again just spends the owner's quota to be told the same thing (BUG-72).
TRANSPORT_FAILURE_CODES = (
    "provider_connection_failed",
    "provider_timeout",
    "provider_unavailable",
)


def is_transport_failure(code: str) -> bool:
    base = code.split(":", 1)[0]
    if base in TRANSPORT_FAILURE_CODES:
        return True
    # `provider_stream_failed` bare is a provider-declared stream error, which is
    # a decision. `provider_stream_failed:<Type>` is an unclassified exception
    # mid-stream — the shape a dropped connection takes.
    return base == "provider_stream_failed" and ":" in code


class ModelAttempts:
    """One transient retry per configured candidate, shared by both call modes.

    Callers report failure before advancing. Once any visible output is
    committed the sequence stops, so neither retry nor fallback can replay it.
    """

    def __init__(self, chain: list[tuple[str, str]]) -> None:
        self.chain = chain
        self._retry = False
        self._is_retry = False
        self._stopped = False

    def failed(self, code: str, *, output_committed: bool = False) -> None:
        self._stopped = output_committed
        self._retry = not self._is_retry and not output_committed and is_transport_failure(code)

    def __iter__(self) -> Iterator[tuple[int, str, str, bool]]:
        for rank, (provider, model) in enumerate(self.chain):
            self._retry = False
            self._is_retry = False
            yield rank, provider, model, False
            if self._stopped:
                return
            if self._retry:
                self._retry = False
                self._is_retry = True
                yield rank, provider, model, True
                if self._stopped:
                    return
