# SPDX-License-Identifier: Apache-2.0
"""Build the governed-command sandbox runner into the Python package.

The runner is the only part of Raiker that is not Python, and it is the part
that builds the operating-system boundary. It therefore has to travel in the
wheel: a runner that works from a source checkout and is missing from an
installed Raiker is worse than no runner, because the source tree is where the
screenshots get taken.

`[tool.setuptools.packages.find]` is ``find``, not ``find_namespace``, so
``raiker/native/`` needs an ``__init__.py`` or the declared package data applies
to a package setuptools never discovers. That file is in the repository; this
script only fills the platform directory beside it.

Usage::

    python scripts/build_native_runner.py            # build and install
    python scripts/build_native_runner.py --check    # verify what is installed
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRATE = ROOT / "native"
TARGET = ROOT / "raiker" / "native"
BINARY = "raiker-command-runner"


def platform_tag() -> str:
    """One directory per (system, machine), because the runner is native code."""
    system = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    return f"{system}-{platform.machine().lower()}"


def installed_directory() -> Path:
    return TARGET / platform_tag()


def binary_name() -> str:
    return f"{BINARY}.exe" if sys.platform == "win32" else BINARY


def digest_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> Path:
    if shutil.which("cargo") is None:
        raise SystemExit(
            "cargo is not on PATH. The runner is Rust; install a toolchain or "
            "use a release artefact built on a machine that has one."
        )
    subprocess.run(  # noqa: S603 - fixed argv, no shell
        ["cargo", "build", "--release", "-p", BINARY],
        cwd=CRATE,
        check=True,
    )
    built = CRATE / "target" / "release" / binary_name()
    if not built.is_file():
        raise SystemExit(f"cargo reported success but {built} is missing")
    return built


def install(built: Path) -> Path:
    directory = installed_directory()
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / binary_name()
    shutil.copy2(built, destination)
    # The digest is recorded beside the binary and checked before the runner is
    # used. It detects corruption and casual replacement. It is **not**
    # protection against someone with write access to the install directory, who
    # could replace Raiker itself — that needs a signature chain, which is not
    # built.
    (directory / "digest.json").write_text(
        json.dumps(
            {
                "binary": binary_name(),
                "sha256": digest_of(destination),
                "platform": platform_tag(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return destination


def check() -> int:
    directory = installed_directory()
    binary = directory / binary_name()
    manifest = directory / "digest.json"
    if not binary.is_file() or not manifest.is_file():
        print(f"native runner missing for {platform_tag()}: {directory}")
        return 1
    recorded = json.loads(manifest.read_text(encoding="utf-8"))
    actual = digest_of(binary)
    if recorded.get("sha256") != actual:
        print(f"native runner digest mismatch: recorded {recorded.get('sha256')}, found {actual}")
        return 1
    print(f"native runner ok: {binary} ({actual[:16]}…)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify the installed runner only")
    arguments = parser.parse_args()
    if arguments.check:
        return check()
    destination = install(build())
    print(f"installed {destination}")
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
