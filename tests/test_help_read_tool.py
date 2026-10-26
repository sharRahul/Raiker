"""TOOL-46 — a turn reads Raiker's own help articles."""

from __future__ import annotations

from raiker.models.tool_call_validation import default_tool_specs, risk_for_tool
from raiker.runtime.turn_sources import source_from_tool_result
from raiker.tools.help_tools import help_read


def test_no_arguments_lists_the_articles() -> None:
    result = help_read()
    assert result["status"] == "success"
    slugs = [article["slug"] for article in result["articles"]]
    assert slugs[0] == "getting-started"
    assert "connecting-a-model" in slugs


def test_a_slug_reads_one_article_and_an_unknown_one_names_the_list() -> None:
    article = help_read("connecting-a-model")
    assert article["status"] == "success" and article["text"].startswith("#")
    missing = help_read("no-such-page")
    assert missing["error"]["type"] == "unknown_help_article"
    assert "getting-started" in missing["error"]["articles"]
    # A slug is matched against the listing, never used as a path.
    assert help_read("../README")["error"]["type"] == "unknown_help_article"


def test_a_query_finds_matching_lines() -> None:
    result = help_read(query="approval")
    assert result["matches"], result
    assert all(hit["lines"] for hit in result["matches"])
    assert len(result["matches"]) <= 5


def test_it_is_low_risk_advertised_and_cited() -> None:
    assert risk_for_tool("help_read") == "low"
    specs = {spec.name: spec for spec in default_tool_specs()}
    assert specs["help_read"].parameters["required"] == []
    draft = source_from_tool_result("help_read", {"slug": "memory"}, help_read("memory"))
    assert draft is not None and draft.kind == "help" and draft.title.startswith("Help: ")


def test_an_article_reads_as_its_intro_and_a_list_of_parts() -> None:
    article = help_read("working-in-chat")
    assert "## " not in article["text"], "the intro stops at the first part"
    ids = [item["part"] for item in article["parts"]]
    assert "approvals" in ids
    one = help_read("working-in-chat", part="approvals")
    assert one["text"].startswith("## Approvals") and one["part"] == "approvals"
    assert one["title"] == "Working in Chat › Approvals"
    assert help_read("working-in-chat", part="nope")["error"]["type"] == "unknown_help_part"


def test_a_query_names_the_part_it_matched_and_the_chip_opens_it() -> None:
    result = help_read(query="approvals")
    assert all(hit["part"] for hit in result["matches"])
    one = help_read("working-in-chat", part="approvals")
    draft = source_from_tool_result("help_read", {"slug": "working-in-chat", "part": "approvals"}, one)
    assert draft is not None and draft.locator == "working-in-chat#approvals"
