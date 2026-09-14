"""RR-AUTHORITY-01 — a switch the owner cannot read is a switch they cannot use.

DEC-16 step 8 asks for a mechanical check that every real side-effect capability
carries, among other things, an owner-facing Permissions description. There was
no such check, and four capabilities had no description at all: the connector
runtimes are registered dynamically, so ``capabilityLabel`` humanised their
names and ``capabilityDescription`` fell through to "Governed capability." The
four switches reaching furthest into an owner's own accounts — their mail, their
calendar, their Slack, their repositories — were the four the Permissions page
explained least.

This is the check that keeps it closed. It reads the web module rather than
duplicating its text, so the copy stays in the one place the page renders it
from, and a capability that gains a real executor cannot reach Permissions
without a sentence saying what it does.
"""
from __future__ import annotations

import re
from pathlib import Path

from raiker.runtime.executors import REAL_EXECUTOR_CAPABILITIES

CAPABILITY_MODEL = Path("web/src/lib/capabilityModel.ts")

#: The label the page falls back to when a capability has no copy at all.
_FALLBACK_DESCRIPTION = "Governed capability."


_ENTRY_START = re.compile(r"^  ([a-z0-9_]+):\s*\{", re.M)
_DESCRIPTION = re.compile(r'description:\s*"((?:[^"\\]|\\.)*)"', re.S)


def _copy_entries() -> dict[str, str]:
    """``{capability: description}`` as the web module declares it.

    Each entry runs from its own key to the next one, which is what makes this
    read the file correctly whether an entry is written on one line or four —
    a regex that assumed the four-line form silently skipped every entry
    following a one-line one, which is the kind of quiet under-reading that
    makes a coverage check worse than none.
    """
    source = CAPABILITY_MODEL.read_text(encoding="utf-8")
    _, _, body = source.partition("const CAPABILITY_COPY: Record<string, CapabilityCopy> = {")
    assert body, "CAPABILITY_COPY is no longer declared the way this check reads it"
    body = body.split("\n};", 1)[0]

    starts = list(_ENTRY_START.finditer(body))
    entries: dict[str, str] = {}
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(body)
        described = _DESCRIPTION.search(body[match.end() : end])
        entries[match.group(1)] = described.group(1) if described else ""
    return entries


def test_every_real_capability_is_described_on_permissions() -> None:
    """A capability with a real executor is a switch an owner can flip. It has
    to say what flipping it does."""
    entries = _copy_entries()
    missing = sorted(REAL_EXECUTOR_CAPABILITIES - set(entries))
    assert missing == [], (
        "A capability has a real executor and no Permissions description, so its "
        "switch renders as 'Governed capability.' Add copy in "
        f"{CAPABILITY_MODEL}: {missing}"
    )


def test_no_description_is_the_fallback_in_disguise() -> None:
    """Copy that says nothing is the same defect with more characters."""
    entries = _copy_entries()
    for capability in sorted(REAL_EXECUTOR_CAPABILITIES):
        description = entries[capability].strip()
        assert description and description != _FALLBACK_DESCRIPTION, (
            f"{capability} has a placeholder Permissions description: {description!r}"
        )
        # Six words is not a style rule: it is the length below which the
        # existing copy in this file stops describing a switch and starts
        # restating its name, which is the fallback with extra characters.
        assert len(description.split()) >= 6, (
            f"{capability}'s Permissions description is too short to tell an owner "
            f"what the switch does: {description!r}"
        )


def test_the_connector_capabilities_say_that_they_only_read() -> None:
    """The regression this check was written for. Each of the four reaches into
    an account the owner owns, and 'read only' is the fact that decides whether
    an owner turns it on."""
    entries = _copy_entries()
    for capability in (
        "connector_github_runtime",
        "connector_gmail_runtime",
        "connector_gcal_runtime",
        "connector_slack_runtime",
    ):
        description = entries[capability]
        assert "Reads only" in description, capability
        # Anything a connector brings back is somebody else's text. Saying so on
        # the switch is how an owner knows the agent is not taking instructions
        # from their inbox.
        assert "untrusted data" in description, capability
