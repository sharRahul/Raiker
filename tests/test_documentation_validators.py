"""The five documentation validators run in the ordinary suite.

``VERIFICATION_PLAN.md`` lists them as required local checks, and until this
file only one of them ran in CI — in a workflow of its own, a separate runner
that checked out the tree and installed Python to grep five documents. Two
others (documentation truthfulness and the single-user runtime markers) ran
nowhere at all, so a change that deleted the sentence one of them guards would
merge green. Each is a documentation gate that exists because a specific untrue
sentence once shipped; here they fail the same pull request that breaks them.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from scripts import (
    validate_documentation_truthfulness,
    validate_local_single_user_runtime,
    validate_phase_status,
    validate_repo_truthfulness,
    validate_runtime_enablement_readiness,
)

ROOT = Path(__file__).resolve().parents[1]

VALIDATORS: dict[str, Callable[[], int]] = {
    "phase_status": validate_phase_status.main,
    "documentation_truthfulness": validate_documentation_truthfulness.main,
    "repo_truthfulness": validate_repo_truthfulness.main,
    "local_single_user_runtime": validate_local_single_user_runtime.main,
    "runtime_enablement_readiness": validate_runtime_enablement_readiness.main,
}


@pytest.mark.parametrize("name", sorted(VALIDATORS))
def test_documentation_validator_passes(
    name: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # `validate_phase_status` reads paths relative to the repository root, as
    # its command line always has.
    monkeypatch.chdir(ROOT)
    result = VALIDATORS[name]()
    assert result == 0, capsys.readouterr().out
