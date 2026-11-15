"""A deferred tool the owner's request names is carried from the first call."""

from __future__ import annotations

from raiker.models.tool_projection import (
    ALWAYS_PROJECTED,
    DEFERRABLE_TOOL_NAMES,
    PRESELECT_LIMIT,
    preselect_for_prompt,
)


def test_a_request_that_names_a_deferred_tool_reveals_it() -> None:
    assert "git_commit" in preselect_for_prompt("Commit my changes to the branch")
    assert preselect_for_prompt("read my gmail") == ("gmail_read",)
    assert preselect_for_prompt("show the document symbols in main.py") == ("document_symbols",)


def test_a_request_that_names_no_tool_reveals_nothing() -> None:
    for prompt in ("hello", "what is the weather in Paris", "", "   ", "check my calendar for today"):
        assert preselect_for_prompt(prompt) == ()


def test_a_shared_name_word_alone_reveals_nothing() -> None:
    # "git" and "read" are in many tool names and say nothing about which one.
    assert preselect_for_prompt("git") == ()
    assert preselect_for_prompt("read it") == ()


def test_only_deferred_tools_and_never_more_than_the_limit() -> None:
    picked = preselect_for_prompt(
        "commit push branch clone fetch log the diff files, read gmail slack outlook and github"
    )
    assert len(picked) <= PRESELECT_LIMIT
    assert set(picked) <= DEFERRABLE_TOOL_NAMES
    assert not set(picked) & ALWAYS_PROJECTED
