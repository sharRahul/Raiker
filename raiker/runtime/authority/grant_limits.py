"""QUI-P03 — **Allow with limits**: a standing grant that names its limits.

A standing grant (``grants.py``) says *this action shape may run unprompted,
below this risk, until it expires*. That was enough for a Security Settings
entry and too blunt for the approval card. The Quiet UI plan asks that choosing
**Allow with limits** *require* the limits: where it applies, which recipients
or sites, which account, how many times, until when, and whether attachments
and sensitive content still ask. This module is those limits.

A rule never widens anything. It is consulted only for an **ordinary** approval
the broker was about to park (never a critical action, a question to the owner,
a hook or managed-policy pause, or a push without its delegation), the
action still runs through the full runtime authority, and every limit fails
closed: a target that cannot be read is a target outside the limits.

Where a rule applies (``scope``), following the plan's *one task / one project /
future work*:

* ``conversation`` — the one conversation it was made in. This is **Allow for
  this task** on the approval card, so it applies there under Standard and
  Within limits; Careful asks anyway, because its turn-level ``ask`` sends
  every change to the owner before any rule is consulted.
* ``project`` — conversations filed in one project whose profile is **Within
  limits**.
* ``future`` — any conversation whose profile is **Within limits**.

The last two apply only where the owner chose Within limits for the
conversation: that profile is defined as "Standard plus the owner's
Allow-with-limits rules", so a Standard conversation behaves as it always has.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any, Literal, cast
from urllib.parse import urlsplit

from typing_extensions import TypedDict

from raiker.memory.policy import MemorySensitivity, classify_memory_sensitivity

Scope = Literal["conversation", "project", "future"]
SCOPES: tuple[str, ...] = ("conversation", "project", "future")

#: The conversation profile under which project and future rules apply.
WITHIN_LIMITS = "within_limits"

MAX_TARGETS = 20
MAX_USES = 100
DEFAULT_USES = 10
#: Expiry in hours. A rule for one task lasts a working day by default; nothing
#: lasts longer than a week, the ceiling every standing grant already has.
MIN_HOURS = 1
MAX_HOURS = 24 * 7
DEFAULT_HOURS = {"conversation": 8, "project": 24 * 7, "future": 24 * 7}

_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_EMAIL = re.compile(r"^[^@\s]+@([a-z0-9-]+\.)+[a-z]{2,63}$")
_DOMAIN = re.compile(r"^([a-z0-9-]+\.)+[a-z]{2,63}$")
_REPO = re.compile(r"^[a-z0-9_.-]+/[a-z0-9_.-]+$")
_CHANNEL = re.compile(r"^#?[a-z0-9_.-]{1,80}$")

#: Argument names whose values are who or where an action reaches.
_RECIPIENT_KEYS = ("to", "cc", "bcc", "recipient", "recipients", "attendees")
_PLACE_KEYS = ("channel", "channel_id", "repo", "repository")
_URL_KEYS = ("url", "endpoint", "link")
_ACCOUNT_KEYS = ("account_id", "account")
_ATTACHMENT_KEYS = ("attachments", "attachment", "files")


class GrantLimits(TypedDict):
    scope: Scope
    session_id: str | None
    project_id: str | None
    targets: list[str]
    account: str | None
    max_uses: int
    attachments: bool
    sensitive_asks: bool


class LimitsError(ValueError):
    """A limit the owner gave that Raiker cannot enforce, by reason code."""


def _target(value: str) -> str:
    """One owner-typed target, normalised, or :class:`LimitsError`."""
    text = value.strip().lower()
    text = re.sub(r"^(https?://)?(www\.)?github\.com/", "", text).removesuffix(".git").strip("/")
    if text.startswith(("http://", "https://")):
        text = (urlsplit(text).hostname or "").lower()
    text = text.removeprefix("*.").removeprefix("@")
    if _EMAIL.match(text) or _DOMAIN.match(text) or _REPO.match(text) or _CHANNEL.match(text):
        return text
    raise LimitsError("grant_limit_target_invalid")


def clean(
    raw: dict[str, Any],
    *,
    session_id: str | None = None,
    project_id: str | None = None,
) -> tuple[GrantLimits, int]:
    """Validate the limits the owner chose; returns them and the expiry in hours.

    ``session_id`` and ``project_id`` come from the server (the approval's own
    conversation and that conversation's project), never from the request, so
    a rule cannot be pointed at a conversation the owner did not decide in.
    """
    if not isinstance(raw, dict):
        raise LimitsError("grant_limits_invalid")
    scope = raw.get("scope", "conversation")
    if scope not in SCOPES:
        raise LimitsError("grant_limit_scope_invalid")
    if scope == "conversation" and not session_id:
        raise LimitsError("grant_limit_needs_conversation")
    if scope == "project" and not project_id:
        raise LimitsError("grant_limit_needs_project")
    targets_raw = raw.get("targets") or []
    if not isinstance(targets_raw, list) or len(targets_raw) > MAX_TARGETS:
        raise LimitsError("grant_limit_targets_invalid")
    targets: list[str] = []
    for entry in targets_raw:
        if not isinstance(entry, str):
            raise LimitsError("grant_limit_target_invalid")
        cleaned = _target(entry)
        if cleaned not in targets:
            targets.append(cleaned)
    # Work beyond one conversation names where it may reach: "allow sending"
    # with no recipient is the unrestricted "Always allow" the plan refuses.
    if scope != "conversation" and not targets:
        raise LimitsError("grant_limit_needs_targets")
    account = raw.get("account")
    if account is not None and (not isinstance(account, str) or not _ID.match(account)):
        raise LimitsError("grant_limit_account_invalid")
    uses = raw.get("max_uses", DEFAULT_USES)
    if isinstance(uses, bool) or not isinstance(uses, int) or not 1 <= uses <= MAX_USES:
        raise LimitsError("grant_limit_uses_invalid")
    hours = raw.get("expires_hours", DEFAULT_HOURS[str(scope)])
    if isinstance(hours, bool) or not isinstance(hours, int) or not MIN_HOURS <= hours <= MAX_HOURS:
        raise LimitsError("grant_limit_expiry_invalid")
    for flag in ("attachments", "sensitive_asks"):
        if flag in raw and not isinstance(raw[flag], bool):
            raise LimitsError(f"grant_limit_{flag}_invalid")
    limits: GrantLimits = {
        "scope": cast(Scope, scope),
        "session_id": session_id if scope == "conversation" else None,
        "project_id": project_id if scope == "project" else None,
        "targets": targets,
        "account": account,
        "max_uses": uses,
        "attachments": bool(raw.get("attachments", False)),
        # Sensitive content asks unless the owner says otherwise, explicitly.
        "sensitive_asks": bool(raw.get("sensitive_asks", True)),
    }
    return limits, hours


def load(row: dict[str, Any]) -> GrantLimits | None:
    """A grant row's limits, or ``None`` for a grant made without any.

    A stored value this build cannot read matches nothing: an unreadable limit
    is not a missing one.
    """
    raw = row.get("limits_json")
    if raw in (None, "", "{}"):
        return None
    try:
        data = json.loads(str(raw))
    except (TypeError, ValueError):
        return _UNREADABLE
    if not isinstance(data, dict) or data.get("scope") not in SCOPES:
        return _UNREADABLE
    return cast(GrantLimits, data)


#: Stands in for limits that could not be read: a rule that covers nothing.
_UNREADABLE: GrantLimits = {
    "scope": "conversation", "session_id": "\x00unreadable", "project_id": None,
    "targets": [], "account": None, "max_uses": 0, "attachments": False,
    "sensitive_asks": True,
}


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[,;]", value) if part.strip()]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, str):
                out.extend(_strings(item))
            elif isinstance(item, dict):
                out.extend(_strings(item.get("email") or item.get("address") or ""))
        return out
    return []


def action_targets(arguments: dict[str, Any]) -> list[str]:
    """Who or where an action reaches, read from its own arguments, lower-cased.

    Every target counts here, for a live action: one no limit contains keeps
    the action outside the rule.
    """
    found: list[str] = []
    for key in _RECIPIENT_KEYS:
        found.extend(address.lower() for address in _strings(arguments.get(key)))
    for key in _PLACE_KEYS:
        found.extend(place.lower().removeprefix("#") for place in _strings(arguments.get(key)))
    for key in _URL_KEYS:
        for url in _strings(arguments.get(key)):
            host = (urlsplit(url).hostname or "").lower()
            found.append(host or url.lower())
    return found


def known_targets(arguments: dict[str, Any]) -> list[str]:
    """The targets a draft or a suggestion may show and send back.

    The API's privacy redactor rewrites every email address in a response to
    ``[REDACTED_EMAIL]``, so an address offered here would come back as a limit
    nobody can be inside. Addresses, and values already redacted, are left out;
    the owner types a recipient into the form when the rule should name one.
    Sites, repositories and channels make the round trip intact.
    """
    return [
        target
        for target in action_targets(arguments)
        if "[redacted" not in target and not _EMAIL.match(target)
    ]


def _within(target: str, allowed: Iterable[str]) -> bool:
    """A reached target is inside the limits when one allowed entry names it.

    An address matches itself or its domain; a host matches its domain and any
    subdomain; a repository or channel matches itself exactly.
    """
    target = target.removeprefix("#")
    host = target.rsplit("@", 1)[-1]
    for entry in allowed:
        entry = entry.removeprefix("#")
        if target == entry:
            return True
        if _DOMAIN.match(entry) and (host == entry or host.endswith("." + entry)):
            return True
    return False


def _sensitive(arguments: dict[str, Any]) -> bool:
    """Credential- or secret-like content anywhere in the arguments."""
    def walk(value: Any) -> Iterable[str]:
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for item in value.values():
                yield from walk(item)
        elif isinstance(value, list):
            for item in value:
                yield from walk(item)

    return any(
        classify_memory_sensitivity(text)
        in {MemorySensitivity.SECRET_LIKE, MemorySensitivity.CREDENTIAL_LIKE}
        for text in walk(arguments)
    )


def uncovered_reason(
    limits: GrantLimits,
    *,
    arguments: dict[str, Any],
    session_id: str,
    session_project: str | None,
    session_profile: str,
    use_count: int,
) -> str | None:
    """Why these limits do not cover the action, or ``None`` when they do."""
    scope = limits.get("scope")
    if scope == "conversation":
        if not session_id or limits.get("session_id") != session_id:
            return "grant_limit_other_conversation"
    elif scope == "project":
        if session_profile != WITHIN_LIMITS:
            return "grant_limit_profile_not_within_limits"
        if not session_project or limits.get("project_id") != session_project:
            return "grant_limit_other_project"
    elif scope == "future":
        if session_profile != WITHIN_LIMITS:
            return "grant_limit_profile_not_within_limits"
    else:
        return "grant_limit_scope_invalid"
    if use_count >= int(limits.get("max_uses") or 0):
        return "grant_limit_uses_spent"
    allowed = limits.get("targets") or []
    if allowed:
        reached = action_targets(arguments)
        # A target that cannot be read is outside the limits, never inside.
        if not reached or not all(_within(target, allowed) for target in reached):
            return "grant_limit_target_outside"
    account = limits.get("account")
    if account:
        named = next((arguments.get(key) for key in _ACCOUNT_KEYS if arguments.get(key)), None)
        if named != account:
            return "grant_limit_other_account"
    if not limits.get("attachments") and any(arguments.get(key) for key in _ATTACHMENT_KEYS):
        return "grant_limit_attachments_ask"
    if limits.get("sensitive_asks", True) and _sensitive(arguments):
        return "grant_limit_sensitive_asks"
    return None


def describe(limits: GrantLimits | None, *, use_count: int = 0) -> list[str]:
    """The limits in words, as every surface shows them."""
    if limits is None:
        return []
    scope = limits.get("scope")
    lines = [
        {
            "conversation": "Only in the conversation it was allowed in",
            "project": "Only in its project, in conversations set to Within limits",
            "future": "In conversations set to Within limits",
        }.get(str(scope), "Covers nothing: its limits could not be read")
    ]
    if limits.get("targets"):
        lines.append("Only to " + ", ".join(limits["targets"]))
    if limits.get("account"):
        lines.append(f"Only with the account {limits['account']}")
    left = max(0, int(limits.get("max_uses") or 0) - use_count)
    lines.append(f"{left} of {limits.get('max_uses')} uses left")
    lines.append("Attachments allowed" if limits.get("attachments") else "Attachments still ask")
    lines.append(
        "Sensitive content still asks" if limits.get("sensitive_asks", True) else "Sensitive content does not ask"
    )
    return lines
