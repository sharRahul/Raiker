from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def _ensure_git_identity() -> None:
    """Guarantee a git author/committer identity for tests that create commits.

    Several tests initialise a throwaway git repository and run ``git commit``
    (e.g. the code-review and proposal-lifecycle suites). CI runners have no
    global git identity configured, so those commits fail with exit status 128
    ("Author identity unknown"). Populate the standard git identity environment
    variables when they are absent. ``setdefault`` only fills missing values, so
    developer machines that already have a global identity are unaffected.
    """
    os.environ.setdefault("GIT_AUTHOR_NAME", "Raiker Test")
    os.environ.setdefault("GIT_AUTHOR_EMAIL", "raiker-test@example.com")
    os.environ.setdefault("GIT_COMMITTER_NAME", "Raiker Test")
    os.environ.setdefault("GIT_COMMITTER_EMAIL", "raiker-test@example.com")
