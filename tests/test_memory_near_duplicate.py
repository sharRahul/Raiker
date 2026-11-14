# SPDX-License-Identifier: Apache-2.0
"""FIXED-1439 — a proposal that repeats an approved memory says so."""

from __future__ import annotations

from raiker.memory.near_duplicate import THRESHOLD, nearest_approved, similarity


def test_the_same_fact_in_other_words_is_a_near_duplicate() -> None:
    assert similarity("The owner prefers short replies.", "User prefers short replies") >= THRESHOLD


def test_a_different_fact_is_not() -> None:
    assert similarity("Anna prefers short replies.", "Anna lives in Lisbon.") < THRESHOLD


def test_the_nearest_approved_memory_is_named() -> None:
    approved = [
        {"memory_id": "mem_1", "text": "Anna lives in Lisbon."},
        {"memory_id": "mem_2", "text": "The owner prefers short replies."},
    ]
    found = nearest_approved("User prefers short replies", approved)
    assert found is not None
    assert found["memory_id"] == "mem_2"
    assert 0.0 < found["similarity"] <= 1.0


def test_nothing_close_is_none() -> None:
    assert nearest_approved("Meeting moved to Friday", [{"memory_id": "m", "text": "Likes tea"}]) is None


def test_empty_text_is_never_a_duplicate() -> None:
    assert nearest_approved("", [{"memory_id": "m", "text": ""}]) is None
