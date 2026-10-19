# SPDX-License-Identifier: Apache-2.0
"""Choose the one installer per platform a draft GitHub release carries.

The release workflow builds, installs and tests every installer format on every
platform's own runner. A release an owner downloads from is one file per
platform — Windows x86-64 and Arm, macOS Apple silicon, Linux x86-64 and Arm —
named for that platform (``raiker.app.desktop_release.release_asset_names``).

This copies those five files from ``--from`` to ``--to`` under their published
names and writes ``SHA256SUMS.txt`` beside them. A missing installer is a
refusal: a release that is short a platform is not one.

    python scripts/select_release_assets.py --version 1.2.3 --from dist --to assets
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from raiker.app.desktop_release import release_asset_names, sha256_file  # noqa: E402


def select(version: str, source: Path, destination: Path) -> list[Path]:
    assets = release_asset_names(version)
    missing = [built for built, _platform in assets.values() if not (source / built).is_file()]
    if missing:
        raise SystemExit("refused: missing installers: " + ", ".join(sorted(set(missing))))
    destination.mkdir(parents=True, exist_ok=True)
    chosen: list[Path] = []
    for published, (built, _platform) in assets.items():
        target = destination / published
        shutil.copyfile(source / built, target)
        chosen.append(target)
    lines = [f"{sha256_file(path)}  {path.name}" for path in sorted(chosen)]
    (destination / "SHA256SUMS.txt").write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    return chosen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--version", required=True)
    parser.add_argument("--from", dest="source", type=Path, required=True)
    parser.add_argument("--to", dest="destination", type=Path, required=True)
    args = parser.parse_args(argv)
    for path in select(args.version, args.source, args.destination):
        print(path.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
