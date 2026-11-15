"""Library search: by words, then by meaning where the owner's embedder may run."""

from __future__ import annotations

from typing import Any

from raiker.control.library import LibraryItem, search_library


def _item(item_id: str, title: str, detail: str = "Image") -> LibraryItem:
    return {
        "item_id": item_id, "kind": "image", "title": title, "detail": detail,
        "created_at": "2026-11-18T10:00:00Z", "project_id": None, "project_name": None,
        "session_id": None, "session_title": None, "turn_id": None, "href": "#/design",
        "external": False, "download_url": None, "block": None, "pin_id": None,
    }


ITEMS = [
    _item("a", "Poster for the Kyoto flights"),
    _item("b", "Quarterly revenue chart", "Chart"),
    _item("c", "A red bicycle on a beach"),
]


def _embedder(topics: dict[str, list[float]]) -> Any:
    def embed(text: str) -> list[float] | None:
        lowered = text.lower()
        for word, vector in topics.items():
            if word in lowered:
                return vector
        return [0.0, 0.0, 1.0]
    return embed


def test_every_word_must_match_and_the_match_is_marked() -> None:
    found = search_library(ITEMS, "revenue CHART")
    assert [item["item_id"] for item in found] == ["b"]
    assert found[0]["match_kind"] == "words"
    assert search_library(ITEMS, "revenue bicycle") == []


def test_an_empty_query_returns_everything_unmarked() -> None:
    assert search_library(ITEMS, "  ") == ITEMS
    assert "match_kind" not in search_library(ITEMS, "")[0]


def test_meaning_adds_items_about_the_query_in_other_words() -> None:
    embed = _embedder({"japan": [1.0, 0.0, 0.0], "kyoto": [0.95, 0.05, 0.0]})
    found = search_library(ITEMS, "Japan holiday", embed=embed)
    assert [(item["item_id"], item["match_kind"]) for item in found] == [("a", "meaning")]


def test_without_an_allowed_embedder_only_words_answer() -> None:
    assert search_library(ITEMS, "Japan holiday", embed=None) == []


def test_a_failing_embedder_leaves_the_word_matches() -> None:
    def broken(_text: str) -> list[float] | None:
        raise RuntimeError("backend down")

    found = search_library(ITEMS, "bicycle", embed=broken)
    assert [item["item_id"] for item in found] == ["c"]
