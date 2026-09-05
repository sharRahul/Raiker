"""A version guard that runs *before* pip resolves anything.

`pyproject.toml` already declares `requires-python = ">=3.11"`, and that is the
real statement of the constraint. This file exists because of *when* pip acts on
it.

pip builds the project's metadata first and resolves the dependency tree second,
and older pip does not check the root package's `Requires-Python` until after
that resolution. On Python 3.10 there is no solution to find, so the resolver
goes looking for one: it walks every dependency down to its floor, downloading
each wheel to read the metadata inside, discarding it, and trying the version
below. Measured on Python 3.10 with the pip that `ensurepip` bundles for it
(23.0.1): **382 MB in four minutes and still going** — ruff descending release by
release, then watchfiles, then uvicorn, then sqlcipher3-wheels. The same command
under pip 26.2.1 stops in about a second with the correct error, because newer
pip checks first.

The build backend runs before either of those, so a check here is the earliest
moment the answer can possibly be given — and the answer takes no network at
all. pip 26.2.1: 1.2 MB. pip 23.0.1 without this file: 382 MB and counting. pip
23.0.1 with it: 1.1 MB.

Everything else — the metadata, the entry points, the package data — still comes
from `pyproject.toml`; `setup()` takes no arguments here and reads all of it from
there.
"""

import sys

MINIMUM = (3, 11)

if sys.version_info < MINIMUM:
    raise SystemExit(
        f"\nRaiker requires Python {MINIMUM[0]}.{MINIMUM[1]} or newer. "
        f"This interpreter is Python {sys.version_info.major}.{sys.version_info.minor} "
        f"({sys.executable}).\n\n"
        "Stopping here on purpose: without this check, pip would spend hundreds of\n"
        "megabytes searching for a dependency set that cannot exist before telling\n"
        "you the same thing.\n\n"
        "Create the environment with a 3.11+ interpreter and install again:\n\n"
        "  Windows      py -3.11 -m venv .venv\n"
        "               .\\.venv\\Scripts\\Activate.ps1\n\n"
        "  Linux/macOS  python3.11 -m venv .venv\n"
        "               . .venv/bin/activate\n\n"
        "Then check it took, and install:\n\n"
        "  python --version\n"
        "  python -m pip install --upgrade pip\n"
        '  python -m pip install -e ".[dev]"\n'
    )

# The guard has to run before setuptools is imported: if a future setuptools
# drops the Python version this interpreter is on, its own import error would
# land in front of the message above and say something much less useful.
from setuptools import setup  # noqa: E402

setup()
