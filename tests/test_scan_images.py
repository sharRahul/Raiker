"""DEC-24 step 7 / BUG-329 — a base image with a fixable serious vulnerability fails a change.

The scan itself needs the registry and a pinned grype, which CI installs; these
tests hold the parts that decide: which images are scanned, which findings
count, and how a reviewed exception is honoured, expired or left unused.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("scan_images", ROOT / "scripts" / "scan_images.py")
assert _SPEC is not None and _SPEC.loader is not None
scan_images = importlib.util.module_from_spec(_SPEC)
sys.modules["scan_images"] = scan_images
_SPEC.loader.exec_module(scan_images)

IMAGE = "python:3.13.16-alpine@sha256:" + "a" * 64
TODAY = dt.date(2026, 10, 11)


def _match(vuln: str, severity: str, package: str, fixed: list[str]) -> dict[str, object]:
    return {
        "vulnerability": {"id": vuln, "severity": severity, "fix": {"versions": fixed, "state": "fixed" if fixed else "not-fixed"}},
        "artifact": {"name": package, "version": "1.0"},
    }


def test_only_serious_findings_with_a_fix_count() -> None:
    report = {
        "matches": [
            _match("CVE-1", "Critical", "openssl", ["3.0.1"]),
            _match("CVE-2", "High", "zlib", ["1.3.2-r1"]),
            _match("CVE-3", "High", "glibc", []),
            _match("CVE-4", "Medium", "busybox", ["1.2"]),
            _match("CVE-5", "Negligible", "tzdata", ["2026b"]),
        ]
    }
    found = scan_images.findings_from(IMAGE, report)
    assert [(f.vulnerability, f.package) for f in found] == [("CVE-1", "openssl"), ("CVE-2", "zlib")]


def _exception(**overrides: str) -> dict[str, str]:
    entry = {
        "image": IMAGE,
        "vulnerability": "CVE-2",
        "package": "zlib",
        "owner": "Raiker maintainers",
        "reason": "read and accepted",
        "expires": "2026-11-10",
    }
    entry.update(overrides)
    return entry


def _finding(vuln: str = "CVE-2", package: str = "zlib") -> object:
    return scan_images.Finding(IMAGE, vuln, "High", package, "1.0", ("1.1",))


def test_an_unexcused_finding_fails_and_names_the_way_out() -> None:
    problems = scan_images.check([_finding()], [], TODAY)
    assert len(problems) == 1 and "CVE-2" in problems[0] and "image-scan-exceptions.json" in problems[0]


def test_a_reviewed_exception_passes_until_it_expires() -> None:
    assert scan_images.check([_finding()], [_exception()], TODAY) == []
    expired = scan_images.check([_finding()], [_exception(expires="2026-10-01")], TODAY)
    assert len(expired) == 1 and expired[0].startswith("expired exception")


def test_an_exception_whose_finding_is_gone_fails() -> None:
    problems = scan_images.check([], [_exception()], TODAY)
    assert problems and problems[0].startswith("unused exception")


def test_an_exception_needs_every_field() -> None:
    entry = _exception()
    del entry["owner"]
    problems = scan_images.check([_finding()], [entry], TODAY)
    assert any("missing owner" in problem for problem in problems)


def test_an_exception_covers_one_image_vulnerability_and_package_only() -> None:
    other_package = scan_images.check([_finding(package="zlib-dev")], [_exception()], TODAY)
    assert any("zlib-dev" in problem for problem in other_package)


def test_the_repositorys_bases_are_found_once_each_and_pinned() -> None:
    images = scan_images.base_images(ROOT)
    assert len(images) == len(set(images)) >= 2
    assert all("@sha256:" in image for image in images)


def test_the_committed_exceptions_are_well_formed() -> None:
    data = json.loads((ROOT / ".github" / "image-scan-exceptions.json").read_text(encoding="utf-8"))
    images = set(scan_images.base_images(ROOT))
    for entry in data["exceptions"]:
        assert entry["image"] in images, "an exception must name an image a definition builds on"
        dt.date.fromisoformat(entry["expires"])
        assert entry["owner"] and entry["reason"]
