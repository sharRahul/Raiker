from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _workflow() -> dict[str, Any]:
    return yaml.load(
        Path(".github/workflows/ci.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )


def _pinned_or_local(reference: str) -> bool:
    """A third-party action pinned to a full commit, or one of this repository's own."""
    if reference.startswith("./"):
        return True
    return "@" in reference and len(reference.split("@", 1)[1]) == 40


def test_every_action_reference_is_pinned_or_local() -> None:
    """OPT-19 — moving shared set-up into a local action must not unpin it.

    A local action is reviewed with the workflows that use it, so it may be
    referenced by path; what it uses in turn is held to the same rule.
    """
    files = sorted(Path(".github/workflows").glob("*.yml")) + sorted(
        Path(".github/actions").glob("*/action.yml")
    )
    unpinned: list[str] = []
    for path in files:
        document = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        steps = [
            step
            for job in document.get("jobs", {}).values()
            for step in job.get("steps", [])
        ] + list(document.get("runs", {}).get("steps", []))
        unpinned += [
            f"{path}: {step['uses']}"
            for step in steps
            if "uses" in step and not _pinned_or_local(step["uses"])
        ]
    assert len(files) >= 3
    assert unpinned == []
    local = [path for path in files if path.name == "action.yml"]
    for path in local:
        assert "actions/setup-python@" in path.read_text(encoding="utf-8")


def test_ci_runs_the_suite_under_the_products_memory_security_default() -> None:
    job = _workflow()["jobs"]["python"]
    steps = {step["name"]: step for step in job["steps"]}
    assert "Verify SQLCipher memory-security probe" in steps
    assert "scripts/test_shard.py --check 3" in steps["Every test file is in exactly one shard"]["run"]

    # The suite runs in three shards, each serially, each inside the limit the
    # single job used to reach, and under the product's own memory-security
    # default: fresh workspaces come from a schema template (FIXED-1247), so it
    # no longer has to be switched off to finish.
    tests = _workflow()["jobs"]["python-tests"]
    assert tests["strategy"]["matrix"]["shard"] == ["1", "2", "3"]
    test_step = {step["name"]: step for step in tests["steps"]}["Run tests"]
    assert "RAIKER_SQLCIPHER_MEMORY_SECURITY" not in (test_step.get("env") or {})
    assert "-vv" in test_step["run"]
    assert "scripts/test_shard.py ${{ matrix.shard }} 3" in test_step["run"]
    assert tests["timeout-minutes"] == "45"


def test_every_test_file_lands_in_exactly_one_shard() -> None:
    from scripts.test_shard import shards, test_files

    dealt = [name for bucket in shards(3) for name in bucket]
    assert sorted(dealt) == test_files()
    assert all(bucket for bucket in shards(3))


def test_a_dependency_with_a_known_vulnerability_fails_ci() -> None:
    """CR-12 — both ecosystems are audited on every change that could ship."""
    job = _workflow()["jobs"]["supply-chain"]
    runs = "\n".join(step.get("run", "") for step in job["steps"])
    assert "pip_audit" in runs
    assert "pyproject.toml" in runs
    # Every action is pinned to a commit, like the rest of this workflow.
    for step in job["steps"]:
        if "uses" in step:
            assert _pinned_or_local(step["uses"]), step["uses"]

    web = yaml.load(
        Path(".github/workflows/ci.yml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader
    )
    web_runs = [step.get("run", "") for job in web["jobs"].values() for step in job["steps"]]
    assert any(run.startswith("npm audit") for run in web_runs)
