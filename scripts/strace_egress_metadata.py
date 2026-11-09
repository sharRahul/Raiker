# SPDX-License-Identifier: Apache-2.0
"""Extract destination/timing observations from a Linux strace network trace.

Capture connect/sendto/sendmsg/sendmmsg with strace -f -ttt -s 0. Keep the
trace private: only the JSONL output is input to verify_egress_audit.py. Failed
attempts count too; this converter never hides a refused destination or adds
synthetic start/end observations to make a short recording pass.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
from datetime import UTC, datetime
from pathlib import Path

_TIME = re.compile(r"^(?:\[pid\s+\d+\]\s+|\d+\s+)?(\d+\.\d+)\s+")
_ADDRESS = re.compile(r'inet_addr\("([^"\n]+)"\)|inet_pton\(AF_INET6,\s*"([^"\n]+)"')


def observations(trace: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for line in trace.splitlines():
        stamp = _TIME.match(line)
        if stamp is None or not re.search(r"\b(connect|sendto|sendmsg|sendmmsg)\(", line):
            continue
        for match in _ADDRESS.finditer(line):
            host = str(ipaddress.ip_address(match.group(1) or match.group(2)))
            timestamp = datetime.fromtimestamp(float(stamp.group(1)), UTC).isoformat().replace("+00:00", "Z")
            records.append({"timestamp": timestamp, "host": host})
    return sorted(records, key=lambda record: record["timestamp"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = observations(args.trace.read_text())
    if not records:
        parser.error("trace contains no IP destination observations")
    args.output.write_text("".join(json.dumps(record) + "\n" for record in records))
    print(f"Wrote {len(records)} observations; no duration or allowlist verdict inferred.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
