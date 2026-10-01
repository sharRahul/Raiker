"""Proof that the runtime authority is dispatching *this* action right now (CR-03).

**Why this exists.** The governed services — the four connectors, web access
and the advisor — enforce their own gate and decision mode, because a chat tool
reaches them directly. The executor that runs *after* ``route_action`` must not
enforce them a second time: the router already applied the gate, the mode and
the approval, and a second ``ask`` would withhold an action the owner just
approved. The skip is never a boolean, which any caller can pass: one ``False``
in a future scheduler, plugin bridge or route handler would skip the owner's
switch without anything noticing.

The skip needs a :class:`RoutedAuthority`, and only
:func:`routed_dispatch` — entered by ``RuntimeAuthority.route_action``
immediately around ``executor.execute`` — issues one. A token is honoured only
while that dispatch is still running, only in the context it was issued in,
and only for the capability it was issued for. A service asked to skip its
gate with anything else — ``False``, ``True``, a stale token kept from an
earlier dispatch, a token for a different capability — enforces its gate as
though nothing had been passed.

**What this is not.** A runtime-issued handle stops the *accidental* bypass
this finding is about. It is not a boundary against hostile code running in
the same process, which could call :func:`routed_dispatch` itself; the release
review says as much about handles in general. The type boundary that would
make construction impossible from outside the authority is RR-AUTHORITY-01.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

__all__ = [
    "RoutedAuthority",
    "current_routed_authority",
    "is_routed",
    "routed_dispatch",
]

#: Held only by this module; the constructor refuses anything else, so a token
#: cannot be built by naming the class.
_ISSUER = object()


class RoutedAuthority:
    """An opaque token for one governed dispatch. Compared by identity."""

    __slots__ = ("action_id", "capability")

    def __init__(self, capability: str, action_id: str, *, _issuer: object) -> None:
        if _issuer is not _ISSUER:
            raise TypeError("RoutedAuthority is issued by the runtime authority only")
        self.capability = capability
        self.action_id = action_id

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return f"RoutedAuthority(capability={self.capability!r}, action_id={self.action_id!r})"


_CURRENT: ContextVar[RoutedAuthority | None] = ContextVar("raiker_routed_authority", default=None)


@contextmanager
def routed_dispatch(capability: str, action_id: str) -> Iterator[RoutedAuthority]:
    """Issue the token for one executor call and withdraw it when the call ends."""
    token = RoutedAuthority(capability, action_id, _issuer=_ISSUER)
    reset = _CURRENT.set(token)
    try:
        yield token
    finally:
        _CURRENT.reset(reset)


def current_routed_authority(action_id: str) -> RoutedAuthority | None:
    """The token for *action_id* if the authority is dispatching it now, else ``None``.

    An executor calls this with its own action's id and hands the result to the
    service. Called from anywhere the router is not dispatching that action —
    a direct ``executor.execute``, a test, a later thread — it answers ``None``,
    and the service governs as it would for a chat tool.
    """
    token = _CURRENT.get()
    if token is None or token.action_id != action_id:
        return None
    return token


def is_routed(authority: object, capability: str) -> bool:
    """True only for the live token of the current dispatch of *capability*."""
    return (
        isinstance(authority, RoutedAuthority)
        and authority is _CURRENT.get()
        and authority.capability == capability
    )
