"""The guard in `setup.py`, and the thing that keeps it honest.

`pyproject.toml` declares `requires-python = ">=3.11"`. That is the real
statement of the constraint, and `setup.py` only exists to act on it *earlier*
than pip does: pip resolves the whole dependency tree before older versions of it
check the root package's `Requires-Python`, and on an unsupported interpreter
there is no solution to find — so the resolver walks every dependency down to its
floor, downloading each wheel to read the metadata inside and discarding it.
Measured on Python 3.10 with the pip that `ensurepip` bundles for it: 382 MB in
four minutes, still going. With the guard: 1.1 MB and an immediate error.

The failure mode this file protects against is the guard drifting away from the
declaration it is supposed to be enforcing. A `requires-python` raised in
`pyproject.toml` without a matching `MINIMUM` here would leave the download storm
back in place for the newly-unsupported version, silently.
"""

from __future__ import annotations

import ast
import sys
import tomllib
from collections import namedtuple
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SETUP_PY = REPO_ROOT / "setup.py"
PYPROJECT = REPO_ROOT / "pyproject.toml"

#: Faithful enough to stand in for the real structseq: it compares as a tuple
#: *and* answers `.major`/`.minor`, both of which the guard uses. A plain tuple
#: passes the comparison and then fails on the attribute, which would test the
#: guard's happy path and none of its message.
VersionInfo = namedtuple("VersionInfo", "major minor micro releaselevel serial")

PY_310 = VersionInfo(3, 10, 20, "final", 0)


def _minimum_from_setup() -> tuple[int, ...]:
    """`MINIMUM` read without executing the module.

    Executing it here would run `setup()` with no arguments, which is a build,
    not an assertion.
    """
    for node in ast.parse(SETUP_PY.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "MINIMUM" for t in node.targets
        ):
            value = ast.literal_eval(node.value)
            assert isinstance(value, tuple)
            return value
    raise AssertionError("setup.py no longer defines MINIMUM")


def _run_guard() -> str:
    """Execute the guard and return the refusal it raised."""
    with pytest.raises(SystemExit) as raised:
        exec(compile(SETUP_PY.read_text(encoding="utf-8"), str(SETUP_PY), "exec"), {})
    return str(raised.value)


def test_the_guard_matches_the_declaration_in_pyproject() -> None:
    """`MINIMUM` and `requires-python` say the same thing, or the guard is a lie."""
    declared = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["requires-python"]
    assert declared.startswith(">="), (
        f"requires-python is {declared!r}; the guard in setup.py understands a "
        "lower bound and would need updating for any other form."
    )
    expected = tuple(int(part) for part in declared.removeprefix(">=").strip().split("."))
    assert _minimum_from_setup() == expected


def test_an_unsupported_interpreter_is_refused_before_anything_is_downloaded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The guard raises on 3.10 rather than letting pip go looking."""
    monkeypatch.setattr(sys, "version_info", PY_310)
    message = _run_guard()
    assert "3.11" in message, "the message has to name the version actually required"
    assert "3.10" in message, "and the version that was found, or it is not diagnosable"


def test_the_refusal_says_how_to_fix_it_on_the_platform_it_happens_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A refusal that does not say what to do next just moves the search elsewhere.

    Windows is called out by name because it is the platform where the wrong
    interpreter is easiest to end up on: `python` there is whatever the launcher
    or the Store last associated with the name, and `py -3.11` is the thing that
    picks a version deliberately.
    """
    monkeypatch.setattr(sys, "version_info", PY_310)
    message = _run_guard()
    assert "py -3.11 -m venv" in message
    assert "python3.11 -m venv" in message
    assert "python --version" in message


def test_the_guard_is_the_first_thing_the_build_backend_runs() -> None:
    """`setuptools` must be imported *after* the check, not before.

    If a future setuptools drops the interpreter this is running on, its own
    import error would land in front of the message and say something much less
    useful than the message does.
    """
    source = SETUP_PY.read_text(encoding="utf-8")
    assert source.index("sys.version_info") < source.index("from setuptools import setup")
