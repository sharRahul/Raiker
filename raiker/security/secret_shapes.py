"""The published credential formats Raiker looks for, in one place.

Used by ``scripts/scan_secrets.py`` (CI fails a change that commits one) and by
the push preview (TOOL-30: a push whose outgoing commits add one is refused
before the owner is asked). High-precision shapes only: each is a real
provider's key format, so a match is a key or a deliberate fixture, never a
hash or an identifier. A match is reported by a fingerprint, never by value.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any

RULES: dict[str, re.Pattern[str]] = {
    "anthropic_key": re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}"),
    "openai_key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9]{32,}\b"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    # The stateless installation-token form GitHub began issuing 2026-04-27:
    # `ghs_`, the App id, an underscore and a JWT.
    "github_installation_jwt": re.compile(r"\bghs_[0-9]+_[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
    "github_pat": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{60,}\b"),
    "huggingface_token": re.compile(r"\bhf_[A-Za-z0-9]{34}\b"),
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "slack_token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    "google_api_key": re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    "stripe_live_key": re.compile(r"\b(?:sk|rk)_live_[0-9A-Za-z]{24,}\b"),
    "private_key_block": re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"),
}

#: Files that cannot hold text a person committed by hand.
SKIP_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".woff", ".woff2", ".pdf", ".zip")
SKIP_NAMES = ("package-lock.json", "uv.lock")

#: Where a repository records its deliberate fixtures, in the format
#: ``scripts/scan_secrets.py`` reads.
EXCEPTIONS_PATH = Path(".github") / "secret-scan-exceptions.json"


def fingerprint(value: str) -> str:
    """A one-way label for a match, stable across lines moving."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def skipped(path: str) -> bool:
    return path.endswith(SKIP_SUFFIXES) or Path(path).name in SKIP_NAMES


def matches(line: str) -> list[tuple[str, str]]:
    """``(rule, fingerprint)`` for every credential shape in one line."""
    return [
        (rule, fingerprint(match.group(0)))
        for rule, pattern in RULES.items()
        for match in pattern.finditer(line)
    ]


def excused(repo_root: Path, today: dt.date | None = None) -> set[tuple[str, str]]:
    """``(path, fingerprint)`` pairs a repository excuses and has not let expire.

    A malformed file excuses nothing, so a broken exceptions list can only make
    the check stricter.
    """
    try:
        raw: Any = json.loads((repo_root / EXCEPTIONS_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    day = today or dt.date.today()
    pairs: set[tuple[str, str]] = set()
    for entry in raw.get("exceptions", []) if isinstance(raw, dict) else []:
        try:
            if dt.date.fromisoformat(str(entry["expires"])) >= day:
                pairs.add((str(entry["path"]), str(entry["fingerprint"])))
        except (KeyError, TypeError, ValueError):
            continue
    return pairs
