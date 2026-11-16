"""A command whose program is missing says so, with the installed alternative (2026-11-16)."""

from __future__ import annotations

from unittest import mock

from raiker.runtime.executors.tier2_shell import missing_program_hint


def test_python_points_to_python3_when_only_that_is_installed() -> None:
    with mock.patch("shutil.which", side_effect=lambda name: "/usr/bin/python3" if name == "python3" else None):
        hint = missing_program_hint("python")
    assert "`python` is not installed" in hint and "`python3` is installed" in hint


def test_an_unknown_program_is_named_without_a_guess() -> None:
    with mock.patch("shutil.which", return_value=None):
        assert missing_program_hint("/usr/bin/frobnicate") == (
            "The program `frobnicate` is not installed on this computer, so the command did not run."
        )
