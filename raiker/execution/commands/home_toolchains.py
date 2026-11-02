"""Toolchains installed in the owner's home, mounted on terms of their own.

The sandbox never mounts the owner's home: it holds credentials, history and
other projects. Two common installs live there anyway, and a project that
needs them could not run at all:

* **rustup** puts proxies (`cargo`, `rustc`, …) in `~/.cargo/bin` and the
  toolchains in `~/.rustup`. Both are mounted read-only; `~/.cargo` itself is
  not, because it holds `credentials.toml` and the registry cache. Cargo's own
  home stays the sandbox's (`CARGO_HOME` under the copy), and rustup is told
  where its toolchains are and not to install anything.
* **nvm** puts each Node version in `~/.nvm/versions/node/<version>`. That one
  folder is mounted read-only; `~/.npmrc` and the rest of `~/.nvm` are not.

Linux only: that is the boundary that mounts toolchains. Anything else in a
home folder stays out of reach, as before.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

#: The rustup proxies a project's commands use.
RUST_PROGRAMS = frozenset(
    {"cargo", "rustc", "rustdoc", "rustfmt", "cargo-fmt", "cargo-clippy", "clippy-driver"}
)
NODE_PROGRAMS = frozenset({"node", "npm", "npx"})
_NODE_VERSION = re.compile(r"v\d+\.\d+\.\d+")


@dataclass(frozen=True)
class HomeToolchain:
    """What the boundary needs for one program from a home install."""

    executable: str
    mounts: tuple[str, ...]
    environment: dict[str, str] = field(default_factory=dict)
    path_entry: str = ""


def home_toolchain(name: str, search_path: str, home: Path | None = None) -> HomeToolchain | None:
    """The governed home install that provides *name* on *search_path*, if any."""
    if not sys.platform.startswith("linux") or "/" in name:
        return None
    home = (home or Path.home()).resolve()
    found = shutil.which(name, path=search_path)
    if found is None:
        return None
    return governed(Path(found).absolute(), home)


def governed(found: Path, home: Path) -> HomeToolchain | None:
    """*found* as a rustup proxy or an nvm Node, or ``None`` for anything else."""
    rust = _rustup(found, home)
    return rust if rust is not None else _nvm(found, home)


def _rustup(found: Path, home: Path) -> HomeToolchain | None:
    bin_dir = home / ".cargo" / "bin"
    rustup_home = home / ".rustup"
    if found.parent != bin_dir or found.name not in RUST_PROGRAMS:
        return None
    if not (rustup_home / "toolchains").is_dir():
        return None
    # The proxy is a link to `rustup` in the same folder; nothing outside the
    # two mounted folders may be what actually runs.
    target = found.resolve()
    if not any(target == place or place in target.parents for place in (bin_dir, rustup_home)):
        return None
    return HomeToolchain(
        executable=str(found),
        mounts=(str(bin_dir), str(rustup_home)),
        environment={"RUSTUP_HOME": str(rustup_home), "RUSTUP_AUTO_INSTALL": "0"},
        path_entry=str(bin_dir),
    )


def _nvm(found: Path, home: Path) -> HomeToolchain | None:
    versions = home / ".nvm" / "versions" / "node"
    prefix = found.parent.parent
    if (
        found.name not in NODE_PROGRAMS
        or found.parent.name != "bin"
        or prefix.parent != versions
        or not _NODE_VERSION.fullmatch(prefix.name)
    ):
        return None
    # `npm` and `npx` link into the version's own `lib`; a link out of it
    # would mount one folder and run another.
    target = found.resolve()
    if prefix not in target.parents:
        return None
    return HomeToolchain(
        executable=str(found),
        mounts=(str(prefix),),
        path_entry=str(prefix / "bin"),
    )


def with_path_entry(environment: dict[str, str], entry: str) -> None:
    """Put *entry* first on the run's ``PATH``, so the program's own children
    (cargo starting rustc, npm starting node) find the same install."""
    if not entry:
        return
    current = environment.get("PATH", "")
    environment["PATH"] = entry + (os.pathsep + current if current else "")
