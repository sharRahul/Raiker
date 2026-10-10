"""DEC-24 step 7 / CI-02 — a credential in a change fails the change.

The scanner looks for published credential formats only, reports a finding by
fingerprint rather than value, and lets a deliberate fixture through only under
an exception that names an owner, a reason and an expiry — an expired or unused
exception fails like the finding it excused.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("scan_secrets", ROOT / "scripts" / "scan_secrets.py")
assert _SPEC is not None and _SPEC.loader is not None
scan_secrets = importlib.util.module_from_spec(_SPEC)
sys.modules["scan_secrets"] = scan_secrets
_SPEC.loader.exec_module(scan_secrets)

TODAY = dt.date(2026, 10, 10)
# Assembled at run time so this file is not itself a finding.
KEY = "sk-" + "ant-" + "api03-" + "Q" * 40


def test_a_provider_key_is_found_and_reported_without_its_value() -> None:
    findings = scan_secrets.scan_text("notes.md", f"token = {KEY}\n")
    assert [(f.path, f.line, f.rule) for f in findings] == [("notes.md", 1, "anthropic_key")]
    assert KEY not in findings[0].describe()
    failures = scan_secrets.evaluate(findings, [], TODAY)
    assert failures and "anthropic_key" in failures[0]


def test_hashes_and_identifiers_are_not_findings() -> None:
    text = "sha256 " + "a" * 64 + "\nsession sess_" + "b" * 40 + "\n"
    assert scan_secrets.scan_text("x.py", text) == []


def test_an_exception_needs_to_be_current_and_used() -> None:
    finding = scan_secrets.scan_text("tests/t.py", KEY)[0]

    def exception(path: str, expires: dt.date) -> object:
        return scan_secrets.Exception_(path, finding.fingerprint, "owner", "fixture", expires)

    assert scan_secrets.evaluate([finding], [exception("tests/t.py", TODAY)], TODAY) == []
    expired = scan_secrets.evaluate([finding], [exception("tests/t.py", TODAY - dt.timedelta(days=1))], TODAY)
    assert expired and expired[0].startswith("expired exception")
    unused = scan_secrets.evaluate([], [exception("tests/t.py", TODAY)], TODAY)
    assert unused and unused[0].startswith("exception matches nothing")
    # An exception for one file does not excuse the same value in another.
    elsewhere = scan_secrets.evaluate([finding], [exception("tests/other.py", TODAY)], TODAY)
    assert any(item.startswith("credential-shaped value") for item in elsewhere)


def test_an_exception_without_an_owner_reason_or_date_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "exceptions.json"
    path.write_text('{"exceptions": [{"path": "a", "fingerprint": "b", "owner": "", "reason": "r", "expires": "2027-01-01"}, {"path": "a"}]}')
    entries, problems = scan_secrets.load_exceptions(path)
    assert entries == [] and len(problems) == 2


def test_this_repository_passes_its_own_scan() -> None:
    assert scan_secrets.main([]) == 0
