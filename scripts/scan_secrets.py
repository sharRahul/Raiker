# SPDX-License-Identifier: Apache-2.0
"""Fail a change that commits a credential (DEC-24 step 7, CI-02).

Scans every git-tracked file for the shapes real provider credentials take —
not for "anything long", which would bury the one real key under thousands of
test digests. A finding is reported by file, line and rule, with the value
reduced to a fingerprint: the log of a failed check must not be where a leaked
key is copied next.

A deliberate fixture (a test that proves a key is redacted needs a key-shaped
string) is an exception in ``.github/secret-scan-exceptions.json``. Each one
names the file, the finding's fingerprint, an owner, a reason and an expiry
date. An expired exception fails the check like the finding it excused, so an
exception is a decision someone renews, not a permanent hole; an exception that
matches nothing fails too, so the list cannot fill with entries nobody needs.

    python scripts/scan_secrets.py            # check, exit 1 on any finding
    python scripts/scan_secrets.py --list     # print fingerprints for new exceptions
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCEPTIONS = ROOT / ".github" / "secret-scan-exceptions.json"

#: High-precision shapes only. Each is a published credential format, so a
#: match is a key or a deliberate fixture — never a hash or an identifier.
RULES: dict[str, re.Pattern[str]] = {
    "anthropic_key": re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}"),
    "openai_key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9]{32,}\b"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "github_pat": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{60,}\b"),
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "slack_token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    "google_api_key": re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    "stripe_live_key": re.compile(r"\b(?:sk|rk)_live_[0-9A-Za-z]{24,}\b"),
    "private_key_block": re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"),
}

#: Files that cannot hold text a person committed by hand.
SKIP_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".woff", ".woff2", ".pdf", ".zip")
SKIP_NAMES = ("package-lock.json", "uv.lock")


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    fingerprint: str

    def describe(self) -> str:
        return f"{self.path}:{self.line}: {self.rule} (fingerprint {self.fingerprint})"


def fingerprint(value: str) -> str:
    """A one-way label for a match, stable across lines moving."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def tracked_files(root: Path) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True
    ).stdout.decode("utf-8", "replace")
    return [name for name in out.split("\0") if name]


def scan_text(path: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for rule, pattern in RULES.items():
            for match in pattern.finditer(line):
                findings.append(Finding(path, number, rule, fingerprint(match.group(0))))
    return findings


def scan(root: Path, files: list[str] | None = None) -> list[Finding]:
    findings: list[Finding] = []
    for name in files if files is not None else tracked_files(root):
        if name.endswith(SKIP_SUFFIXES) or Path(name).name in SKIP_NAMES:
            continue
        path = root / name
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        if b"\0" in raw[:4096]:
            continue
        findings.extend(scan_text(name, raw.decode("utf-8", "replace")))
    return findings


@dataclass(frozen=True)
class Exception_:
    path: str
    fingerprint: str
    owner: str
    reason: str
    expires: dt.date


def load_exceptions(path: Path) -> tuple[list[Exception_], list[str]]:
    """The exceptions, and any entry that is not a complete, dated decision."""
    if not path.is_file():
        return [], []
    problems: list[str] = []
    entries: list[Exception_] = []
    for index, raw in enumerate(json.loads(path.read_text(encoding="utf-8")).get("exceptions", [])):
        try:
            entry = Exception_(
                path=str(raw["path"]),
                fingerprint=str(raw["fingerprint"]),
                owner=str(raw["owner"]).strip(),
                reason=str(raw["reason"]).strip(),
                expires=dt.date.fromisoformat(str(raw["expires"])),
            )
        except (KeyError, ValueError, TypeError):
            problems.append(f"exception {index}: needs path, fingerprint, owner, reason and an ISO expiry date")
            continue
        if not entry.owner or not entry.reason:
            problems.append(f"exception {index}: an exception names who owns it and why")
            continue
        entries.append(entry)
    return entries, problems


def evaluate(
    findings: list[Finding], exceptions: list[Exception_], today: dt.date
) -> list[str]:
    """Every reason the check fails: unexcused findings, expired and unused exceptions."""
    failures: list[str] = []
    used: set[tuple[str, str]] = set()
    by_key = {(entry.path, entry.fingerprint): entry for entry in exceptions}
    for finding in findings:
        entry = by_key.get((finding.path, finding.fingerprint))
        if entry is None:
            failures.append(f"credential-shaped value: {finding.describe()}")
            continue
        used.add((entry.path, entry.fingerprint))
        if entry.expires < today:
            failures.append(
                f"expired exception ({entry.expires.isoformat()}, owner {entry.owner}): {finding.describe()}"
            )
    for entry in exceptions:
        if (entry.path, entry.fingerprint) not in used:
            failures.append(f"exception matches nothing: {entry.path} {entry.fingerprint}")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--list", action="store_true", help="Print every finding's fingerprint.")
    args = parser.parse_args(argv)
    findings = scan(ROOT)
    if args.list:
        for finding in findings:
            print(finding.describe())
        return 0
    exceptions, problems = load_exceptions(EXCEPTIONS)
    failures = [*problems, *evaluate(findings, exceptions, dt.date.today())]
    if failures:
        print("Secret scan failed:")
        print("\n".join(f"- {failure}" for failure in failures))
        print(
            "Remove the credential (and rotate it if it was real). A deliberate fixture "
            "goes in .github/secret-scan-exceptions.json with an owner, a reason and an expiry."
        )
        return 1
    print(f"Secret scan passed: {len(findings)} excepted fixture(s), no credentials.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
