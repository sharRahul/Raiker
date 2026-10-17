# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from raiker.app.release import TARGETS_BY_ID

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "release.yml"
#: DIST-11 — the per-target build, install and test of the desktop installers,
#: called by the release with the signing identities.
PACKAGE_PATH = ROOT / ".github" / "workflows" / "desktop-package.yml"


def _workflow(path: Path = WORKFLOW_PATH) -> dict[str, Any]:
    loaded = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
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


def test_the_release_builds_the_desktop_installers_with_its_signing_decision() -> None:
    """DIST-01 — the release publishes the desktop package, not a venv installer."""
    workflow = _workflow()
    desktop = workflow["jobs"]["desktop"]
    assert desktop["uses"] == "./.github/workflows/desktop-package.yml"
    assert desktop["with"]["signed"] == "${{ inputs.signing == 'require' }}"
    assert desktop["secrets"] == "inherit"
    assert "build" not in workflow["jobs"], "the venv-based payload installers are retired"
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "build_installer.py --artifact" not in text
    assert "raiker-release desktop-channel" in text


def test_desktop_packages_are_built_from_the_hash_locked_set() -> None:
    package = _workflow(PACKAGE_PATH)["jobs"]["package"]
    install = _step(package, "Install the hash-locked build environment")
    assert "--require-hashes --no-deps -r requirements/release-build.txt" in install["run"]
    assert "python -m pip install --no-deps -e ." in install["run"]


def test_a_required_signature_is_never_skipped_quietly() -> None:
    package = _workflow(PACKAGE_PATH)["jobs"]["package"]
    for name in ("Prepare the macOS signing identity", "Prepare the Authenticode identity",
                 "Prepare the Linux package signing key"):
        step = _step(package, name)
        assert "env.SIGNED == 'true'" in step["if"]
        assert "refused:" in step["run"]


def test_every_target_is_installed_tested_and_uninstalled_on_its_runner() -> None:
    package = _workflow(PACKAGE_PATH)["jobs"]["package"]
    names = {step.get("name", "") for step in package["steps"]}
    for required in (
        "Install (Windows, NSIS per-user)",
        "Install (macOS, from the .dmg)",
        "Install (Linux, the .deb through apt)",
        "Smoke-test the installed host from a fresh profile",
        "Open the installed window, reach first run, and complete onboarding",
        "Uninstall (Windows) and check the data is kept",
        "Uninstall (macOS) and check the data is kept",
        "Uninstall (Linux) and check the data is kept",
    ):
        assert required in names, required


def test_release_artifact_actions_are_immutable() -> None:
    artifact_uses = [
        step["uses"]
        for path in (WORKFLOW_PATH, PACKAGE_PATH)
        for job in _workflow(path)["jobs"].values()
        for step in job.get("steps", [])
        if str(step.get("uses", "")).startswith(
            ("actions/upload-artifact@", "actions/download-artifact@")
        )
    ]

    assert len(artifact_uses) == 7
    assert all(
        re.fullmatch(r"actions/(?:upload|download)-artifact@[0-9a-f]{40}", use)
        for use in artifact_uses
    )


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
