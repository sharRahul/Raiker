"""Malformed probe reports must not turn on a native execution boundary."""

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from raiker.execution.commands.backends.native import NativeSandboxDriver


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
    (helper / "digest.json").write_text(json.dumps({"sha256": hashlib.sha256(binary.read_bytes()).hexdigest()}))
    report = json.dumps({"available": available, "observations": observations})
    driver._run_probe = lambda argv: subprocess.CompletedProcess(argv, returncode, report, "")

    proof = driver.probe()
    assert not proof.available
    assert proof.reason_code == "native_sandbox_probe_failed"
