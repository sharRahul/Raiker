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


def test_a_short_title_found_by_meaning_only_when_it_stands_out() -> None:
    # Scores as measured with nomic-embed-text for "Japan holiday" (2026-11-19).
    scores = {"a": 0.586, "b": 0.43, "c": 0.48}

    def embed(text: str) -> list[float] | None:
        if text == "Japan holiday":
            return [1.0, 0.0]
        item = next(key for key, value in {"a": "Kyoto", "b": "revenue", "c": "bicycle"}.items() if value in text)
        import math

        score = scores[item]
        return [score, math.sqrt(1 - score * score)]

    found = search_library(ITEMS, "Japan holiday", embed=embed)
    assert [item["item_id"] for item in found] == ["a"]

    # In a field of four or more where nothing stands out, nothing is offered.
    scores.update({"a": 0.53, "b": 0.52, "c": 0.525})
    field = ITEMS + [{**ITEMS[1], "item_id": "b2"}]
    assert search_library(field, "Japan holiday", embed=embed) == []


def test_a_small_library_is_judged_by_the_floor_alone() -> None:
    def embed(text: str) -> list[float] | None:
        return [1.0, 0.0] if text == "Japan holiday" else [0.586, 0.81]

    two = ITEMS[:1] + [{**ITEMS[0], "item_id": "a2"}]
    assert [item["item_id"] for item in search_library(two, "Japan holiday", embed=embed)] == ["a", "a2"]
