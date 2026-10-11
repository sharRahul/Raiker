# SPDX-License-Identifier: Apache-2.0
"""Fail a change whose container base images carry a fixable serious vulnerability.

DEC-24 step 7 / BUG-329. ``scan_containers.py`` reads the container definitions
for how they are built; this reads what they are built *on*. Every ``FROM``
image in a tracked ``Containerfile``/``Dockerfile`` is pinned by digest, so the
exact image a rebuild would use is scanned — by `grype`_, pulled from the
registry, with no container engine.

A finding fails the change when it is **High or Critical and has a fixed
version**: a vulnerability nobody can fix yet is not a change's fault, and a
Low one is not worth stopping work for. A finding that was read and accepted
goes in ``.github/image-scan-exceptions.json`` with the image, the
vulnerability, the package, an owner, a reason and an expiry — the shape of
the SAST and credential exceptions. An expired or unused entry fails too, so
the file cannot quietly outlive the findings it excuses.

Raiker's own layers on top of these bases add its supervisor binary and its own
sources; the Python and npm dependency audits and the SAST gate cover those.

The scanner is supply-chain input of its own, so CI installs one exact release
and checks its SHA-256 against the value in the workflow before running it; no
``latest`` is ever fetched.

    python scripts/scan_images.py                 # grype on PATH, or $GRYPE
    python scripts/scan_images.py --report a.json # also keep the raw findings

.. _grype: https://github.com/anchore/grype
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCEPTIONS = ROOT / ".github" / "image-scan-exceptions.json"

_FROM = re.compile(r"^FROM\s+(?:--platform=\S+\s+)?(\S+)", re.IGNORECASE)
_GATED = {"High", "Critical"}


@dataclass(frozen=True)
class Finding:
    image: str
    vulnerability: str
    severity: str
    package: str
    version: str
    fixed_in: tuple[str, ...]

    def key(self) -> tuple[str, str, str]:
        return (self.image, self.vulnerability, self.package)

    def describe(self) -> str:
        fixed = ", ".join(self.fixed_in)
        return (
            f"{self.image}: {self.vulnerability} ({self.severity}) in {self.package} "
            f"{self.version}, fixed in {fixed}"
        )


def base_images(root: Path) -> list[str]:
    """Every pinned ``FROM`` image in a tracked definition, once each.

    A ``FROM`` naming an earlier build stage is not an image to pull, and an
    unpinned one is ``scan_containers.py``'s failure, not this script's.
    """
    sys.path.insert(0, str(root / "scripts"))
    try:
        from scan_containers import definitions, instructions
    finally:
        sys.path.pop(0)
    seen: list[str] = []
    for name in definitions(root):
        stages: set[str] = set()
        for _, instruction in instructions((root / name).read_text(encoding="utf-8")):
            match = _FROM.match(instruction)
            if not match:
                continue
            image = match.group(1)
            alias = re.search(r"\s+AS\s+(\S+)\s*$", instruction, re.IGNORECASE)
            if alias:
                stages.add(alias.group(1).lower())
            if image.lower() in stages or "@sha256:" not in image or image in seen:
                continue
            seen.append(image)
    return seen


def findings_from(image: str, report: dict[str, object]) -> list[Finding]:
    """Gated findings in one grype JSON report: serious, and with a fix."""
    out: list[Finding] = []
    for match in report.get("matches", []) or []:  # type: ignore[union-attr]
        vulnerability = match.get("vulnerability", {})
        artifact = match.get("artifact", {})
        fix = vulnerability.get("fix", {}) or {}
        fixed_in = tuple(str(version) for version in fix.get("versions", []) or [])
        severity = str(vulnerability.get("severity", ""))
        if severity not in _GATED or not fixed_in:
            continue
        out.append(Finding(
            image=image,
            vulnerability=str(vulnerability.get("id", "")),
            severity=severity,
            package=str(artifact.get("name", "")),
            version=str(artifact.get("version", "")),
            fixed_in=fixed_in,
        ))
    return out


def run_grype(grype: str, image: str) -> dict[str, object]:
    completed = subprocess.run(  # noqa: S603 - a fixed argv naming a pinned digest
        [grype, f"registry:{image}", "--platform", "linux/amd64", "-o", "json", "-q"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"grype could not scan {image}: {completed.stderr.strip()[-2000:]}")
    return json.loads(completed.stdout)  # type: ignore[no-any-return]


def load_exceptions(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("exceptions", []))


def check(findings: list[Finding], exceptions: list[dict[str, str]], today: dt.date) -> list[str]:
    problems: list[str] = []
    by_key: dict[tuple[str, str, str], int] = {}
    for index, entry in enumerate(exceptions):
        missing = [
            key
            for key in ("image", "vulnerability", "package", "owner", "reason", "expires")
            if not entry.get(key)
        ]
        if missing:
            problems.append(f"exception {index} is missing {', '.join(missing)}")
            continue
        by_key[(entry["image"], entry["vulnerability"], entry["package"])] = index
    used: set[int] = set()
    for finding in findings:
        index = by_key.get(finding.key())
        if index is None:
            problems.append(
                f"{finding.describe()} — update the base image, or record a reviewed "
                f"exception in {EXCEPTIONS.relative_to(ROOT).as_posix()}"
            )
            continue
        used.add(index)
        expires = dt.date.fromisoformat(exceptions[index]["expires"])
        if expires < today:
            problems.append(
                f"expired exception ({exceptions[index]['expires']}): {finding.describe()} — "
                "re-pin the base image or re-review and renew the date"
            )
    for index in sorted(set(by_key.values()) - used):
        entry = exceptions[index]
        problems.append(
            f"unused exception: {entry['image']} {entry['vulnerability']} in {entry['package']} — "
            "the finding is gone; delete the entry"
        )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--report", type=Path, help="write every image's raw grype report here")
    args = parser.parse_args(argv)
    grype = os.environ.get("GRYPE") or shutil.which("grype")
    if not grype:
        print("grype is not installed; CI installs a pinned, checksummed release", file=sys.stderr)
        return 2
    images = base_images(ROOT)
    findings: list[Finding] = []
    reports: dict[str, object] = {}
    for image in images:
        report = run_grype(grype, image)
        reports[image] = report
        findings.extend(findings_from(image, report))
    if args.report:
        args.report.write_text(json.dumps(reports, indent=2), encoding="utf-8")
    problems = check(findings, load_exceptions(EXCEPTIONS), dt.date.today())
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        return 1
    print(
        f"Images: {len(images)} base image(s) scanned; no fixable High or Critical "
        f"vulnerability outside a reviewed exception."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
