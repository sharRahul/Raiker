# SPDX-License-Identifier: Apache-2.0
"""Split the Python test files into N shards of about equal running time.

The Python CI job ran the whole suite in one process and reached its
45-minute limit (CI run 39612791351 was cancelled partway through the tests),
so runner speed decided the result. The suite is split instead of the limit
raised: each shard is its own job, run serially exactly as before.

Files are dealt to shards longest first, each to the shard with the least time
so far, using the per-file seconds in ``tests/test_durations.json`` (measured on
a full run; regenerate with ``--measure <pytest --durations=0 log>``). A file
that is not in the table counts as the median, so a new test file lands
somewhere sensible without anyone editing the table. Every file appears in
exactly one shard, and the assignment depends only on the file list and the
table, so it is the same on every runner::

    python scripts/test_shard.py 1 3          # the files of shard 1 of 3
    python scripts/test_shard.py --check 3    # every file in exactly one shard
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
TABLE = TESTS / "test_durations.json"


def test_files() -> list[str]:
    return sorted(path.relative_to(ROOT).as_posix() for path in TESTS.rglob("test_*.py"))


def weights() -> dict[str, float]:
    try:
        table = json.loads(TABLE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    return {str(name): float(seconds) for name, seconds in table.items()}


def shards(count: int) -> list[list[str]]:
    files = test_files()
    table = weights()
    default = statistics.median(table.values()) if table else 1.0
    cost = {name: table.get(name, default) for name in files}
    buckets: list[list[str]] = [[] for _ in range(count)]
    totals = [0.0] * count
    for name in sorted(files, key=lambda item: (-cost[item], item)):
        index = min(range(count), key=lambda i: (totals[i], i))
        buckets[index].append(name)
        totals[index] += cost[name]
    return [sorted(bucket) for bucket in buckets]


def measure(log: Path) -> dict[str, float]:
    """Per-file seconds from a ``pytest --durations=0`` report."""
    pattern = re.compile(r"^\s*([0-9.]+)s\s+(?:call|setup|teardown)\s+(tests/[^:\s]+\.py)::")
    totals: dict[str, float] = {}
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.match(line)
        if match:
            totals[match.group(2)] = totals.get(match.group(2), 0.0) + float(match.group(1))
    return {name: round(seconds, 2) for name, seconds in sorted(totals.items())}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("shard", nargs="?", type=int)
    parser.add_argument("count", nargs="?", type=int)
    parser.add_argument("--check", type=int, metavar="COUNT")
    parser.add_argument("--measure", type=Path, metavar="LOG")
    args = parser.parse_args(argv)
    if args.measure is not None:
        TABLE.write_text(json.dumps(measure(args.measure), indent=1) + "\n", encoding="utf-8")
        return 0
    if args.check is not None:
        dealt = [name for bucket in shards(args.check) for name in bucket]
        missing = sorted(set(test_files()) - set(dealt))
        doubled = sorted({name for name in dealt if dealt.count(name) > 1})
        if missing or doubled:
            print(f"missing: {missing}\ndoubled: {doubled}", file=sys.stderr)
            return 1
        return 0
    if args.shard is None or args.count is None or not 1 <= args.shard <= args.count:
        parser.error("give SHARD and COUNT, with 1 <= SHARD <= COUNT")
    print("\n".join(shards(args.count)[args.shard - 1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
