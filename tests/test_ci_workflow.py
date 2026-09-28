from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _workflow() -> dict[str, Any]:
    return yaml.load(
        Path(".github/workflows/ci.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )


def test_ci_probes_memory_locking_without_running_the_whole_suite_locked() -> None:
    job = _workflow()["jobs"]["python"]
    steps = {step["name"]: step for step in job["steps"]}

    assert "Verify SQLCipher memory-security probe" in steps
    test_step = steps["Run tests"]
    assert test_step["env"]["RAIKER_SQLCIPHER_MEMORY_SECURITY"] == "off"
    assert "-vv" in test_step["run"]
    assert job["timeout-minutes"] == "45"


def test_a_dependency_with_a_known_vulnerability_fails_ci() -> None:
    """CR-12 — both ecosystems are audited on every change that could ship."""
    job = _workflow()["jobs"]["supply-chain"]
    runs = "\n".join(step.get("run", "") for step in job["steps"])
    assert "pip_audit" in runs
    assert "pyproject.toml" in runs
    # Every action is pinned to a commit, like the rest of this workflow.
    for step in job["steps"]:
        if "uses" in step:
            assert "@" in step["uses"] and len(step["uses"].split("@", 1)[1]) == 40

    web = yaml.load(
        Path(".github/workflows/web.yml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader
    )
    web_runs = [step.get("run", "") for job in web["jobs"].values() for step in job["steps"]]
    assert any(run.startswith("npm audit") for run in web_runs)
