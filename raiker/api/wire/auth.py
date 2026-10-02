# SPDX-License-Identifier: Apache-2.0
"""Sign-in, MFA, elevation, device sessions and the account."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from raiker.contracts.views import View


@dataclass(frozen=True)
class LoginResultView(View):
    """A sign-in step: a full session, or a ticket that MFA must upgrade.

    ``csrf_token`` pairs with the reload-surviving session cookie and is set
    only on a full session (BUG-253).
    """

    stage: Literal["session", "mfa_required"]
    principal_id: str
    token: str | None
    ticket: str | None
    csrf_token: str | None


@dataclass(frozen=True)
class IssuedSessionView(View):
    """The first-run owner session, with the CSRF token for its cookie."""

    token: str
    session_id: str
    principal_id: str
    expires_at: str | None
    csrf_token: str | None


@dataclass(frozen=True)
class BootstrapStatusView(View):
    can_register: bool


@dataclass(frozen=True)
class PasswordRecoveryBeginView(View):
    """The same shape for a known and an unknown user; only a real ticket completes."""

    ok: bool
    ticket: str


@dataclass(frozen=True)
class MfaEnrollmentView(View):
    secret: str
    provisioning_uri: str
    backup_codes: tuple[str, ...]


@dataclass(frozen=True)
class ElevatedTokenView(View):
    token: str


@dataclass(frozen=True)
class WhoamiView(View):
    principal_id: str
    display_name: str
    scope: str


@dataclass(frozen=True)
class SessionStateView(View):
    """Who this browser is — all three null when nobody is (BUG-267)."""

    principal_id: str | None
    display_name: str | None
    scope: str | None


@dataclass(frozen=True)
class DeviceSessionView(View):
    """One sign-in of this account, without its token."""

    session_id: str
    created_at: str
    last_seen_at: str | None
    device_label: str | None
    revoked: bool
    expires_at: str | None
    scope: str
    current: bool
