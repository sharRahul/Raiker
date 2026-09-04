"""BUG-226 — the `http` hook handler, behind a named, revocable egress grant.

[The Claude Code hooks reference](https://code.claude.com/docs/en/hooks)
documents five handler types. Raiker refused three of them at parse time, and
`http` was refused for a reason rather than an omission: **a hook has no
implicit network access.** Giving one an outbound request is a capability
decision, not a handler type, and the entry that raised this said `http` would
follow "only once a hook can be given a named, revocable egress grant". This is
that grant, and it is the same shape the channel and connector paths already use:

* **Named.** `RAIKER_HOOK_EGRESS_ALLOWLIST` holds the host globs a hook may
  reach — `hooks.internal.example.com`, `127.0.0.1:*`. A destination outside it
  is refused with a reason that says so, not silently skipped.
* **Empty by default.** A workspace that has never set the variable grants
  nothing, so adding an `http` rule to a hooks file cannot by itself make a
  request leave the machine. Fail-closed independently of the hook config, which
  is the point: a rule can be contributed by a plugin, and a plugin must not be
  able to widen egress by writing a file.
* **Revocable in one place.** Clearing the variable revokes every `http` hook at
  once, without editing any hooks file — which is what "revocable" has to mean
  when the rules live in five files across four scopes.

What the request carries is exactly what a `prompt` handler already sends to a
model provider: the bounded, redacted event JSON. Nothing here reads a file, a
credential, or a turn's standing context.

What comes back is read on the same terms a `command` handler's stdout is: a
JSON decision object, or nothing. And it is bounded the same way the aggregate
already bounds every handler — :func:`raiker.hooks.decision.combine` honours only
`deny` and `ask`, and only from a handler the owner gave authority, so a remote
responder can make an action stricter and can never make one permitted.
"""

from __future__ import annotations

import json
import os
from fnmatch import fnmatch
from urllib.parse import urlparse

from raiker.hooks.contracts import HookHandler, HookInput, HookOutput
from raiker.hooks.handlers.command import CommandHookTimeout, _parse_output

#: The most of a responder's answer that is read. Same bound the command
#: handler's stdout gets, for the same reason: a hook's answer is a decision,
#: not a payload.
MAX_RESPONSE_CHARS = 10_000


class HttpHookError(ValueError):
    pass


def hook_egress_allowlist() -> frozenset[str]:
    """Owner-controlled outbound host allowlist for `http` hook handlers.

    Read from ``RAIKER_HOOK_EGRESS_ALLOWLIST`` (comma-separated host globs, e.g.
    ``hooks.internal.example.com,127.0.0.1:*``). Defaults to **empty**, so a hook
    cannot reach the network until the owner names a host — fail-closed even
    when the hooks file says otherwise, and revocable in one place for every
    rule at once.
    """
    raw = os.environ.get("RAIKER_HOOK_EGRESS_ALLOWLIST", "")
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def egress_granted(url: str | None) -> bool:
    """Whether the owner's grant currently covers *url*'s host."""
    if not url:
        return False
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False
    allowlist = hook_egress_allowlist()
    return any(fnmatch(parsed.netloc, pattern) for pattern in allowlist)


def event_body(hook_input: HookInput, *, limit: int = 12_000) -> str:
    """The bounded, redacted event JSON a hook is allowed to send outward.

    Shared with the `prompt` handler rather than written twice: both send the
    same event to something outside Raiker's process, and two copies of "what a
    hook may reveal" is exactly the kind of pair that drifts apart and turns one
    of them into a leak.

    Private context fields (those whose key starts with ``_``) are the runtime's
    own plumbing — the authorised provider and model for the turn — and never
    leave.
    """
    from raiker.context.redaction import redact_text

    public_context = {
        str(key): value
        for key, value in hook_input.context.items()
        if not str(key).startswith("_")
    }
    raw = json.dumps(
        {
            "event_name": hook_input.event_name,
            "tool_name": hook_input.tool_name,
            "tool_input": hook_input.tool_input,
            "context": public_context,
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )[:limit]
    return redact_text(raw)[0]


def run_http(handler: HookHandler, hook_input: HookInput) -> HookOutput:
    """POST one hook event to the owner-declared destination and read its answer."""
    import urllib.error
    import urllib.request

    url = handler.url
    if not url:
        raise HttpHookError("http_handler_requires_url")
    if not egress_granted(url):
        # Named rather than silent: an owner who added the rule and not the grant
        # should read why nothing happened, on the page that lists the rule.
        raise HttpHookError(f"hook_http_egress_not_granted:{urlparse(url).netloc}")
    body = event_body(hook_input).encode("utf-8")
    request = urllib.request.Request(  # noqa: S310 - scheme checked in egress_granted
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            # Says what this is, so a receiver can tell a hook delivery from any
            # other request. It carries no identity and no credential.
            "User-Agent": "raiker-hook/1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=handler.timeout_ms / 1000) as response:  # noqa: S310
            payload = response.read(MAX_RESPONSE_CHARS + 1)
            status = int(response.status if hasattr(response, "status") else 200)
    except TimeoutError as exc:
        raise CommandHookTimeout(f"hook_timeout:{handler.id}") from exc
    except urllib.error.HTTPError as exc:
        # A responder that refuses is a responder that said nothing, not a deny:
        # inferring "block the action" from a 500 would let an outage become a
        # policy. The exit-code convention is for a *local* program the owner
        # wrote; a remote status is not that.
        raise HttpHookError(f"hook_http_status:{exc.code}") from None
    except OSError as exc:
        raise HttpHookError(f"hook_http_unreachable:{type(exc).__name__}") from None
    text = payload[:MAX_RESPONSE_CHARS].decode("utf-8", errors="replace")
    if not 200 <= status < 300:
        raise HttpHookError(f"hook_http_status:{status}")
    # Returncode 0: the exit-code fallback never applies here, so an answer that
    # is not a decision object is "no decision" rather than a deny.
    return _parse_output(text, "", 0)


__all__ = [
    "HttpHookError",
    "MAX_RESPONSE_CHARS",
    "egress_granted",
    "event_body",
    "hook_egress_allowlist",
    "run_http",
]
