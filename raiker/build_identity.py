"""One answer to "which Raiker is this", for every surface that reports it.

GCR-16. There were four independent ones. ``pyproject.toml`` declares ``0.0.0``
and ``raiker.__version__`` repeats it; the FastAPI application declared
``0.1.0``; every ``ClientMetadata`` a turn is recorded against carried a
hard-coded ``0.0.0``; ``web/package.json`` declares its own ``0.0.0``; and the
release workflow is handed a version through ``workflow_dispatch`` that none of
them ever see. A support question as ordinary as *what are you running* therefore
had four answers, and which one you got depended on which surface you read.

The release build already writes the honest answer into the artifact —
``installation.json``, produced by :func:`raiker.app.release.build_bundle`, with
the version, the commit and the build timestamp in it. This module is the one
place that finds it, so every surface reports the same identity and says the same
thing when there is nothing to report.

The order is deliberate, and each step is evidence rather than inference:

1. the installation record the release pipeline wrote inside this artifact;
2. the distribution metadata of an installed ``raiker`` package;
3. :data:`UNKNOWN_VERSION`, the honest answer for a source checkout — no release
   number is invented for a tree that has never been released.

Kept free of ``raiker`` imports on purpose: ``raiker/__init__.py`` reads it, and
so does :mod:`raiker.app.installation`, which reads much more besides.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from importlib import metadata
from pathlib import Path

__all__ = ["UNKNOWN_VERSION", "BuildIdentity", "build_identity", "version"]

#: What this reports when there is no record and no installed distribution:
#: the same placeholder ``pyproject.toml`` carries, so nothing anywhere invents
#: a release number for a checkout that has never been released.
UNKNOWN_VERSION = "0.0.0"

#: The file the release build writes inside the artifact.
INSTALLATION_FILE = "installation.json"

#: How far above this package to look for the record before concluding there is
#: not one. A ``.deb`` installs to ``/opt/raiker`` and puts the package inside
#: ``/opt/raiker/venv/lib/pythonX.Y/site-packages/raiker`` — five levels — so the
#: walk has to be deep enough for that and bounded enough that it cannot wander
#: up to ``/`` and adopt a stranger's file. Kept identical to the search in
#: :mod:`raiker.app.installation`, which reads the same record for much more.
_RECORD_SEARCH_DEPTH = 6


@dataclass(frozen=True)
class BuildIdentity:
    """Which Raiker this is, as every surface will report it."""

    version: str
    #: The commit the artifact was built from, when a build recorded one.
    commit: str | None
    #: When it was built, as the reproducible timestamp the build stamped.
    built_at: str | None
    #: Whether this came out of the release pipeline at all. ``False`` is the
    #: ordinary answer in development and is not a failure.
    packaged: bool

    @property
    def described(self) -> str:
        """``1.2.3 (abc1234)`` — the one string a log line or a header wants."""
        if self.commit:
            return f"{self.version} ({self.commit[:7]})"
        return self.version


def _record_paths() -> list[Path]:
    declared = os.environ.get("RAIKER_INSTALL_ROOT", "").strip()
    if declared:
        return [Path(declared) / INSTALLATION_FILE]
    here = Path(__file__).resolve().parent
    return [parent / INSTALLATION_FILE for parent in list(here.parents)[:_RECORD_SEARCH_DEPTH]]


def _from_record() -> BuildIdentity | None:
    for candidate in _record_paths():
        try:
            raw = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(raw, dict):
            continue
        recorded = str(raw.get("version") or "").strip()
        if not recorded:
            continue
        commit = raw.get("commit")
        built_at = raw.get("built_at")
        return BuildIdentity(
            version=recorded,
            commit=str(commit) if isinstance(commit, str) and commit else None,
            built_at=str(built_at) if isinstance(built_at, str) and built_at else None,
            packaged=True,
        )
    return None


def _from_distribution() -> BuildIdentity | None:
    try:
        installed = metadata.version("raiker").strip()
    except metadata.PackageNotFoundError:
        return None
    if not installed or installed == UNKNOWN_VERSION:
        return None
    return BuildIdentity(version=installed, commit=None, built_at=None, packaged=False)


@lru_cache(maxsize=1)
def build_identity() -> BuildIdentity:
    """This installation's identity, resolved once per process."""
    return (
        _from_record()
        or _from_distribution()
        or BuildIdentity(version=UNKNOWN_VERSION, commit=None, built_at=None, packaged=False)
    )


def version() -> str:
    """The version string every surface reports."""
    return build_identity().version
