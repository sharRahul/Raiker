# SPDX-License-Identifier: Apache-2.0
"""The owner's settings document, the composer's approval posture, the bundled
guide, the tray's session exchange and a new instance."""

from __future__ import annotations

from typing import Any, Literal

from typing_extensions import TypedDict

from raiker.auth.vault_key_file import VaultState

ApprovalMode = Literal["manual", "auto", "skip", "dont_ask"]


class SettingsStatus(TypedDict):
    vault: VaultState
    mfa_enrolled: bool
    #: The fixed sign-in handle.
    username: str
    #: What to call this owner, resolved once server-side (RR-IDENTITY-01).
    display_name: str


class SettingsView(TypedDict):
    """The owner's settings document — their own keys, stored as written — and status."""

    settings: dict[str, Any]
    status: SettingsStatus
    #: 13.2 #6 — what the stored document was when this was read. A save sends
    #: it back, so an edit made from a stale read cannot overwrite a newer one.
    revision: str


class SettingsSaved(TypedDict):
    settings: dict[str, Any]
    revision: str
    #: Keys another surface had changed since the save's read, kept as they
    #: were rather than overwritten, because this save did not touch them.
    merged_keys: list[str]


class ComposerApprovalMode(TypedDict):
    approval_mode: ApprovalMode


class GuideSectionSummary(TypedDict):
    slug: str
    title: str
    summary: str


class GuideIndex(TypedDict):
    """The sections this install carries; ``available`` is false when a build shipped none."""

    available: bool
    sections: list[GuideSectionSummary]
    reason_code: str


class GuideSection(GuideSectionSummary):
    """One section's Markdown, rendered by the client."""

    markdown: str


class TraySession(TypedDict):
    """A host-control session for the native tray, exchanged once for its bootstrap secret."""

    token: str
    expires_at: str | None
    scope: str


class InstanceCreated(TypedDict):
    """The new instance's name and mount; the workspace path never reaches the browser."""

    name: str
    url: str
