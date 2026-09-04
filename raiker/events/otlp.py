"""Governed events as OTLP log records (compatibility backlog #18).

Raiker records strictly more per governed action than any compared product
exports: the decision, where the decision came from, the gate that admitted the
action, the approval that carried it, and the hash chain that proves the record
was not edited afterwards. All of it stayed inside the product.
[Cowork exports six event types this way](https://claude.com/docs/cowork/monitoring)
— including `tool_decision`, which carries a decision and its source. What Raiker
lacked was not the record. It was the wire.

This module is the wire's encoding, and nothing else: it turns indexed events
into the OTLP/HTTP JSON body an OpenTelemetry collector accepts, and it decides
what a record is allowed to carry.

**Metadata by default, and metadata is defined here rather than assumed.** A
record carries the event's identifiers and its type — the fields the index keeps
as columns because they are already metadata by construction. It does *not*
carry the event's summary: a summary names the object an action acted on, which
is a file path more often than not, and a path is content.

**Content is one explicit opt-in, and it is still redacted.** With
`include_content`, the record's body is the event payload put through
`redact_event_payload` — the same function the on-screen record and the audit
export pass through, so a destination can never be told more than the owner can
read in the product.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

#: The attribute keys a record carries by default. Every one is a column on
#: `events_index`, which is what makes "metadata only" checkable rather than a
#: claim: a field that is not on this list cannot reach a destination.
METADATA_ATTRIBUTE_KEYS = (
    "event_id",
    "event_type",
    "actor",
    "session_id",
    "turn_id",
    "task_id",
    "risk_level",
)

#: Where an OTLP/HTTP collector receives logs, appended to the owner's endpoint
#: when they gave a base URL rather than a full one.
OTLP_LOGS_PATH = "/v1/logs"

#: The most events one export run will carry. A run that finds more leaves the
#: rest for the next one rather than building an unbounded body.
MAX_RECORDS_PER_RUN = 500


def logs_endpoint(endpoint_url: str) -> str:
    """The URL to POST to, whether the owner gave a base or a full signal URL."""
    trimmed = endpoint_url.rstrip("/")
    if trimmed.endswith(OTLP_LOGS_PATH):
        return trimmed
    return f"{trimmed}{OTLP_LOGS_PATH}"


def _nanoseconds(timestamp: str) -> int:
    """An RFC-3339 timestamp as OTLP's Unix nanoseconds. 0 when unparseable —
    a collector reads that as "no time recorded", which is honest, where a
    fabricated `now` would silently re-date the record."""
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return 0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return int(parsed.timestamp() * 1_000_000_000)


def _attribute(key: str, value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": str(value)}}
    return {"key": key, "value": {"stringValue": str(value)}}


def log_record(row: dict[str, Any], *, include_content: bool) -> dict[str, Any]:
    """One indexed event as an OTLP log record."""
    attributes = [
        _attribute(key, row[key])
        for key in METADATA_ATTRIBUTE_KEYS
        if row.get(key) not in (None, "")
    ]
    body = str(row.get("event_type", ""))
    if include_content:
        from raiker.events.export import redact_event_payload

        payload = row.get("payload")
        if isinstance(payload, dict):
            body = json.dumps(redact_event_payload(payload), sort_keys=True)
    nanos = _nanoseconds(str(row.get("timestamp", "")))
    return {
        "timeUnixNano": str(nanos),
        "observedTimeUnixNano": str(nanos),
        # One severity for every governed event: this is a record of what
        # happened, not a log level. A collector that wants to rank them has
        # `risk_level` as an attribute.
        "severityNumber": 9,
        "severityText": "INFO",
        "body": {"stringValue": body},
        "attributes": attributes,
    }


def logs_payload(
    rows: list[dict[str, Any]], *, include_content: bool, service_name: str = "raiker"
) -> dict[str, Any]:
    """The OTLP/HTTP JSON body for one export run."""
    return {
        "resourceLogs": [
            {
                "resource": {
                    "attributes": [
                        _attribute("service.name", service_name),
                        _attribute("telemetry.sdk.name", "raiker"),
                    ]
                },
                "scopeLogs": [
                    {
                        "scope": {"name": "raiker.governed_events"},
                        "logRecords": [
                            log_record(row, include_content=include_content) for row in rows
                        ],
                    }
                ],
            }
        ]
    }
