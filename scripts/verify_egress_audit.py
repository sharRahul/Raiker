# SPDX-License-Identifier: Apache-2.0
#!/usr/bin/env python3
"""Produce a redacted, release-ready verdict from a local egress capture.

The capture is JSON Lines, one connection observation per line. Each line must
contain an RFC 3339 ``timestamp`` and a ``host``. The verifier deliberately
does not accept packet bodies, headers, URLs, or credentials: release evidence
needs destinations and timing, not private payloads.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(UTC)


def _host(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("host must be a non-empty string")
    host = value.strip().lower().rstrip(".")
    if "/" in host or "://" in host or any(char.isspace() for char in host):
        raise ValueError("host must be a hostname or IP address, not a URL")
    return host


def _load_capture(path: Path) -> tuple[list[tuple[datetime, str]], str]:
    content = path.read_bytes()
    observations: list[tuple[datetime, str]] = []
    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            record: Any = json.loads(raw_line)
            if not isinstance(record, dict):
                raise ValueError("record must be an object")
            observations.append((_timestamp(record.get("timestamp")), _host(record.get("host"))))
        except (json.JSONDecodeError, ValueError) as error:
            raise ValueError(f"invalid capture record at line {line_number}: {error}") from error
    if not observations:
        raise ValueError("capture contains no observations")
    return observations, hashlib.sha256(content).hexdigest()


def _report(
    observations: list[tuple[datetime, str]],
    capture_sha256: str,
    allowed_hosts: set[str],
    minimum_seconds: int,
    scope: str,
) -> dict[str, object]:
    started_at = min(timestamp for timestamp, _ in observations)
    ended_at = max(timestamp for timestamp, _ in observations)
    duration_seconds = int((ended_at - started_at).total_seconds())
    observed_hosts = sorted({host for _, host in observations})
    unexpected_hosts = sorted(set(observed_hosts) - allowed_hosts)
    reasons: list[str] = []
    if duration_seconds < minimum_seconds:
        reasons.append(f"capture duration {duration_seconds}s is below required {minimum_seconds}s")
    if unexpected_hosts:
        reasons.append("unexpected destination hosts were observed")
    return {
        "format": "raiker-local-egress-audit/v1",
        "scope": scope,
        "capture_sha256": capture_sha256,
        "started_at": started_at.isoformat().replace("+00:00", "Z"),
        "ended_at": ended_at.isoformat().replace("+00:00", "Z"),
        "duration_seconds": duration_seconds,
        "minimum_seconds": minimum_seconds,
        "allowed_hosts": sorted(allowed_hosts),
        "observed_hosts": observed_hosts,
        "unexpected_hosts": unexpected_hosts,
        "approved": not reasons,
        "reasons": reasons,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--allowed-host", action="append", default=[])
    parser.add_argument("--minimum-seconds", type=int, default=1800)
    parser.add_argument("--scope", choices=("local-only",), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.minimum_seconds <= 0:
        parser.error("--minimum-seconds must be positive")
    try:
        observations, capture_sha256 = _load_capture(args.capture)
        allowed_hosts = {_host(host) for host in args.allowed_host}
    except (OSError, ValueError) as error:
        parser.error(str(error))
    report = _report(observations, capture_sha256, allowed_hosts, args.minimum_seconds, args.scope)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if report["approved"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
