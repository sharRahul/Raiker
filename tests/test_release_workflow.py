# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from raiker.app.release import TARGETS_BY_ID

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "release.yml"


def _workflow() -> dict[str, Any]:
    loaded = yaml.load(WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(loaded, dict)
    return loaded


def _step(job: dict[str, Any], name: str) -> dict[str, Any]:
    for step in job["steps"]:
        if step.get("name") == name:
            return step
    raise AssertionError(f"missing workflow step: {name}")


def test_release_workflow_is_manual_and_publishes_only_a_signed_draft() -> None:
    workflow = _workflow()

    assert set(workflow["on"]) == {"workflow_dispatch"}
    assert workflow["jobs"]["channel"]["if"] == "inputs.signing == 'require'"
    publish = workflow["jobs"]["publish"]
    assert "inputs.publish" in publish["if"]
    assert "inputs.signing == 'require'" in publish["if"]
    assert "--draft" in _step(publish, "Create the draft")["run"]


def test_release_workflow_covers_supported_cross_platform_runners() -> None:
    assert {
        target_id: target.runner for target_id, target in TARGETS_BY_ID.items()
    } == {
        "macos-arm64": "macos-14",
        "windows-x86_64": "windows-2022",
        "linux-x86_64": "ubuntu-22.04",
        "linux-arm64": "ubuntu-22.04-arm",
    }


def test_release_build_installs_desktop_tooling_and_native_appimagetool() -> None:
    build = _workflow()["jobs"]["build"]

    install = _step(build, "Install package and desktop build tool")
    assert 'python -m pip install -e ".[dev]"' in install["run"]
    appimagetool = _step(build, "Install appimagetool")["run"]
    assert "x86_64" in appimagetool
    assert "aarch64" in appimagetool


def test_release_artifact_actions_are_immutable() -> None:
    workflow = _workflow()
    artifact_uses = [
        step["uses"]
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
        if str(step.get("uses", "")).startswith(
            ("actions/upload-artifact@", "actions/download-artifact@")
        )
    ]

    assert len(artifact_uses) == 6
    assert all(
        re.fullmatch(r"actions/(?:upload|download)-artifact@[0-9a-f]{40}", use)
        for use in artifact_uses
    )
