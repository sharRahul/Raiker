from __future__ import annotations

import base64
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from raiker.execution.windows_authenticode import (
    AuthenticodeError,
    verify_windows_authenticode,
)


def _runner(value: dict[str, str], returncode: int = 0):
    def run(*_args, **_kwargs):
        return subprocess.CompletedProcess([], returncode, json.dumps(value), "")

    return run


def test_authenticode_requires_chain_publisher_spki_and_timestamp(tmp_path: Path) -> None:
    artifact = tmp_path / "runner.exe"
    artifact.write_bytes(b"fixture")
    spki = b"leaf public key"
    value = {
        "status": "Valid",
        "publisher": "CN=Raiker Test",
        "leaf_spki": base64.b64encode(spki).decode(),
        "timestamp_subject": "CN=Timestamp Test",
        "timestamp_not_before": "2026-01-01T00:00:00Z",
        "timestamp_not_after": "2027-01-01T00:00:00Z",
    }
    verdict = verify_windows_authenticode(
        artifact,
        expected_publisher="CN=Raiker Test",
        expected_leaf_spki_sha256=hashlib.sha256(spki).hexdigest(),
        runner=_runner(value),
    )
    assert verdict.status == "publisher_verified"

    with pytest.raises(AuthenticodeError, match="authenticode_spki_mismatch"):
        verify_windows_authenticode(
            artifact,
            expected_publisher="CN=Raiker Test",
            expected_leaf_spki_sha256="0" * 64,
            runner=_runner(value),
        )
    value["timestamp_subject"] = ""
    with pytest.raises(AuthenticodeError, match="authenticode_timestamp_missing"):
        verify_windows_authenticode(
            artifact,
            expected_publisher="CN=Raiker Test",
            expected_leaf_spki_sha256=hashlib.sha256(spki).hexdigest(),
            runner=_runner(value),
        )


def test_authenticode_revocation_or_chain_failure_is_named(tmp_path: Path) -> None:
    artifact = tmp_path / "runner.exe"
    artifact.write_bytes(b"fixture")
    with pytest.raises(AuthenticodeError, match="authenticode_chain_or_revocation_invalid"):
        verify_windows_authenticode(
            artifact,
            expected_publisher="CN=Raiker Test",
            expected_leaf_spki_sha256="0" * 64,
            runner=_runner({"status": "UnknownError"}),
        )
