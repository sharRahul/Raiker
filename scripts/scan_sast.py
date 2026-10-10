# SPDX-License-Identifier: Apache-2.0
"""Fail a change that adds an unreviewed static-analysis security finding (DEC-24 step 7).

The rules are ruff's port of Bandit (``S``), narrowed to the ones that mean
something in this codebase: SQL built from strings, a shell, unsafe
deserialisation and parsers, weak hashes used for security, disabled TLS
verification, binding every interface, hard-coded credentials and the like.
Rules that only restate a style choice — ``assert`` (S101), ``try/except/pass``
(S110, S112) and "a subprocess was started" (S603, S607, which fire on every
argv-list call this project deliberately uses instead of a shell) — are not
gated.

A finding that has been looked at and is not a defect is an exception in
``.github/sast-exceptions.json``. Each names the file, the rule, the finding's
fingerprint, an owner, a reason and an expiry date — the shape the credential
scan uses. An expired exception fails the check like the finding it excused, so
an exception is a decision someone renews; one that matches nothing fails too,
so the list cannot fill with entries nobody needs. The fingerprint is taken
over the rule and the finding's source text, not its line number, so moving
code does not invalidate a review and changing the flagged line does.

A scanner's success is not a statement that the design is secure: it says that
every finding of these rules has been read by somebody who wrote down why.

    python scripts/scan_sast.py            # check, exit 1 on any finding
    python scripts/scan_sast.py --list     # print entries for new exceptions
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCEPTIONS = ROOT / ".github" / "sast-exceptions.json"

#: What is scanned: the shipped package, the app entry points and the scripts
#: CI and releases run. Tests build hostile inputs on purpose.
PATHS = ("raiker", "apps", "scripts")

#: Bandit's families as ruff numbers them, less the style-only rules above.
SELECT = (
    "S102,S103,S104,S105,S106,S107,S108,S113,"
    "S2,S3,S4,S5,S6,S7"
)
IGNORE = "S603,S607"


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    message: str
    fingerprint: str

    def describe(self) -> str:
        return f"{self.path}:{self.line}: {self.rule} {self.message} (fingerprint {self.fingerprint})"


def fingerprint(rule: str, source: str) -> str:
    """Stable across the finding moving; changes when the flagged code does."""
    normalized = " ".join(source.split())
    return hashlib.sha256(f"{rule}\0{normalized}".encode()).hexdigest()[:16]


def run_ruff(root: Path) -> list[dict[str, object]]:
    completed = subprocess.run(
        [
            sys.executable, "-m", "ruff", "check", *PATHS,
            "--select", SELECT, "--ignore", IGNORE,
            "--output-format", "json", "--exit-zero", "--no-cache",
        ],
        cwd=root, check=True, capture_output=True,
    )
    parsed = json.loads(completed.stdout.decode("utf-8") or "[]")
    return parsed if isinstance(parsed, list) else []


def findings_from(raw: list[dict[str, object]], root: Path) -> list[Finding]:
    found: list[Finding] = []
    for item in raw:
        filename = Path(str(item["filename"]))
        try:
            relative = filename.resolve().relative_to(root).as_posix()
        except ValueError:
            relative = filename.as_posix()
        start = int(item["location"]["row"])  # type: ignore[index]
        end = int(item["end_location"]["row"])  # type: ignore[index]
        try:
            lines = filename.read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []
        source = "\n".join(lines[start - 1 : end])
        rule = str(item["code"])
        found.append(
            Finding(relative, start, rule, str(item.get("message", "")), fingerprint(rule, source))
        )
    return found


def load_exceptions(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("exceptions", []) if isinstance(data, dict) else []
    return [entry for entry in entries if isinstance(entry, dict)]


def check(findings: list[Finding], exceptions: list[dict[str, str]], today: dt.date) -> list[str]:
    """Every problem, in words. Empty means the check passes."""
    problems: list[str] = []
    used: set[int] = set()
    keyed: dict[tuple[str, str, str], int] = {}
    for index, entry in enumerate(exceptions):
        missing = [key for key in ("path", "rule", "fingerprint", "owner", "reason", "expires") if not entry.get(key)]
        if missing:
            problems.append(f"exception {index} is missing {', '.join(missing)}")
            continue
        keyed[(entry["path"], entry["rule"], entry["fingerprint"])] = index
    for finding in findings:
        index = keyed.get((finding.path, finding.rule, finding.fingerprint))
        if index is None:
            problems.append(f"unreviewed finding: {finding.describe()}")
            continue
        used.add(index)
        try:
            expires = dt.date.fromisoformat(exceptions[index]["expires"])
        except ValueError:
            problems.append(f"exception {index} has an unreadable expiry")
            continue
        if expires < today:
            problems.append(
                f"expired exception ({exceptions[index]['expires']}): {finding.describe()} — "
                "re-review it and renew the date, or fix the finding"
            )
    for key, index in keyed.items():
        if index not in used:
            problems.append(
                f"exception {index} ({key[0]} {key[1]} {key[2]}) matches nothing — remove it"
            )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--list", action="store_true", help="print exception entries for every finding")
    args = parser.parse_args(argv)
    findings = findings_from(run_ruff(ROOT), ROOT)
    if args.list:
        print(json.dumps(
            [
                {"path": f.path, "rule": f.rule, "fingerprint": f.fingerprint, "line": f.line, "message": f.message}
                for f in findings
            ],
            indent=2,
        ))
        return 0
    problems = check(findings, load_exceptions(EXCEPTIONS), dt.date.today())
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        print(
            f"{len(problems)} problem(s). Fix the finding, or add a reviewed entry to "
            f"{EXCEPTIONS.relative_to(ROOT).as_posix()} (python scripts/scan_sast.py --list).",
            file=sys.stderr,
        )
        return 1
    print(f"SAST: {len(findings)} finding(s), each reviewed and unexpired.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
