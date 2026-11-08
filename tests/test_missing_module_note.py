"""BD-5 follow-up: a sandboxed check that cannot import the owner's per-user module says why."""

from __future__ import annotations

from pathlib import Path

from raiker.execution.commands.missing_module import missing_module, missing_module_note
from raiker.runtime.executors.tier2_shell import _with_module_note

FAILURE = "C:\\Python313\\python.exe: No module named pytest\n"


def test_the_missing_module_is_read_from_both_python_wordings() -> None:
    assert missing_module(FAILURE) == "pytest"
    assert missing_module("ModuleNotFoundError: No module named 'yaml.loader'") == "yaml"
    assert missing_module("ImportError: cannot import name 'x'") is None


def test_a_module_the_owner_installed_for_themselves_is_named_with_its_fixes(tmp_path: Path) -> None:
    site = tmp_path / "site-packages"
    (site / "pytest").mkdir(parents=True)
    note = missing_module_note(FAILURE, [site])
    assert note is not None
    assert "could not import pytest" in note
    assert "installed for your account only" in note
    assert "Install it for all users" in note and "backend that has it" in note


def test_a_dist_info_counts_and_an_absent_module_says_nothing(tmp_path: Path) -> None:
    site = tmp_path / "site-packages"
    site.mkdir()
    assert missing_module_note(FAILURE, [site]) is None
    (site / "pytest-8.3.0.dist-info").mkdir()
    assert missing_module_note(FAILURE, [site]) is not None


def test_only_a_failed_run_gets_the_note(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    site = tmp_path / "site-packages"
    (site / "pytest").mkdir(parents=True)
    monkeypatch.setattr("raiker.execution.commands.missing_module.user_site_folders", lambda home=None: [site])
    failed = _with_module_note("Shell command exit 1.", {"returncode": 1, "stderr": FAILURE, "stdout": ""})
    assert failed.startswith("Shell command exit 1. The sandbox could not import pytest")
    passed = _with_module_note("Shell command exit 0.", {"returncode": 0, "stderr": FAILURE, "stdout": ""})
    assert passed == "Shell command exit 0."
