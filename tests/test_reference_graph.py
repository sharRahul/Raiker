"""MEM-14 — the citation ledger, read as a graph a model can walk.

Raiker recorded every source a turn used, with the passage that reached the
model, and read that table exactly one way: forwards, for the chips under one
answer. Which meant a model could not ask the two questions a reference graph
exists to answer — *what else used this?* and *what does this actually say?* —
about material its own workspace had already read.

The shape borrowed here is Obsidian's metadata cache, whose useful properties
turned out to be three claims rather than a data structure: a link carries a
count, an unresolved link is reported rather than dropped, and a reference
resolves to a passage rather than to a document. Each is asserted below against
the case that makes it matter.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from raiker.contracts.ids import utc_now
from raiker.contracts.models import User
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.graph_tools import knowledge_graph

OWNER = "prin_owner"
OTHER = "prin_someone_else"
USER = "usr_owner"


@pytest.fixture()
def store(tmp_path: Path) -> SQLiteStore:
    built = SQLiteStore(tmp_path)
    now = utc_now()
    built.insert_user(User(USER, "Owner", None, True, now, now))
    return built


def _cite(
    store: SQLiteStore,
    session_id: str,
    turn_id: str,
    *,
    locator: str,
    passage: str = "",
    kind: str = "file",
    tool_name: str = "read_file",
    title: str = "",
    principal_id: str = OWNER,
    ordinal: int = 0,
    origin: str = "chat",
    session_title: str = "Work",
) -> None:
    """One recorded citation, through the same writer the runtime uses."""
    if store.load_session(session_id) is None:
        store.create_session(
            session_id, "/w", title=session_title, user_id=USER, origin=origin
        )
    store.record_turn_sources(
        session_id=session_id,
        turn_id=turn_id,
        principal_id=principal_id,
        rows=[
            {
                "source_id": f"s{ordinal + 1}",
                "ordinal": ordinal,
                "kind": kind,
                "title": title or locator,
                "locator": locator,
                "tool_name": tool_name,
                "detail": "",
                "attachment_id": "",
                "passage": passage,
            }
        ],
    )


# ── backlinks: who used this, and how much ───────────────────────────────────


def test_a_file_names_the_conversations_that_used_it(store: SQLiteStore, tmp_path: Path) -> None:
    """The question the ledger could answer and no one could ask."""
    _cite(store, "sess_a", "t1", locator="docs/runbook.md", session_title="Restore drill")
    _cite(store, "sess_b", "t1", locator="docs/runbook.md", session_title="Ship the parser",
          origin="build")

    answer = knowledge_graph(
        tmp_path, "references", locator="docs/runbook.md", owner_principal_id=OWNER
    )

    assert answer["status"] == "success"
    assert {b["session_id"] for b in answer["backlinks"]} == {"sess_a", "sess_b"}
    surfaces = {b["session_id"]: b["surface"] for b in answer["backlinks"]}
    # Which *kind* of work used it, not just that some did.
    assert surfaces == {"sess_a": "chat", "sess_b": "build"}
    titles = {b["session_title"] for b in answer["backlinks"]}
    assert titles == {"Restore drill", "Ship the parser"}


def test_nine_references_and_one_are_different_facts(store: SQLiteStore, tmp_path: Path) -> None:
    """Obsidian counts references per backlink; the reason is this case.

    A conversation that leaned on a file across nine turns and one that glanced
    at it once are both "a backlink", and collapsing them would throw away the
    only signal that says which of the two matters.
    """
    for turn in range(9):
        _cite(store, "sess_heavy", f"t{turn}", locator="docs/runbook.md")
    _cite(store, "sess_light", "t1", locator="docs/runbook.md")

    answer = knowledge_graph(
        tmp_path, "references", locator="docs/runbook.md", owner_principal_id=OWNER
    )

    counts = {b["session_id"]: b["refs"] for b in answer["backlinks"]}
    assert counts == {"sess_heavy": 9, "sess_light": 1}
    # And ordered by weight, because a model reads the top of a list.
    assert answer["backlinks"][0]["session_id"] == "sess_heavy"


def test_another_accounts_citations_are_not_visible(store: SQLiteStore, tmp_path: Path) -> None:
    _cite(store, "sess_mine", "t1", locator="docs/runbook.md")
    _cite(store, "sess_theirs", "t1", locator="docs/runbook.md", principal_id=OTHER)

    answer = knowledge_graph(
        tmp_path, "references", locator="docs/runbook.md", owner_principal_id=OWNER
    )

    assert [b["session_id"] for b in answer["backlinks"]] == ["sess_mine"]


# ── co-citation: what was used alongside it ──────────────────────────────────


def test_what_was_used_alongside_it_is_reported_with_its_evidence(
    store: SQLiteStore, tmp_path: Path
) -> None:
    """The edge a graph view draws, and the honest weakening of it.

    Nobody authored these links. Two files used to answer one question are
    related only in the sense that some work needed both — so the count of
    conversations behind the edge travels with it rather than being hidden
    behind a line on a picture.
    """
    for session in ("sess_a", "sess_b"):
        _cite(store, session, "t1", locator="docs/runbook.md", ordinal=0)
        _cite(store, session, "t1", locator="docs/deploy.md", ordinal=1)
    _cite(store, "sess_c", "t1", locator="docs/runbook.md", ordinal=0)
    _cite(store, "sess_c", "t1", locator="docs/alerts.yaml", ordinal=1)

    answer = knowledge_graph(
        tmp_path, "references", locator="docs/runbook.md", owner_principal_id=OWNER
    )

    related = {r["locator"]: r["shared_sessions"] for r in answer["related"]}
    assert related == {"docs/deploy.md": 2, "docs/alerts.yaml": 1}
    # Strongest edge first: two conversations needing both beats one.
    assert answer["related"][0]["locator"] == "docs/deploy.md"
    # And the anchor never lists itself.
    assert "docs/runbook.md" not in related


# ── outgoing links: what one piece of work rested on ─────────────────────────


def test_a_conversation_lists_what_it_rested_on(store: SQLiteStore, tmp_path: Path) -> None:
    _cite(store, "sess_a", "t1", locator="docs/runbook.md", ordinal=0)
    _cite(store, "sess_a", "t2", locator="docs/runbook.md", ordinal=0)
    _cite(store, "sess_a", "t2", locator="https://example.test/status", ordinal=1,
          kind="web", tool_name="web_fetch")

    answer = knowledge_graph(
        tmp_path, "references", session_id="sess_a", owner_principal_id=OWNER
    )

    assert answer["anchor"] == {"kind": "session", "session_id": "sess_a"}
    outbound = {row["locator"]: row for row in answer["outbound"]}
    assert outbound["docs/runbook.md"]["refs"] == 2
    assert outbound["docs/runbook.md"]["turns"] == 2
    assert outbound["https://example.test/status"]["refs"] == 1


def test_a_citation_with_nothing_to_point_at_is_left_out_of_the_count_too(
    store: SQLiteStore, tmp_path: Path
) -> None:
    """A web *search* is a real citation with no target.

    It belongs under the answer that used it and not in a reference graph, which
    is a graph of things one can point at. The interesting half is the count: a
    `count` computed before the filter would promise more rows than the caller
    receives.
    """
    _cite(store, "sess_a", "t1", locator="docs/runbook.md", ordinal=0)
    _cite(store, "sess_a", "t1", locator="", kind="web", tool_name="web_search",
          title="Web search: restores", ordinal=1)

    answer = knowledge_graph(
        tmp_path, "references", session_id="sess_a", owner_principal_id=OWNER
    )

    assert answer["count"] == 1
    assert len(answer["outbound"]) == 1


# ── resolution: the unresolved half, kept ────────────────────────────────────


def test_a_reference_to_a_deleted_file_is_reported_not_dropped(
    store: SQLiteStore, tmp_path: Path
) -> None:
    """`unresolvedLinks` is half of Obsidian's cache, and the useful half here.

    "The answer rested on something that is now gone" is a more valuable fact
    than a shorter list, and silently omitting the row would leave a model
    concluding the work had no basis rather than a missing one.
    """
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "kept.md").write_text("still here", encoding="utf-8")
    _cite(store, "sess_a", "t1", locator="docs/kept.md", ordinal=0)
    _cite(store, "sess_a", "t1", locator="docs/deleted.md", ordinal=1)

    answer = knowledge_graph(
        tmp_path, "references", session_id="sess_a", owner_principal_id=OWNER
    )

    status = {row["locator"]: row["resolution"] for row in answer["outbound"]}
    assert status == {"docs/kept.md": "resolved", "docs/deleted.md": "unresolved"}


def test_a_web_page_is_external_rather_than_missing(store: SQLiteStore, tmp_path: Path) -> None:
    """Raiker never held the page, so its absence from disk says nothing."""
    _cite(store, "sess_a", "t1", locator="https://example.test/status", kind="web",
          tool_name="web_fetch")

    answer = knowledge_graph(
        tmp_path, "references", session_id="sess_a", owner_principal_id=OWNER
    )

    assert answer["outbound"][0]["resolution"] == "external"


def test_a_repository_read_is_not_mistaken_for_a_missing_file(
    store: SQLiteStore, tmp_path: Path
) -> None:
    """`git_status` records kind `repository` with the tool's own name as locator.

    Testing that for a file on disk would report a deleted document on every
    single repository read — which is why resolution is gated on the tool, not
    on the kind alone.
    """
    _cite(store, "sess_a", "t1", locator="git_status", kind="repository",
          tool_name="git_status")

    answer = knowledge_graph(
        tmp_path, "references", session_id="sess_a", owner_principal_id=OWNER
    )

    assert answer["outbound"][0]["resolution"] == "external"


# ── passages: the text, which is the point ───────────────────────────────────


def test_the_model_can_read_what_a_reference_says(store: SQLiteStore, tmp_path: Path) -> None:
    """A backlink without a passage is a rumour.

    This is the half that makes the graph usable for building an understanding
    rather than a citation footer: the model gets the sentence, not a promise
    that one exists.
    """
    _cite(
        store, "sess_a", "t1", locator="docs/runbook.md",
        passage="Restores are verified against the encrypted NAS target.",
    )

    answer = knowledge_graph(
        tmp_path, "passages", locator="docs/runbook.md", owner_principal_id=OWNER
    )

    assert answer["count"] == 1
    passage = answer["passages"][0]
    assert "encrypted NAS target" in passage["text"]
    assert passage["session_id"] == "sess_a"
    assert passage["turn_id"] == "t1"
    # Where it came from travels with it, so the model can open the source.
    assert passage["tool_name"] == "read_file"


def test_a_passage_is_dated_and_says_it_is_a_snapshot(
    store: SQLiteStore, tmp_path: Path
) -> None:
    """The stored copy is what reached a turn *then*, not what the file says now.

    Left unsaid, a model would quote a year-old passage as the current contents
    of a file it never opened.
    """
    _cite(store, "sess_a", "t1", locator="docs/runbook.md", passage="Old wording.")

    answer = knowledge_graph(
        tmp_path, "passages", locator="docs/runbook.md", owner_principal_id=OWNER
    )

    assert answer["passages"][0]["captured_at"]
    assert "as it was then" in answer["note"]
    assert answer["trust_label"] == "untrusted_source_data"


def test_passages_are_bounded_and_say_when_they_were_cut(
    store: SQLiteStore, tmp_path: Path
) -> None:
    from raiker.tools.graph_tools import MAX_PASSAGE_CHARS, MAX_PASSAGES

    long_text = "x" * (MAX_PASSAGE_CHARS + 500)
    for turn in range(MAX_PASSAGES + 4):
        _cite(store, "sess_a", f"t{turn}", locator="docs/runbook.md", passage=long_text)

    answer = knowledge_graph(
        tmp_path, "passages", locator="docs/runbook.md", max_results=50,
        owner_principal_id=OWNER,
    )

    assert answer["count"] == MAX_PASSAGES
    assert len(answer["passages"][0]["text"]) == MAX_PASSAGE_CHARS
    assert answer["passages"][0]["truncated"] is True


def test_a_source_with_no_stored_text_answers_empty_rather_than_guessing(
    store: SQLiteStore, tmp_path: Path
) -> None:
    _cite(store, "sess_a", "t1", locator="docs/runbook.md", passage="")

    answer = knowledge_graph(
        tmp_path, "passages", locator="docs/runbook.md", owner_principal_id=OWNER
    )

    assert answer["status"] == "success"
    assert answer["passages"] == []


def test_another_accounts_passages_are_not_readable(store: SQLiteStore, tmp_path: Path) -> None:
    """The one that would be a disclosure rather than a wrong answer."""
    _cite(store, "sess_theirs", "t1", locator="docs/runbook.md",
          passage="Their private note.", principal_id=OTHER)

    answer = knowledge_graph(
        tmp_path, "passages", locator="docs/runbook.md", owner_principal_id=OWNER
    )

    assert answer["passages"] == []


# ── refusals ─────────────────────────────────────────────────────────────────


def test_a_reference_read_with_no_anchor_is_a_named_refusal(tmp_path: Path) -> None:
    assert knowledge_graph(tmp_path, "references")["error"]["type"] == "missing_anchor"
    assert knowledge_graph(tmp_path, "passages")["error"]["type"] == "missing_anchor"


def test_the_unknown_action_message_names_every_action(tmp_path: Path) -> None:
    """A model that mistypes an action should learn the whole surface from the error."""
    message = knowledge_graph(tmp_path, "delete")["error"]["message"]
    for action in ("entities", "neighbors", "references", "passages"):
        assert action in message


def test_the_flow_a_model_would_actually_take(store: SQLiteStore, tmp_path: Path) -> None:
    """Discovery to text in three calls, with nothing invented in between.

    This is the claim the whole change rests on: a model that has seen one file
    mentioned can reach the material of the work around it without opening a
    single new source.
    """
    _cite(store, "sess_a", "t1", locator="docs/runbook.md", ordinal=0,
          passage="Restores are verified against the encrypted NAS target.")
    _cite(store, "sess_a", "t1", locator="docs/deploy.md", ordinal=1,
          passage="Deploys pause while a restore drill is running.")

    who = knowledge_graph(
        tmp_path, "references", locator="docs/runbook.md", owner_principal_id=OWNER
    )
    neighbour = who["related"][0]["locator"]
    assert neighbour == "docs/deploy.md"

    text = knowledge_graph(
        tmp_path, "passages", locator=neighbour, owner_principal_id=OWNER
    )
    assert "Deploys pause" in text["passages"][0]["text"]
