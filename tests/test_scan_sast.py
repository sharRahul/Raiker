"""DEC-24 step 7 — an unreviewed static-analysis security finding fails the change.

The gate runs ruff's Bandit rules over the shipped code. A finding passes only
under an exception naming an owner, a reason and an expiry; an expired or
unused exception fails like the finding it excused, and moving code does not
invalidate a review while changing the flagged code does.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("scan_sast", ROOT / "scripts" / "scan_sast.py")
assert _SPEC is not None and _SPEC.loader is not None
scan_sast = importlib.util.module_from_spec(_SPEC)
sys.modules["scan_sast"] = scan_sast
_SPEC.loader.exec_module(scan_sast)

TODAY = dt.date(2026, 10, 10)


def _finding(source: str = 'conn.execute(f"SELECT * FROM t WHERE {where}")') -> object:
    return scan_sast.Finding(
        "raiker/x.py", 12, "S608", "possible SQL injection", scan_sast.fingerprint("S608", source)
    )


def _exception(finding: object, expires: str = "2027-01-01") -> dict[str, str]:
    return {
        "path": finding.path,  # type: ignore[attr-defined]
        "rule": finding.rule,  # type: ignore[attr-defined]
        "fingerprint": finding.fingerprint,  # type: ignore[attr-defined]
        "owner": "Raiker maintainers",
        "reason": "fixed fragments",
        "expires": expires,
    }


def test_an_unreviewed_finding_fails() -> None:
    problems = scan_sast.check([_finding()], [], TODAY)
    assert len(problems) == 1 and "unreviewed finding" in problems[0]


def test_a_reviewed_finding_passes() -> None:
    finding = _finding()
    assert scan_sast.check([finding], [_exception(finding)], TODAY) == []


def test_an_expired_exception_fails_like_the_finding() -> None:
    finding = _finding()
    problems = scan_sast.check([finding], [_exception(finding, "2026-10-09")], TODAY)
    assert len(problems) == 1 and "expired exception" in problems[0]


def test_an_exception_that_matches_nothing_fails() -> None:
    problems = scan_sast.check([], [_exception(_finding())], TODAY)
    assert len(problems) == 1 and "matches nothing" in problems[0]


def test_an_exception_missing_its_owner_or_reason_fails() -> None:
    entry = _exception(_finding())
    del entry["owner"]
    problems = scan_sast.check([_finding()], [entry], TODAY)
    assert any("missing owner" in p for p in problems)


def test_the_fingerprint_survives_moving_and_not_changing() -> None:
    same = scan_sast.fingerprint("S608", '  conn.execute(f"SELECT * FROM t WHERE {where}")\n')
    assert same == _finding().fingerprint  # type: ignore[attr-defined]
    changed = scan_sast.fingerprint("S608", 'conn.execute(f"SELECT * FROM t WHERE {user_text}")')
    assert changed != same


def test_every_committed_exception_is_complete_and_dated() -> None:
    data = json.loads((ROOT / ".github" / "sast-exceptions.json").read_text(encoding="utf-8"))
    for entry in data["exceptions"]:
        assert {"path", "rule", "fingerprint", "owner", "reason", "expires"} <= set(entry)
        dt.date.fromisoformat(entry["expires"])
        assert entry["rule"].startswith("S")


def test_the_style_only_rules_are_not_gated() -> None:
    for rule in ("S101", "S110", "S112"):
        assert rule not in scan_sast.SELECT
    assert "S603" in scan_sast.IGNORE and "S607" in scan_sast.IGNORE
