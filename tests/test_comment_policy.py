"""OPT-15 — production comments state invariants, not how a bug was found.

CONTRIBUTING.md keeps the story of a fix in its commit and its
``docs/plans/FIXED_ITEMS.md`` entry; the code cites the ID. A "found live on
<date>" narrative in a production file is that story retold, and it goes stale
the day the code next changes. Tests are exempt: a regression test is the place
that says which failure it pins.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from scripts.measure_loc import classify

ROOT = Path(__file__).resolve().parents[1]
_CHRONOLOGY = re.compile(r"\bFound live\b|\bFound by the\b")


def _production_files() -> list[str]:
    listed = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    return [path for path in listed if classify(path) == "production"]


def test_production_files_do_not_retell_how_a_bug_was_found() -> None:
    production = _production_files()
    # An empty list would pass vacuously; the classifier must still see the code.
    assert "raiker/api/app.py" in production
    offenders = []
    for path in production:
        file = ROOT / path
        if not file.is_file():
            continue
        for number, line in enumerate(file.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if _CHRONOLOGY.search(line):
                offenders.append(f"{path}:{number}: {line.strip()}")
    assert offenders == [], "\n".join(offenders)
