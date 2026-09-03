"""The session that survives a reload, and the CSRF surface that comes with it.

BUG-253. The bearer token lived in a module variable in the browser and was
deliberately never written to ``localStorage`` or ``sessionStorage``. That is a
real posture — nothing on disk in the browser can be read back later — but it
also meant refreshing the tab, which is exactly what applying a UI change asks
an owner to do, returned them to the unlock screen.

**An ``HttpOnly`` cookie is not weaker than a memory token.** Script cannot read
either one, and script running on the page can *use* either one. The difference
is the one that matters here: the cookie survives a reload, and it is sent
automatically — which is precisely what creates a CSRF surface that an
``Authorization`` header does not have. So the cookie never ships alone:

* The session cookie is ``HttpOnly``, ``SameSite=Strict``, and ``Path``-scoped.
  ``Strict`` alone already refuses a cross-site form post, and it is the primary
  defence; everything below is what holds when a browser does not honour it.
* A second, deliberately **readable** cookie carries a CSRF token. Any
  state-changing request authenticated *by cookie* must echo it in a header.
  Script on another origin can neither read Raiker's cookie nor set that header,
  so the double submit only succeeds from Raiker's own page.
* An ``Origin``/``Referer`` that is present and is not this host is refused
  outright, before the token comparison.

A request that authenticates with an ``Authorization`` header is unchanged and
is *not* subject to any of this: a header the browser never attaches on its own
cannot be forged by a cross-site page, which is the whole reason bearer tokens
have no CSRF problem. Both paths therefore coexist without either weakening the
other — the CLI, the tray and the tests keep using the header.
"""

from __future__ import annotations

import hmac
import secrets
from typing import Final
from urllib.parse import urlsplit

from fastapi import Request, Response

#: The session token. HttpOnly: nothing on the page can read it back.
SESSION_COOKIE: Final = "raiker_session"
#: The CSRF token. Deliberately readable, because the page has to echo it.
CSRF_COOKIE: Final = "raiker_csrf"
#: Where the page echoes it.
CSRF_HEADER: Final = "X-Raiker-CSRF"

#: Methods that cannot change anything, and so need no CSRF proof.
SAFE_METHODS: Final = frozenset({"GET", "HEAD", "OPTIONS"})

# Matches the API session's own default lifetime; the cookie must not outlive
# the session it names, and a cookie that dies first would sign the owner out
# while the session is still perfectly good.
_MAX_AGE_SECONDS: Final = 86400 * 30


def _secure(request: Request) -> bool:
    """``Secure`` only over TLS.

    Raiker binds loopback over plain HTTP by default, and a ``Secure`` cookie is
    simply never sent there — the flag would not harden anything, it would stop
    the feature working. Over a real HTTPS deployment it is set.
    """
    return request.url.scheme == "https"


def issue(request: Request, response: Response, token: str) -> str:
    """Put the session on the response and return the CSRF token that guards it."""
    csrf = secrets.token_urlsafe(32)
    secure = _secure(request)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=_MAX_AGE_SECONDS,
        httponly=True,
        samesite="strict",
        secure=secure,
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        max_age=_MAX_AGE_SECONDS,
        # Readable on purpose: the page's job is to copy this into a header, and
        # it holds no authority on its own — presenting it without the session
        # cookie authenticates nothing.
        httponly=False,
        samesite="strict",
        secure=secure,
        path="/",
    )
    return csrf


def clear(response: Response) -> None:
    """Sign out here as well as server-side, so a reload does not restore it."""
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


def cookie_token(request: Request) -> str | None:
    value = request.cookies.get(SESSION_COOKIE)
    return value if value else None


def origin_is_foreign(request: Request) -> bool:
    """True when a stated origin is present and is not this host.

    Absent is not foreign: plenty of legitimate requests state no origin, and
    treating silence as an attack would break them while stopping nothing — a
    cross-site page cannot suppress the header its browser attaches.
    """
    stated = request.headers.get("origin") or request.headers.get("referer")
    if not stated:
        return False
    host = request.headers.get("host")
    if not host:
        return False
    return urlsplit(stated).netloc.lower() != host.lower()


def csrf_failure(request: Request) -> str | None:
    """Why this cookie-authenticated write is refused, or ``None`` if it is not.

    Only ever consulted for a request that authenticated by *cookie*: a bearer
    header is not attached by the browser and so cannot be forged cross-site.
    """
    if request.method.upper() in SAFE_METHODS:
        return None
    if origin_is_foreign(request):
        return "csrf_origin_mismatch"
    presented = request.headers.get(CSRF_HEADER, "")
    expected = request.cookies.get(CSRF_COOKIE, "")
    if not presented or not expected:
        return "csrf_token_missing"
    # Constant-time: the token is a secret being compared against a value the
    # caller supplies, which is the exact shape a timing oracle needs.
    if not hmac.compare_digest(presented, expected):
        return "csrf_token_mismatch"
    return None
