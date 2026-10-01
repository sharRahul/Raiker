"""Findings, notifications, identity, sign-in and diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from raiker.contracts.views import View


@dataclass(frozen=True)
class SecurityFindingView(View):
    """Owner-scoped view of one redacted security finding (monitored MCP
    connections, Phase B/C). ``redacted_detail`` holds redacted metadata only
    (labels, counts, hostnames, added/removed tool names) — never a raw value."""

    finding_id: str
    source: str
    severity: str
    code: str
    summary: str
    redacted_detail: dict[str, Any]
    subject_id: str | None
    state: str
    created_at: str


@dataclass(frozen=True)
class NotificationView(View):
    """Owner-scoped view of one notification (Phase C). Redacted human-readable
    copy only; ``finding_id`` / ``subject_id`` link back to what raised it."""

    notification_id: str
    kind: str
    title: str
    body: str
    finding_id: str | None
    subject_id: str | None
    read: bool
    created_at: str


@dataclass(frozen=True)
class ProviderHealthView(View):
    profile_id: str
    provider: str
    model: str
    endpoint_kind: str
    local_only: bool
    requires_network: bool
    selected: bool
    # Derived from configuration only — reachability is NOT probed here (no network side effects
    # on a read). Live reachability is checked on demand via the CLI (`/model-health`).
    status: str
    detail: str


@dataclass(frozen=True)
class DiagnosticsView(View):
    runtime_mode: str
    production_ready_local_single_user_runtime: bool
    summary: dict[str, Any]
    disabled_capabilities: tuple[str, ...]
    counts: dict[str, int]
    # M6 additions — an honest readiness/diagnostics surface derived from stored state only.
    readiness: dict[str, Any] = field(default_factory=dict)
    missing_config: tuple[str, ...] = ()
    provider_health: tuple[ProviderHealthView, ...] = ()
    # GCR-38 — one row per host-tick background pass: when it last succeeded,
    # when it last threw, the exception *class* it threw, and how many times in
    # a row, so a pass that fails every fifteen seconds is visible.
    background_workers: tuple[dict[str, Any], ...] = ()
    # GCR-45 — which file the built-in model registry was actually read from,
    # independent of the working directory the host was launched from.
    model_profile_source: dict[str, str] = field(default_factory=dict)
    scope_note: str = "Status reflects the local single-user runtime only."


@dataclass(frozen=True)
class IdentityView(View):
    principal_id: str
    principal_type: str
    display_name: str
    subject: str | None = None
    turn_id: str | None = None
    key_id: str | None = None
    issued_at: str | None = None
    expires_at: str | None = None
    state: str = "unknown"


@dataclass(frozen=True)
class AuthSessionView(View):
    # The only response that intentionally contains a token. Never logged; held in memory by the SPA.
    token: str
    session_id: str
    principal_id: str
    expires_at: str | None


@dataclass(frozen=True)
class AuthError(View):
    ok: bool = False
    reason_code: str = "auth_failed"
    message: str = ""
