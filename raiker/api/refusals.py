"""The API's refusal envelope, in a module that imports nothing of Raiker's (OPT-04).

Its own module so that :mod:`raiker.api.auth` — which every other dependency
builds on — can use it without an import cycle.
"""

from __future__ import annotations

from fastapi import HTTPException


def refusal(status_code: int, reason_code: str | None) -> HTTPException:
    """The API's one refusal envelope: ``{"ok": False, "reason_code": ...}``.

    A hundred and seventy-four route sites built this dictionary by hand. The status
    stays the route's decision — a missing record and a conflict are different
    answers — and the body is always the same shape the web client reads.
    """
    return HTTPException(status_code=status_code, detail={"ok": False, "reason_code": reason_code})
