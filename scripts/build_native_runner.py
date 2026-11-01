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
    python scripts/build_native_runner.py --wsl      # the Linux runner for WSL2
    python scripts/build_native_runner.py --wsl --from <file>  # install a built one

``--wsl`` is the runner Windows installs into Raiker's WSL2 distribution
(``--setup-wsl --linux-runner``). It is built for ``x86_64-unknown-linux-musl``,
statically linked, so it runs in whatever distribution the owner imported;
it lands in ``raiker/native/wsl-x86_64/`` and ships inside the Windows
package. A Windows machine cannot build it, so the release builds it on Linux
and the Windows job installs that file with ``--from``.
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
WSL_TAG = "wsl-x86_64"
WSL_TRIPLE = "x86_64-unknown-linux-musl"


def platform_tag(wsl: bool = False) -> str:
    """One directory per (system, machine), because the runner is native code."""
    if wsl:
        return WSL_TAG
    system = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    return f"{system}-{platform.machine().lower()}"


def installed_directory(wsl: bool = False) -> Path:
    return TARGET / platform_tag(wsl)


def binary_name(wsl: bool = False) -> str:
    return f"{BINARY}.exe" if sys.platform == "win32" and not wsl else BINARY


def digest_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(wsl: bool = False) -> Path:
    if shutil.which("cargo") is None:
        raise SystemExit(
            "cargo is not on PATH. The runner is Rust; install a toolchain or "
            "use a release artefact built on a machine that has one."
        )
    command = ["cargo", "build", "--release", "-p", BINARY]
    if wsl:
        command += ["--target", WSL_TRIPLE]
    subprocess.run(command, cwd=CRATE, check=True)  # noqa: S603 - fixed argv, no shell
    release = CRATE / "target" / (WSL_TRIPLE if wsl else "") / "release"
    built = release / binary_name(wsl)
    if not built.is_file():
        raise SystemExit(f"cargo reported success but {built} is missing")
    return built


def install(built: Path, wsl: bool = False) -> Path:
    if wsl and not built.read_bytes()[:4] == b"\x7fELF":
        raise SystemExit(f"{built} is not a Linux executable")
    directory = installed_directory(wsl)
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / binary_name(wsl)
    shutil.copy2(built, destination)
    # The digest is recorded beside the binary and checked before the runner is
    # used. It detects corruption and casual replacement. It is **not**
    # protection against someone with write access to the install directory, who
    # could replace Raiker itself — that needs a signature chain, which is not
    # built.
    (directory / "digest.json").write_text(
        json.dumps(
            {
                "binary": binary_name(wsl),
                "sha256": digest_of(destination),
                "platform": platform_tag(wsl),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return destination


def check(wsl: bool = False) -> int:
    directory = installed_directory(wsl)
    binary = directory / binary_name(wsl)
    manifest = directory / "digest.json"
    if not binary.is_file() or not manifest.is_file():
        print(f"native runner missing for {platform_tag(wsl)}: {directory}")
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
    parser.add_argument("--wsl", action="store_true", help="the static Linux runner for WSL2")
    parser.add_argument("--from", dest="source", type=Path, help="install this built runner")
    arguments = parser.parse_args()
    if arguments.check:
        return check(arguments.wsl)
    built = arguments.source if arguments.source is not None else build(arguments.wsl)
    destination = install(built, arguments.wsl)
    print(f"installed {destination}")
    return check(arguments.wsl)


if __name__ == "__main__":
    raise SystemExit(main())
