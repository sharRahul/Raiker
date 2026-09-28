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
    assert "--require-hashes --no-deps -r requirements/release-build.txt" in install["run"]
    assert "python -m pip install --no-deps -e ." in install["run"]
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


def _locked(path: Path) -> dict[str, list[str]]:
    """Each pinned requirement in an exported file and the digests it permits."""
    pins: dict[str, list[str]] = {}
    current: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+)==\S+", line)
        if match:
            current = match.group(1).lower().replace("_", "-")
            pins[current] = []
        elif current is not None and "--hash=sha256:" in line:
            pins[current].append(line.strip())
    return pins


def test_the_release_wheels_come_from_the_hash_locked_set() -> None:
    # GCR-41 — `pip wheel .` let the resolver choose on the day of the build.
    run = _step(_workflow()["jobs"]["build"], "Resolve this platform's wheels")["run"]
    assert "--require-hashes --no-deps -r requirements/release.txt" in run
    assert "pip wheel --no-deps . --wheel-dir wheels" in run
    assert "pip wheel . --wheel-dir" not in run


def test_every_runtime_dependency_is_pinned_with_a_digest() -> None:
    import tomllib

    declared = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    locked = _locked(ROOT / "requirements" / "release.txt")
    for requirement in declared["project"]["dependencies"]:
        name = re.split(r"[<>=;!~\s\[]", requirement, maxsplit=1)[0].lower().replace("_", "-")
        assert name in locked, f"{name} is declared and not in requirements/release.txt"
    assert all(digests for digests in locked.values()), "a pin with no digest"


def test_the_build_set_carries_the_desktop_build_tool() -> None:
    locked = _locked(ROOT / "requirements" / "release-build.txt")
    assert "pyinstaller" in locked
    assert set(_locked(ROOT / "requirements" / "release.txt")) <= set(locked)
