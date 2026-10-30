"""Malformed probe reports must not turn on a native execution boundary."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from raiker.execution.commands.backends.native import NativeSandboxDriver


def test_probe_runner_uses_a_restricted_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LD_PRELOAD", "attacker-library")
    monkeypatch.setenv("DYLD_INSERT_LIBRARIES", "attacker-library")
    monkeypatch.setenv("RAIKER_TEST_PRIVATE_TOKEN", "private-value")
    captured: dict[str, object] = {}

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, "{}", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    NativeSandboxDriver._default_probe_runner(["runner", "--probe"])
    environment = captured["env"]
    assert isinstance(environment, dict)
    assert "LD_PRELOAD" not in environment
    assert "DYLD_INSERT_LIBRARIES" not in environment
    assert "RAIKER_TEST_PRIVATE_TOKEN" not in environment


def test_non_object_digest_manifest_is_refused(tmp_path: Path) -> None:
    helper = tmp_path / "helper"
    helper.mkdir()
    driver = NativeSandboxDriver(tmp_path, helper_root=helper)
    driver.runner_path().write_bytes(b"test runner")
    (helper / "digest.json").write_text("[]", encoding="utf-8")
    assert driver.probe().reason_code == "native_sandbox_runner_digest_missing"


@pytest.mark.parametrize(
    "available,observations,returncode",
    [("true", {"egress": "enforced"}, 0), (True, [], 0), (True, {"egress": "enforced"}, 1)],
)
def test_malformed_probe_report_fails_closed(
    tmp_path: Path, available: object, observations: object, returncode: int
) -> None:
    helper = tmp_path / "helper"
    helper.mkdir()
    driver = NativeSandboxDriver(tmp_path, helper_root=helper)
    binary = driver.runner_path()
    binary.write_bytes(b"test runner")
    (helper / "digest.json").write_text(
        json.dumps({"sha256": hashlib.sha256(binary.read_bytes()).hexdigest()})
    )
    report = json.dumps({"available": available, "observations": observations})
    driver._run_probe = lambda argv: subprocess.CompletedProcess(argv, returncode, report, "")

    proof = driver.probe()
    assert not proof.available
    assert proof.reason_code == "native_sandbox_probe_failed"


@pytest.mark.parametrize(
    "missing_property",
    ["relay", "workspace_write", "escape_write", "masked_read", "egress", "descendant_reaped"],
)
def test_unverified_required_property_refuses_the_sandbox(
    tmp_path: Path, missing_property: str
) -> None:
    helper = tmp_path / "helper"
    helper.mkdir()
    driver = NativeSandboxDriver(tmp_path, helper_root=helper)
    binary = driver.runner_path()
    binary.write_bytes(b"test runner")
    (helper / "digest.json").write_text(
        json.dumps({"sha256": hashlib.sha256(binary.read_bytes()).hexdigest()})
    )
    observations = {
        name: "enforced"
        for name in (
            "relay",
            "workspace_write",
            "escape_write",
            "masked_read",
            "egress",
            "descendant_reaped",
        )
    }
    observations[missing_property] = "indeterminate"
    report = json.dumps({"available": True, "observations": observations})
    driver._run_probe = lambda argv: subprocess.CompletedProcess(argv, 0, report, "")
    assert not driver.probe().available


@pytest.mark.parametrize("verdict", [None, "indeterminate", "unenforced"])
def test_linux_probe_requires_seccomp_enforcement(tmp_path: Path, verdict: str | None) -> None:
    helper = tmp_path / "helper"
    helper.mkdir()
    driver = NativeSandboxDriver(tmp_path, helper_root=helper)
    binary = driver.runner_path()
    binary.write_bytes(b"test runner")
    (helper / "digest.json").write_text(
        json.dumps({"sha256": hashlib.sha256(binary.read_bytes()).hexdigest()})
    )
    observations = {
        name: "enforced"
        for name in (
            "relay",
            "workspace_write",
            "escape_write",
            "masked_read",
            "egress",
            "descendant_reaped",
        )
    }
    if verdict is not None:
        observations["seccomp"] = verdict
    report = json.dumps({"platform": "linux", "available": True, "observations": observations})
    driver._run_probe = lambda argv: subprocess.CompletedProcess(argv, 0, report, "")
    assert not driver.probe().available


def test_probe_never_grants_access_to_the_original_workspace(tmp_path: Path) -> None:
    original = tmp_path / "original"
    original.mkdir()
    sentinel = original / "owner.txt"
    sentinel.write_text("owner data", encoding="utf-8")
    helper = tmp_path / "helper"
    helper.mkdir()
    seen: list[Path] = []
    driver = NativeSandboxDriver(original, helper_root=helper)
    binary = driver.runner_path()
    binary.write_bytes(b"test runner")
    (helper / "digest.json").write_text(
        json.dumps({"sha256": hashlib.sha256(binary.read_bytes()).hexdigest()})
    )

    def run_probe(argv: list[str]) -> subprocess.CompletedProcess[str]:
        path = Path(argv[argv.index("--workspace") + 1])
        seen.append(path)
        assert path != original
        assert Path(argv[0]).parent == path
        report = {"available": False, "observations": {}}
        return subprocess.CompletedProcess(argv, 0, json.dumps(report), "")

    driver._run_probe = run_probe
    assert not driver.probe().available
    assert seen and all(not path.exists() for path in seen)
    assert sentinel.read_text(encoding="utf-8") == "owner data"


def test_measured_probe_does_not_authorize_original_workspace_execution(tmp_path: Path) -> None:
    helper = tmp_path / "helper"
    helper.mkdir()
    driver = NativeSandboxDriver(tmp_path, helper_root=helper)
    binary = driver.runner_path()
    binary.write_bytes(b"test runner")
    (helper / "digest.json").write_text(
        json.dumps({"sha256": hashlib.sha256(binary.read_bytes()).hexdigest()})
    )
    observations = {
        name: "enforced"
        for name in (
            "relay",
            "workspace_write",
            "escape_write",
            "masked_read",
            "egress",
            "descendant_reaped",
            "seccomp",
        )
    }
    report = json.dumps({"available": True, "observations": observations})
    driver._run_probe = lambda argv: subprocess.CompletedProcess(argv, 0, report, "")
    proof = driver.probe()
    assert not proof.available
    assert proof.reason_code == "native_disposable_workspace_required"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows ACL revocation")
def test_failed_probe_grant_revocation_never_reports_available(tmp_path: Path) -> None:
    helper = tmp_path / "helper"
    helper.mkdir()
    driver = NativeSandboxDriver(tmp_path, helper_root=helper)
    binary = driver.runner_path()
    binary.write_bytes(b"test runner")
    (helper / "digest.json").write_text(
        json.dumps({"sha256": hashlib.sha256(binary.read_bytes()).hexdigest()})
    )
    observations = {
        name: "enforced"
        for name in (
            "relay",
            "workspace_write",
            "escape_write",
            "masked_read",
            "egress",
            "descendant_reaped",
        )
    }
    report = json.dumps({"available": True, "observations": observations})
    driver._run_probe = lambda argv: subprocess.CompletedProcess(
        argv, 1 if "--revoke-grant" in argv else 0, report, ""
    )
    proof = driver.probe()
    assert not proof.available
    assert proof.reason_code == "native_sandbox_probe_failed"
