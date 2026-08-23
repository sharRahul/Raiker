"""BUG-237 — the terminal client's output survives a legacy Windows code page.

Raiker's command output is full of characters cp1252 does not have: an em dash
between a label and its value, a middle dot between counts, and the empty-set
sign `/checkpoints restore` prints for a file with no pre-image. On Windows,
`sys.stdout` falls back to the ANSI code page when the console is not UTF-8 or
when output is redirected, so `raiker … > out.txt` died with
`UnicodeEncodeError` **mid-print** on a command that works interactively.

Found while exercising the terminal half of BUG-230's fix.
"""

from __future__ import annotations

import io
import sys

from raiker.cli.main import _use_utf8_output


def test_a_cp1252_stdout_is_reconfigured_to_utf8() -> None:
    original_out, original_err = sys.stdout, sys.stderr
    try:
        sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
        sys.stderr = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")

        _use_utf8_output()

        assert sys.stdout.encoding.lower() in {"utf-8", "utf8"}
        assert sys.stderr.encoding.lower() in {"utf-8", "utf8"}
        # The characters the CLI actually prints, on the stream that used to
        # refuse them.
        print("— · ∅ →")
    finally:
        sys.stdout, sys.stderr = original_out, original_err


def test_a_stream_that_cannot_be_reconfigured_is_left_alone() -> None:
    """A detached or non-text stream must not take the command down with it."""

    class Unreconfigurable:
        encoding = "cp1252"

        def reconfigure(self, **_kwargs: object) -> None:
            raise ValueError("cannot reconfigure")

    original_out, original_err = sys.stdout, sys.stderr
    try:
        sentinel = Unreconfigurable()
        sys.stdout = sentinel  # type: ignore[assignment]
        sys.stderr = sentinel  # type: ignore[assignment]

        _use_utf8_output()  # must not raise

        assert sys.stdout is sentinel
    finally:
        sys.stdout, sys.stderr = original_out, original_err


def test_the_restore_preview_prints_the_characters_that_broke_it() -> None:
    """The exact string `_short_sha` produces for an absent pre-image."""
    from raiker.cli.commands import _short_sha

    assert _short_sha(None) == "∅"
    assert _short_sha("a" * 64) == "a" * 12
