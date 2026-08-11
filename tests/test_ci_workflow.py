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
