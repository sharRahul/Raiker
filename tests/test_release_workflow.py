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

    from raiker.app.build_tools import pinned_tools

    install = _step(build, "Install package and desktop build tool")
    assert 'python -m pip install -e ".[dev]"' in install["run"]
    appimagetool = _step(build, "Install appimagetool")["run"]
    assert "appimagetool" in appimagetool
    # GCR-41 — the per-architecture download used to be a `case` in this shell.
    # It is a pinned manifest now, so the coverage is asserted where it lives.
    urls = {tool.url for tool in pinned_tools() if tool.name == "appimagetool"}
    assert any("x86_64" in url for url in urls)
    assert any("aarch64" in url for url in urls)


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


def test_the_appimage_tool_is_pinned_by_version_and_digest() -> None:
    """GCR-41 — `continuous` is a tag the AppImage project moves on every publish.

    Two builds of one Raiker commit a week apart therefore contained different
    build-tool bytes, while the rest of the release process went to some trouble
    to be deterministic. The step must now name an immutable version and check
    what it downloaded against a recorded digest.
    """
    step = _step(_workflow()["jobs"]["build"], "Install appimagetool")

    assert "continuous" not in step["run"], "the moving tag must not come back"
    assert "sha256sum --check --strict" in step["run"]
    assert "pinned_tool" in step["run"], "the pin is data, not a literal in a shell"


def test_every_linux_target_has_a_pinned_appimage_tool() -> None:
    """A target with no pin must fail the release, not fall back to `latest`."""
    from raiker.app.build_tools import pinned_tool

    linux = [target for target in TARGETS_BY_ID.values() if target.os_name == "linux"]
    assert linux
    for target in linux:
        tool = pinned_tool("appimagetool", target.arch)
        assert tool.version in tool.url, "the URL has to carry the version it claims"
        assert re.fullmatch(r"[0-9a-f]{64}", tool.sha256)
        assert "/continuous/" not in tool.url


def test_an_unpinned_architecture_is_refused_rather_than_guessed() -> None:
    import pytest

    from raiker.app.build_tools import pinned_tool

    with pytest.raises(ValueError, match="build_tool_not_pinned"):
        pinned_tool("appimagetool", "riscv64")
