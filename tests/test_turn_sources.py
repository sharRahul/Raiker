"""C6 and C4 — where a turn's answer came from, and opening it at the passage used.

Chat could read an email, a page or an attached document and then answer as if
it had simply known. These tests hold the ledger that ends that to the four
properties the feature is worth nothing without:

**Derived, never asserted.** A source exists because a governed call really
returned material or because the owner attached a file. A failed call, an
unmapped tool and a model that writes `[s9]` all produce nothing.

**Owner-scoped.** Another account reading the same conversation id sees no
sources and can open no passage — the row is keyed by the owner principal, so
the scope is the query rather than a check somebody has to remember.

**Content stays out of the event log.** The streamed record is counts, ids,
kinds and tool names. Titles and passages are content and are served only over
the session-authorized read route.

**Every unopenable source says why.** A changed file, a deleted one and material
Raiker holds no second copy of each resolve to their own named status rather
than to an empty pane or a plausible-looking guess.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.runtime.turn_sources import (
    MAX_SOURCES_PER_TURN,
    SourceDraft,
    TurnSource,
    attachment_sources,
    citation_prompt,
    load_source,
    load_sources,
    locate_answer_quote,
    record_sources,
    resolve_source_excerpt,
    source_from_tool_result,
)
from raiker.storage.sqlite import SQLiteStore

_OWNER = "principal_owner"
_OTHER = "principal_intruder"
_SESSION = "sess_sources"
_TURN = "turn_1"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "sources_ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def store(workspace: Path) -> SQLiteStore:
    return SQLiteStore(workspace)


def _record(
    store: SQLiteStore, *drafts: SourceDraft, principal_id: str = _OWNER
) -> list[TurnSource]:
    return record_sources(
        store,
        session_id=_SESSION,
        turn_id=_TURN,
        principal_id=principal_id,
        drafts=list(drafts),
        starting_ordinal=store.count_turn_sources(_SESSION, _TURN, principal_id),
    )


# ── deriving a source from what really ran ───────────────────────────────────


class TestSourceDerivation:
    def test_a_read_file_result_becomes_a_file_source(self) -> None:
        draft = source_from_tool_result(
            "read_file",
            {"path": "docs/plan.md"},
            {"status": "success", "path": "docs/plan.md", "text": "hello", "truncated": False},
        )
        assert draft is not None
        assert (draft.kind, draft.title, draft.locator) == ("file", "docs/plan.md", "docs/plan.md")
        assert draft.passage == "hello"

    def test_a_fetched_page_carries_its_final_url(self) -> None:
        draft = source_from_tool_result(
            "web_fetch",
            {"url": "https://example.test/a"},
            {
                "status": "success",
                "url": "https://example.test/a",
                "final_url": "https://example.test/b",
                "title": "Example",
                "content": "Web page content (untrusted data):\nbody",
            },
        )
        assert draft is not None
        assert draft.kind == "web"
        assert draft.locator == "https://example.test/b"
        assert "body" in draft.passage

    def test_an_email_is_named_by_its_subject(self) -> None:
        draft = source_from_tool_result(
            "gmail_read",
            {"resource": "message", "message_id": "m1"},
            {"status": "success", "subject": "Renewal", "message_id": "m1", "content": "text"},
        )
        assert draft is not None
        assert (draft.kind, draft.title, draft.locator) == ("email", "Renewal", "m1")

    # MEM-08 — three tools declared a source kind and produced no source, so an
    # answer drawn from them cited nothing at all. The failure mode this
    # codebase keeps finding: two lists that have to agree, with nothing holding
    # them together. The invariant below is the thing holding them.
    def test_every_tool_that_declares_a_source_kind_can_produce_one(self) -> None:
        from raiker.models.tool_registry import TOOL_SOURCE_KIND_BY_TOOL

        # One minimally successful result per declared tool: whatever the shape,
        # a tool that says it produces material must produce a draft.
        outputs: dict[str, tuple[dict[str, object], dict[str, object]]] = {
            "read_file": ({"path": "a.md"}, {"path": "a.md", "text": "x"}),
            "list_directory": ({"path": "."}, {"path": ".", "entries": ["a.md"]}),
            "grep": ({"query": "x"}, {"count": 1, "matches": ["a.md:1"]}),
            "glob": ({"pattern": "*.md"}, {"count": 1, "paths": ["a.md"]}),
            "diff_files": ({"before_path": "a", "after_path": "b"}, {"text": "@@"}),
            "git_status": ({}, {"text": "clean"}),
            "git_diff": ({}, {"text": "@@"}),
            "git_log": ({}, {"text": "commit"}),
            "code_map_search": ({"query": "f"}, {"count": 1, "repository": "repo"}),
            "code_map_references": (
                {"name": "f"},
                {"count": 1, "repository": "repo", "results": [{"path": "a.py", "line": 2, "text": "f()"}]},
            ),
            "memory_search": ({"query": "keys"}, {"count": 1, "results": [{"text": "x"}]}),
            "memory_list": ({}, {"count": 1, "results": [{"text": "x"}]}),
            "memory_get": ({}, {"memory_id": "mem_1", "text": "x"}),
            "knowledge_graph": (
                {"action": "neighbors", "query": "Ada"},
                {"action": "neighbors", "count": 1, "edges": [{"subject": "Ada", "predicate": "knows", "object": "Bo"}]},
            ),
            "conversation_search": (
                {"query": "rotation"},
                {"count": 1, "results": [{"title": "Keys", "created_at": "2026-03-12T00:00:00Z", "text": "monthly"}]},
            ),
            "skill_load": ({"name": "brief"}, {"content": "steps"}),
            "github_read": ({"repo": "o/r", "number": "1"}, {"title": "Issue", "content": "body"}),
            "gmail_read": ({}, {"subject": "Renewal", "message_id": "m1", "content": "text"}),
            "gcal_read": ({}, {"title": "Standup", "event_id": "e1", "content": "text"}),
            "slack_read": ({"channel": "#eng"}, {"content": "text"}),
            "connector_read": ({"connector_id": "c", "operation_id": "o"}, {"content": "text"}),
            "web_fetch": ({"url": "https://e.test"}, {"final_url": "https://e.test", "content": "body"}),
            "web_search": ({"query": "x"}, {"result_count": 2, "results": [{"title": "a"}]}),
            "spawn_subagent": ({"name": "reader"}, {"name": "reader", "steps_executed": 2, "content": "found"}),
        }
        undeclared = sorted(set(TOOL_SOURCE_KIND_BY_TOOL) - set(outputs))
        assert undeclared == [], f"no sample result for declared source tools: {undeclared}"
        for tool, kind in sorted(TOOL_SOURCE_KIND_BY_TOOL.items()):
            args, output = outputs[tool]
            draft = source_from_tool_result(tool, args, {"status": "success", **output})
            assert draft is not None, f"{tool} declares source_kind={kind} and produces no source"
            assert draft.kind == kind
            assert draft.title != ""

    def test_a_recalled_exchange_names_its_conversation_and_its_date(self) -> None:
        # Without the heading, a recalled passage is a paragraph the owner
        # cannot place — which is the whole reason the recall was cited.
        draft = source_from_tool_result(
            "conversation_search",
            {"query": "key rotation"},
            {
                "status": "success",
                "count": 2,
                "results": [
                    {
                        "title": "Key rotation",
                        "created_at": "2026-03-12T09:00:00Z",
                        "session_id": "sess_a",
                        "turn_id": "turn_9",
                        "text": "We settled on monthly.",
                    },
                    {
                        "title": "Ops review",
                        "created_at": "2026-05-01T09:00:00Z",
                        "session_id": "sess_b",
                        "turn_id": "turn_2",
                        "text": "Confirmed monthly.",
                    },
                ],
            },
        )
        assert draft is not None
        assert draft.kind == "conversation"
        assert draft.detail == "2 exchanges"
        assert "Key rotation · 2026-03-12" in draft.passage
        assert "We settled on monthly." in draft.passage

    def test_a_conversation_scoped_recall_names_the_conversation_it_stayed_in(self) -> None:
        draft = source_from_tool_result(
            "conversation_search",
            {"query": "rotation", "session_id": "sess_a"},
            {"status": "success", "count": 1, "results": [{"title": "Key rotation", "text": "x"}]},
        )
        assert draft is not None
        assert draft.locator == "sess_a"

    def test_a_failed_call_produces_no_source(self) -> None:
        # A citation pointing at a call that produced nothing is worse than none.
        assert (
            source_from_tool_result(
                "read_file", {"path": "gone"}, {"status": "failed", "error": {"type": "not_found"}}
            )
            is None
        )

    def test_a_tool_that_reads_nothing_produces_no_source(self) -> None:
        # `update_plan` records intent; `write_file` changes the workspace.
        # Neither is material an answer can have come from.
        assert source_from_tool_result("update_plan", {}, {"status": "success"}) is None
        assert source_from_tool_result("write_file", {}, {"status": "success"}) is None

    def test_a_malformed_result_is_not_a_source(self) -> None:
        assert source_from_tool_result("read_file", {}, None) is None
        assert source_from_tool_result("read_file", {}, {}) is None


class TestAttachmentSources:
    def test_an_included_document_becomes_a_citable_source(self) -> None:
        accepted = attachment_sources([
            {
                "item_id": "item_1",
                "title": "Attachment: uploaded document att_1",
                "content": "Uploaded document: q3.docx\n\nRevenue rose 4%.",
                "metadata": {
                    "attachment_status": "document_uploaded",
                    "attachment_id": "att_1",
                    "filename": "q3.docx",
                },
            }
        ])
        assert len(accepted) == 1
        item_id, draft = accepted[0]
        assert item_id == "item_1"
        assert (draft.kind, draft.title, draft.attachment_id) == ("attachment", "q3.docx", "att_1")

    def test_a_denied_or_dropped_attachment_is_not_citable(self) -> None:
        assert attachment_sources([
            {"item_id": "a", "metadata": {"attachment_status": "denied_outside_workspace"}},
            {"item_id": "b", "metadata": {"attachment_status": "dropped_over_limit"}},
            {"item_id": "c", "metadata": {"attachment_status": "not_found"}},
        ]) == []

    def test_an_image_is_not_citable(self) -> None:
        # Its bytes travel as an image block; its context item is metadata, so
        # there is no passage to open it at.
        assert attachment_sources([
            {"item_id": "i", "metadata": {"attachment_status": "image_attached", "attachment_id": "a"}}
        ]) == []


# ── the ledger itself ────────────────────────────────────────────────────────


class TestLedger:
    def test_ids_are_assigned_in_order_and_continue_across_batches(self, store: SQLiteStore) -> None:
        first = _record(store, SourceDraft(kind="file", title="a.py"))
        second = _record(
            store, SourceDraft(kind="file", title="b.py"), SourceDraft(kind="web", title="page")
        )
        assert [s.source_id for s in first] == ["s1"]
        assert [s.source_id for s in second] == ["s2", "s3"]
        assert [s.source_id for s in load_sources(store, _SESSION, _OWNER, _TURN)] == [
            "s1", "s2", "s3",
        ]

    def test_cite_as_is_the_marker_the_model_is_handed(self, store: SQLiteStore) -> None:
        [source] = _record(store, SourceDraft(kind="file", title="a.py"))
        assert source.cite_as == "[s1]"

    def test_a_turn_cannot_grow_an_unbounded_ledger(self, store: SQLiteStore) -> None:
        recorded = _record(
            store, *[SourceDraft(kind="file", title=f"f{i}") for i in range(MAX_SOURCES_PER_TURN + 10)]
        )
        assert len(recorded) == MAX_SOURCES_PER_TURN

    def test_another_account_sees_no_sources(self, store: SQLiteStore) -> None:
        _record(store, SourceDraft(kind="file", title="secret.py"))
        assert load_sources(store, _SESSION, _OTHER, _TURN) == []
        assert load_source(store, _SESSION, _TURN, "s1", _OTHER) is None

    def test_the_client_view_never_carries_the_passage(self, store: SQLiteStore) -> None:
        [source] = _record(
            store, SourceDraft(kind="web", title="page", passage="secret body text")
        )
        assert "passage" not in source.to_view()
        assert "secret body text" not in str(source.to_view())

    def test_the_citation_instruction_names_the_marker_shape(self) -> None:
        prompt = citation_prompt()
        assert "[s1]" in prompt
        assert "never invent one" in prompt


# ── opening a source at the passage that was used (C4) ───────────────────────


class TestResolution:
    def test_a_workspace_file_is_marked_at_the_passage_the_turn_read(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        target = workspace / "notes.md"
        target.write_text("intro line\nthe renewal is on 14 March\ntail line\n", encoding="utf-8")
        [source] = _record(
            store,
            SourceDraft(
                kind="file", title="notes.md", locator="notes.md", tool_name="read_file",
                passage="the renewal is on 14 March",
            ),
        )
        resolved = resolve_source_excerpt(
            store, workspace_root=workspace, source=source,
            session_id=_SESSION, owner_principal_id=_OWNER,
        )
        assert resolved["status"] == "resolved"
        assert resolved["resolution_method"] == "matching_text"
        start, length = resolved["highlight_start"], resolved["highlight_length"]
        assert resolved["excerpt"][start : start + length] == "the renewal is on 14 March"

    def test_a_file_that_changed_says_so_rather_than_marking_something_near_it(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        target = workspace / "notes.md"
        target.write_text("entirely different content now\n", encoding="utf-8")
        [source] = _record(
            store,
            SourceDraft(
                kind="file", title="notes.md", locator="notes.md", tool_name="read_file",
                passage="the renewal is on 14 March",
            ),
        )
        resolved = resolve_source_excerpt(
            store, workspace_root=workspace, source=source,
            session_id=_SESSION, owner_principal_id=_OWNER,
        )
        assert resolved["status"] == "source_changed"
        assert resolved["highlight_start"] == -1

    def test_a_deleted_file_says_deleted(self, workspace: Path, store: SQLiteStore) -> None:
        [source] = _record(
            store,
            SourceDraft(
                kind="file", title="gone.md", locator="gone.md", tool_name="read_file",
                passage="anything",
            ),
        )
        resolved = resolve_source_excerpt(
            store, workspace_root=workspace, source=source,
            session_id=_SESSION, owner_principal_id=_OWNER,
        )
        assert resolved["status"] == "source_deleted"

    def test_a_whole_file_read_is_shown_without_a_meaningless_highlight(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        target = workspace / "small.md"
        target.write_text("just this\n", encoding="utf-8")
        [source] = _record(
            store,
            SourceDraft(
                kind="file", title="small.md", locator="small.md", tool_name="read_file",
                passage="just this\n",
            ),
        )
        resolved = resolve_source_excerpt(
            store, workspace_root=workspace, source=source,
            session_id=_SESSION, owner_principal_id=_OWNER,
        )
        assert resolved["status"] == "resolved"
        assert resolved["resolution_method"] == "whole_source"

    def test_outside_material_is_shown_as_exactly_what_reached_the_model(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        [source] = _record(
            store,
            SourceDraft(
                kind="web", title="Example", locator="https://example.test/a",
                tool_name="web_fetch", passage="the page said this",
            ),
        )
        resolved = resolve_source_excerpt(
            store, workspace_root=workspace, source=source,
            session_id=_SESSION, owner_principal_id=_OWNER,
        )
        assert resolved["status"] == "resolved"
        assert resolved["resolution_method"] == "recorded_passage"
        assert resolved["excerpt"] == "the page said this"

    def test_a_source_that_kept_nothing_says_so(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        [source] = _record(store, SourceDraft(kind="repository", title="git status"))
        resolved = resolve_source_excerpt(
            store, workspace_root=workspace, source=source,
            session_id=_SESSION, owner_principal_id=_OWNER,
        )
        assert resolved["status"] == "no_provenance"

    def test_a_path_outside_the_workspace_is_refused_rather_than_read(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        [source] = _record(
            store,
            SourceDraft(
                kind="file", title="passwd", locator="../../etc/passwd",
                tool_name="read_file", passage="root",
            ),
        )
        resolved = resolve_source_excerpt(
            store, workspace_root=workspace, source=source,
            session_id=_SESSION, owner_principal_id=_OWNER,
        )
        assert resolved["status"] == "not_authorized"


class TestDeclaredEvent:
    def test_the_streamed_event_type_is_declared(self) -> None:
        # FIXED-97's lesson: an event the runtime emits but does not declare
        # raises inside the streaming turn and kills it with no stated cause.
        from raiker.contracts.models import EVENT_TYPES

        assert "turn_sources_recorded" in EVENT_TYPES


class TestAnswerQuoteLocation:
    """C4 — the sentence carrying a citation is what says *which part* was used.

    Without it, a whole-file read can only open at the whole file. With it, the
    pane opens at the run the answer rests on — and only ever at a run the
    source verbatim contains, so a paraphrase yields no highlight instead of a
    confident mark in the wrong place.
    """

    DOC = (
        "# Meridian\n\nOwner: Facilities.\n\n"
        "The Meridian licence renews on 14 March 2029.\n\n"
        "Renewal is handled by Legal.\n"
    )

    def test_the_citing_sentence_locates_its_own_run(self) -> None:
        start, length = locate_answer_quote(
            self.DOC, "The Meridian licence renews on 14 March 2029 [s1]."
        )
        assert self.DOC[start : start + length] == "The Meridian licence renews on 14 March 2029"

    def test_a_partly_quoting_sentence_matches_on_its_longest_verbatim_fragment(self) -> None:
        start, length = locate_answer_quote(
            self.DOC, "According to the file, the Meridian licence renews on 14 March 2029 [s1]."
        )
        assert self.DOC[start : start + length].lower().endswith("renews on 14 march 2029")

    def test_a_paraphrase_matches_nothing_rather_than_something_near_it(self) -> None:
        assert locate_answer_quote(self.DOC, "It comes up for renewal in a few years [s1].") == (
            -1,
            0,
        )

    def test_a_fragment_too_short_to_mean_anything_is_refused(self) -> None:
        # "Owner" alone is not evidence that a sentence rests on that line.
        assert locate_answer_quote(self.DOC, "Owner [s1].") == (-1, 0)

    def test_an_empty_quote_locates_nothing(self) -> None:
        assert locate_answer_quote(self.DOC, "") == (-1, 0)
        assert locate_answer_quote("", "anything at all in here") == (-1, 0)


class TestQuoteResolution:
    def test_a_whole_file_read_opens_at_the_sentence_the_answer_cited(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        body = "intro\n\nThe Meridian licence renews on 14 March 2029.\n\ntail\n"
        (workspace / "meridian.md").write_text(body, encoding="utf-8")
        [source] = _record(
            store,
            SourceDraft(
                kind="file", title="meridian.md", locator="meridian.md",
                tool_name="read_file", passage=body,
            ),
        )
        resolved = resolve_source_excerpt(
            store, workspace_root=workspace, source=source, session_id=_SESSION,
            owner_principal_id=_OWNER,
            quote="The Meridian licence renews on 14 March 2029 [s1].",
        )
        assert resolved["resolution_method"] == "answer_quote"
        start, length = resolved["highlight_start"], resolved["highlight_length"]
        assert (
            resolved["excerpt"][start : start + length]
            == "The Meridian licence renews on 14 March 2029"
        )

    def test_without_a_quote_the_same_read_says_it_read_the_whole_thing(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        body = "intro\n\nThe Meridian licence renews on 14 March 2029.\n\ntail\n"
        (workspace / "meridian.md").write_text(body, encoding="utf-8")
        [source] = _record(
            store,
            SourceDraft(
                kind="file", title="meridian.md", locator="meridian.md",
                tool_name="read_file", passage=body,
            ),
        )
        resolved = resolve_source_excerpt(
            store, workspace_root=workspace, source=source, session_id=_SESSION,
            owner_principal_id=_OWNER,
        )
        assert resolved["resolution_method"] == "whole_source"
        assert resolved["highlight_start"] == -1


class TestQuoteFormatting:
    """The needle is the model's prose; the haystack is the source, untouched.

    Everything stripped here is the model's own presentation — the citation
    marker, and the emphasis it wraps a figure in. Removing it can only narrow
    what matches, so nothing can ever be marked that the source does not
    literally contain.
    """

    DOC = "Owner: Facilities.\n\nThe Meridian licence renews on 14 March 2029.\n"

    def test_emphasis_around_a_figure_does_not_defeat_the_match(self) -> None:
        start, length = locate_answer_quote(
            self.DOC, "The Meridian licence renews on **14 March 2029** [s1]."
        )
        assert self.DOC[start : start + length] == "The Meridian licence renews on 14 March 2029"


class TestRetention:
    """A conversation's ledger must not outlive the conversation.

    ``turn_sources`` holds recorded passages — real content from the owner's
    files, mail and pages. Deleting a chat and leaving that behind would make
    "delete this conversation" a claim the product does not keep.
    """

    def test_deleting_the_conversation_deletes_its_sources(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        store.create_session(_SESSION, str(workspace))
        store.insert_turn(_SESSION, _TURN, "hello", status="completed")
        _record(store, SourceDraft(kind="web", title="page", passage="secret body text"))
        assert load_sources(store, _SESSION, _OWNER) != []

        assert store.delete_session(_SESSION) is True
        assert load_sources(store, _SESSION, _OWNER) == []

    def test_deleting_the_conversation_also_clears_its_plan_and_controls(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        # Found while adding the ledger: two other session-keyed tables written
        # after this cascade had never been added to it either.
        store.create_session(_SESSION, str(workspace))
        store.save_agent_plan(
            session_id=_SESSION, principal_id=_OWNER, turn_id=_TURN,
            steps_json='[{"title": "step", "status": "pending"}]',
        )
        store.request_turn_stop(_SESSION, _OWNER, reason="stop")
        assert store.load_agent_plan(_SESSION, _OWNER) is not None

        assert store.delete_session(_SESSION) is True
        assert store.load_agent_plan(_SESSION, _OWNER) is None
