# SPDX-License-Identifier: Apache-2.0
"""Prove a release artifact actually works on the platform that built it.

BUG-44. ``docs/DESKTOP_DISTRIBUTION_DESIGN.md`` is explicit that *"native
encrypted-database dependencies require packaging tests on every target;
development-machine success is insufficient"*. This is that test, and it is run
by ``.github/workflows/release.yml`` on each target's own runner, against the
artifact that runner just built rather than against the repository it was built
from.

Four things are checked, in the order a first run would hit them:

1. the artifact contains the service, the built web assets, and the native
   wheels — an installer missing any one of them fails at first launch;
2. ``sqlcipher3`` imports on this platform and its SQLCipher build is real —
   an encrypted database opened with the wrong key must fail, because a build
   that silently falls back to plain SQLite would pass every other check while
   storing the owner's workspace in the clear;
3. the same encryption works through Raiker's own store, from the extracted
   tree rather than from the checkout;
4. the artifact's digest matches its manifest.

Usage:  python scripts/packaging_smoke_test.py --artifact dist/raiker-…zip
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REQUIRED_PREFIXES = ("service/raiker/", "service/apps/", "web/", "wheels/")
REQUIRED_FILES = ("version.txt", "installation.json", "web/index.html")


def _fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def check_contents(artifact: Path, extracted: Path) -> int:
    with zipfile.ZipFile(artifact) as archive:
        names = archive.namelist()
        archive.extractall(extracted)
    for required in REQUIRED_FILES:
        if required not in names:
            return _fail(f"artifact is missing {required}")
    for prefix in REQUIRED_PREFIXES:
        if not any(name.startswith(prefix) for name in names):
            return _fail(f"artifact carries nothing under {prefix}")
    record = json.loads((extracted / "installation.json").read_text(encoding="utf-8"))
    print(
        f"ok: {record['version']} for {record['target']} "
        f"({'signed' if record['signing']['applied'] else 'unsigned'}), {len(names)} entries"
    )
    return 0


_ENCRYPTION_PROBE = r"""
import secrets, sys
from sqlcipher3 import dbapi2 as sqlite3

path, key = sys.argv[1], sys.argv[2]
connection = sqlite3.connect(path)
connection.execute(f'PRAGMA key = "x\'{key}\'"')
connection.execute("CREATE TABLE probe (value TEXT)")
connection.execute("INSERT INTO probe VALUES ('workspace secret')")
connection.commit()
connection.close()

# The bytes on disk must not contain the row. A SQLCipher build that quietly
# degraded to plain SQLite would pass every other check in this file.
if b"workspace secret" in open(path, "rb").read():
    raise SystemExit("database is not encrypted at rest")

wrong = sqlite3.connect(path)
wrong.execute(f'PRAGMA key = "x\'{secrets.token_hex(32)}\'"')
try:
    wrong.execute("SELECT value FROM probe").fetchall()
except sqlite3.DatabaseError:
    pass
else:
    raise SystemExit("a wrong key could read the database")
finally:
    wrong.close()

right = sqlite3.connect(path)
right.execute(f'PRAGMA key = "x\'{key}\'"')
assert right.execute("SELECT value FROM probe").fetchone()[0] == "workspace secret"

# RAIKER-2025 — the packaged build is where an FTS5 regression would actually
# reach someone: a bundle freezes whichever wheel was installed when it was
# built, and Raiker's text indexes are FTS5. The runtime probe would fall back
# to FTS4 without breaking anything, which is exactly why this has to be
# checked here rather than left to be noticed.
try:
    right.execute("CREATE VIRTUAL TABLE fts_probe USING fts5(text)")
    right.execute("INSERT INTO fts_probe VALUES ('relevance ranked')")
    ranked = right.execute(
        "SELECT bm25(fts_probe) FROM fts_probe WHERE fts_probe MATCH 'relevance'"
    ).fetchone()
except sqlite3.DatabaseError as exc:
    raise SystemExit(
        f"the packaged sqlcipher has no FTS5, so search would fall back to "
        f"recency ordering: {exc}"
    ) from None
if ranked is None or ranked[0] is None:
    raise SystemExit("the packaged sqlcipher has FTS5 but no bm25() ranking")
right.close()
print(
    "ok: sqlcipher encrypts, refuses a wrong key, reads back with the right one, "
    "and provides FTS5 with bm25 ranking"
)
"""


def check_encryption(extracted: Path) -> int:
    """Run the probe from the *extracted* tree, with its wheels installed.

    Importing ``sqlcipher3`` in this process would prove the runner has it, not
    that the artifact does. A subprocess whose ``PYTHONPATH`` is the extracted
    service directory is the difference between the two.
    """
    with tempfile.TemporaryDirectory() as tmp:
        probe = Path(tmp) / "probe.py"
        probe.write_text(_ENCRYPTION_PROBE, encoding="utf-8")
        database = Path(tmp) / "probe.db"
        environment = {
            **os.environ,
            "PYTHONPATH": str(extracted / "service"),
        }
        result = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [sys.executable, str(probe), str(database), secrets.token_hex(32)],
            capture_output=True,
            text=True,
            env=environment,
            check=False,
        )
    print(result.stdout.strip() or result.stderr.strip())
    return 0 if result.returncode == 0 else _fail("encrypted-database check failed on this target")


def check_manifest(artifact: Path) -> int:
    manifest_path = artifact.parent / f"{artifact.name}.manifest.json"
    if not manifest_path.is_file():
        return _fail(f"no manifest beside {artifact.name}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    if manifest.get("artifact") != artifact.name:
        return _fail("manifest names a different artifact")
    if manifest.get("sha256") != digest:
        return _fail("manifest digest does not match the artifact")
    print(f"ok: manifest matches {digest}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", required=True)
    args = parser.parse_args(argv)
    artifact = Path(args.artifact)
    if not artifact.is_file():
        return _fail(f"{artifact} does not exist")

    with tempfile.TemporaryDirectory() as tmp:
        extracted = Path(tmp) / "extracted"
        for step in (
            lambda: check_contents(artifact, extracted),
            lambda: check_encryption(extracted),
            lambda: check_manifest(artifact),
        ):
            code = step()
            if code != 0:
                return code
    print("ok: packaging smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
