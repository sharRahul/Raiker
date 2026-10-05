# SPDX-License-Identifier: Apache-2.0
"""Runtime mode, capability gates and modes, standing grants, audit and
telemetry export, health and the environment a turn sees."""

from __future__ import annotations

from typing import Any, Literal, NotRequired

from typing_extensions import TypedDict

from raiker.control.views.security import BackupView

DecisionMode = Literal["ask", "allow", "auto", "deny"]


class RuntimeModeActivated(TypedDict):
    ok: bool
    mode_name: str


class CapabilityStateSet(TypedDict):
    ok: bool
    capability: str
    target_state: str


class ThreatModelAcknowledged(TypedDict):
    ok: bool
    capability: str
    acknowledged: bool


class CapabilityDisabled(TypedDict):
    ok: bool
    capability: str


class CapabilityDecisionMode(TypedDict):
    """``ok`` is false, and the mode absent, when the capability is unknown."""

    ok: bool
    capability: NotRequired[str]
    decision_mode: NotRequired[DecisionMode]


class CapabilityDecisionModeSet(TypedDict):
    ok: bool
    capability: str
    decision_mode: DecisionMode


class StandingGrantView(TypedDict):
    """One standing grant. ``revoked`` is a boolean on the wire, not the stored 0/1."""

    grant_id: str
    principal_id: str
    granted_by: str
    action_type: str
    tool_name: str
    scope_pattern: str
    risk_ceiling: str
    reason: str
    created_at: str
    expires_at: str
    revoked: bool
    revoked_at: str | None
    use_count: int
    last_used_at: str | None


def standing_grant(row: dict[str, Any]) -> StandingGrantView:
    """A stored or newly built grant row, as the owner's settings read it.

    A grant just created has no use or revocation columns yet; it reads as the
    unused, unrevoked grant it is rather than as a different shape.
    """
    return {
        "grant_id": str(row["grant_id"]),
        "principal_id": str(row["principal_id"]),
        "granted_by": str(row["granted_by"]),
        "action_type": str(row["action_type"]),
        "tool_name": str(row.get("tool_name") or ""),
        "scope_pattern": str(row.get("scope_pattern") or "*"),
        "risk_ceiling": str(row["risk_ceiling"]),
        "reason": str(row.get("reason") or ""),
        "created_at": str(row["created_at"]),
        "expires_at": str(row["expires_at"]),
        "revoked": bool(row.get("revoked") or 0),
        "revoked_at": row.get("revoked_at"),
        "use_count": int(row.get("use_count") or 0),
        "last_used_at": row.get("last_used_at"),
    }


class StandingGrantList(TypedDict):
    ok: bool
    grants: list[StandingGrantView]


class StandingGrantCreated(TypedDict):
    ok: bool
    grant: StandingGrantView


class StandingGrantRevoked(TypedDict):
    ok: bool
    grant_id: str


class AuditExportResult(TypedDict):
    """The manifest of an export just produced; never its events."""

    ok: bool
    export_id: str
    manifest_hash: str
    event_count: int
    redacted: bool
    first_event_id: str | None
    last_event_id: str | None
    export_path: str | None


class AuditExportView(TypedDict):
    export_id: str
    manifest_hash: str
    event_count: int
    redacted: bool
    first_timestamp: str | None
    last_timestamp: str | None
    exported_by: str | None
    created_at: str


class TelemetryDestinationView(TypedDict):
    """One OTLP destination. ``header_ref`` names an environment variable, never a value."""

    destination_id: str
    name: str
    endpoint_url: str
    header_ref: str | None
    include_content: bool
    enabled: bool
    cursor_timestamp: str | None
    cursor_event_id: str | None
    last_status: str | None
    last_attempt_at: str | None
    exported_count: int
    created_at: str
    delivery_cadence: str
    next_delivery_at: str | None


def telemetry_destination(row: dict[str, Any]) -> TelemetryDestinationView:
    return {
        "destination_id": str(row["destination_id"]),
        "name": str(row["name"]),
        "endpoint_url": str(row["endpoint_url"]),
        "header_ref": row.get("header_ref"),
        "include_content": bool(row.get("include_content")),
        "enabled": bool(row.get("enabled", True)),
        "cursor_timestamp": row.get("cursor_timestamp"),
        "cursor_event_id": row.get("cursor_event_id"),
        "last_status": row.get("last_status"),
        "last_attempt_at": row.get("last_attempt_at"),
        "exported_count": int(row.get("exported_count") or 0),
        "created_at": str(row["created_at"]),
        "delivery_cadence": str(row.get("delivery_cadence") or "off"),
        "next_delivery_at": row.get("next_delivery_at"),
    }


class TelemetryDestinationCreated(TypedDict):
    ok: bool
    destination_id: str


class TelemetryCadenceSet(TypedDict):
    ok: bool
    delivery_cadence: str
    next_delivery_at: str | None


class TelemetryDestinationDeleted(TypedDict):
    ok: bool
    deleted: bool


class TelemetryExportRun(TypedDict):
    """A delivery: how many events went, never what they said."""

    ok: bool
    exported: int
    destination: str
    include_content: NotRequired[bool]
    cursor_event_id: NotRequired[str]


class ToolReadinessView(TypedDict):
    """Whether a read tool can answer now, said apart from whether it may."""

    tool: str
    available: bool
    ready: bool
    state: Literal["ready", "needs_provider", "blocked", "unavailable", "transient_failure"]
    checked_at: str
    reason_code: NotRequired[str]
    reason_text: NotRequired[str]
    provider: NotRequired[str]
    remediation_route: NotRequired[str]


class ReadCapabilities(TypedDict):
    capabilities: list[str]
    external: list[str]
    interactive: list[str]
    surfaces: dict[str, list[str]]
    administrative_surfaces: list[str]
    readiness: list[ToolReadinessView]


class EnvironmentContextView(TypedDict):
    """The environment bundle a model turn receives, read by Settings."""

    generated_at_utc: str
    timezone: str
    timezone_source: str
    local_datetime: str
    local_date: str
    local_time: str
    day_of_week: str
    utc_offset: str
    display_date: str
    freshness: str
    answer_language: NotRequired[str]
    location: NotRequired[str]
    timezone_error: NotRequired[str]


class HealthView(TypedDict):
    """Liveness, and whether the encrypted store opens (BUG-86).

    The text-search keys are present only when the store opened, because they
    are read from it.
    """

    status: Literal["ok", "degraded"]
    store: Literal["ok", "unavailable"]
    reason: str
    detail: str
    cipher_memory_security: Literal["on", "off"]
    memory_security_in_force: Literal["on", "off"]
    memory_security_reason: str
    memory_security_mode: Literal["auto", "on", "off"]
    memory_security_probe: Literal["supported", "failed", "not_run"]
    memory_security_checked_at: str | None
    sqlcipher_version: str | None
    memlock_allowance_bytes: int | None
    connection_ceiling: int
    text_search_engine: NotRequired[str]
    text_search_ranking: NotRequired[Literal["bm25_relevance", "recency"]]
    text_search_reason: NotRequired[str]


class RecoveryBackupsView(TypedDict):
    """BUG-323 — what the lock screen may restore from, read from manifests only."""

    #: Why the store will not open: ``store_unreadable`` or ``store_schema_newer``.
    reason: str
    #: The fingerprint of this workspace's key, to compare with each backup's.
    key_fingerprint: str
    #: The newest schema generation this build can open.
    schema_generation: int
    backups: list[BackupView]


class RecoveryRestored(TypedDict):
    """A verified backup switched in; the database that would not open is kept aside."""

    ok: bool
    backup_id: str
    #: Where the old database went, relative to the workspace.
    quarantine: str
    counts: dict[str, int]
    deletions_applied: dict[str, int]
