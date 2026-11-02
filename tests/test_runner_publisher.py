"""The runner is "publisher verified" only by a signature matching a pin in code."""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.execution import runner_publisher
from raiker.execution.runner_publisher import runner_trust

PIN = ("CN=Raiker Release", "ab" * 32)


@pytest.fixture(autouse=True)
def _fresh_cache() -> None:
    runner_publisher._CACHE.clear()


def _runner(tmp_path: Path) -> Path:
    binary = tmp_path / "raiker-command-runner.exe"
    binary.write_bytes(b"MZ runner")
    return binary


def test_without_pins_the_digest_beside_the_binary_is_all_there_is(tmp_path: Path) -> None:
    assert runner_trust(_runner(tmp_path), pins=()) == "package_relative_integrity"


def test_a_signature_by_the_pinned_publisher_is_publisher_verified(tmp_path: Path) -> None:
    seen: list[tuple[str, str]] = []

    def verify(binary: Path, *, expected_publisher: str, expected_leaf_spki_sha256: str) -> None:
        seen.append((expected_publisher, expected_leaf_spki_sha256))

    assert runner_trust(_runner(tmp_path), pins=(PIN,), verify=verify) == "publisher_verified"
    assert seen == [PIN]


def test_an_unsigned_or_differently_signed_runner_is_not(tmp_path: Path) -> None:
    def refuse(binary: Path, **_: str) -> None:
        raise RuntimeError("authenticode_publisher_mismatch")

    assert runner_trust(_runner(tmp_path), pins=(PIN,), verify=refuse) == "package_relative_integrity"
