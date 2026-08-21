"""BUG-218 — the Knowledge Map is a map of the owner's work, not of the runtime's.

Measured before this change, on a workspace after a single live round: **20 of
22 nodes were typed `tool`**, and not one of them was a tool. They were one node
per row of the event index — "turn started", "model request completed" — because
the map was built from `list_event_index(limit=250)` and typed every row `tool`.

Underneath that flood, four things an owner would expect to see were simply
never read: which sessions were Chat and which were Build, the projects work
belongs to, the files and pages an answer was grounded in, and the files the
owner attached.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path

import pytest

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import ToolAction, User
from raiker.control.dashboard import DashboardService
from raiker.memory.entity_extraction import propose_memory_relationships
from raiker.memory.store import MemoryGovernance, write_memory
from raiker.storage.sqlite import SQLiteStore

OWNER = "prin_owner"
USER = "usr_owner"


@pytest.fixture()
def service(tmp_path: Path) -> DashboardService:
    built = DashboardService(tmp_path)
    now = utc_now()
    # `sessions.user_id` is a real foreign key, so the owner has to exist before
    # any session can.
    built.store.insert_user(User(USER, "Owner", None, True, now, now))
    return built


def _session(store: SQLiteStore, session_id: str, title: str, origin: str) -> None:
    store.create_session(session_id, "/w", title=title, user_id=USER, origin=origin)


def _tool_action(store: SQLiteStore, session_id: str, tool: str, status: str = "completed") -> None:
    store.insert_tool_action(
        ToolAction(
            action_id=new_id("act_"),
            tool_name=tool,
            arguments={},
            risk_level="low",
            requires_approval=False,
            proposed_by="agent",
        ),
        session_id,
        None,
        status,
        owner_principal_id=OWNER,
    )


def _types(view: object) -> Counter[str]:
    return Counter(node.node_type for node in view.nodes)  # type: ignore[attr-defined]


def _labels(view: object, node_type: str) -> set[str]:
    return {n.label for n in view.nodes if n.node_type == node_type}  # type: ignore[attr-defined]


def test_a_busy_session_draws_one_node_per_tool_not_one_per_event(
    service: DashboardService,
) -> None:
    """The defect, stated as the number it produced.

    Forty runs of one tool used to be forty nodes — or rather, forty *events*
    were forty nodes labelled with event names. One tool used forty times is one
    node that says forty.
    """
    _session(service.store, "sess_build", "Ship the parser", "build")
    for _ in range(40):
        _tool_action(service.store, "sess_build", "read_file")
    for _ in range(3):
        _tool_action(service.store, "sess_build", "write_file")

    view = service.brain_view(principal_id=OWNER, user_id=USER)

    assert _types(view)["tool"] == 2, "one node per tool, not per invocation"
    read = next(n for n in view.nodes if n.label == "Read file")
    assert read.detail == "40 uses"
    assert read.status == "used"


def test_a_failing_tool_says_so(service: DashboardService) -> None:
    _session(service.store, "sess_1", "Chat", "chat")
    _tool_action(service.store, "sess_1", "web_fetch", status="failed")
    view = service.brain_view(principal_id=OWNER, user_id=USER)
    node = next(n for n in view.nodes if n.label == "Fetch page")
    assert node.status == "failed"
    assert "failed" in (node.detail or "")


def test_reviewed_memory_relationship_draws_entities_and_evidence(
    service: DashboardService, tmp_path: Path
) -> None:
    memory = write_memory(
        "Rahul works on Raiker.",
        workspace_root=tmp_path,
        store=service.store,
        owner_principal_id=OWNER,
        governance=MemoryGovernance(
            "evt_graph_relation", "", None, "test", 0.9, 0.9,
            "until_forget", "approved", OWNER,
        ),
    )
    propose_memory_relationships(service.store, memory.memory_id, OWNER)
    candidate = service.store.list_memory_relationship_candidates(OWNER)[0]
    service.store.resolve_memory_relationship_candidate_atomic(
        str(candidate["candidate_id"]),
        owner_principal_id=OWNER,
        decision="approved",
        reviewer_id=OWNER,
    )

    view = service.brain_view(principal_id=OWNER, user_id=USER)

    assert _labels(view, "entity") == {"Rahul", "Raiker"}
    relationships = {(edge.relationship, edge.source, edge.target) for edge in view.edges}
    assert any(value[0] == "works_on" for value in relationships)
    assert any(value[0] == "evidence_for" for value in relationships)


def test_chat_and_build_are_different_nodes(service: DashboardService) -> None:
    """They were the same green dot, and the store already knew which was which."""
    _session(service.store, "sess_chat", "Ask about backups", "chat")
    _session(service.store, "sess_build", "Ship the parser", "build")

    view = service.brain_view(principal_id=OWNER, user_id=USER)
    types = _types(view)

    assert types["conversation"] == 1
    assert types["build"] == 1
    assert types["session"] == 0, "neither should fall back to the generic type"
    assert _labels(view, "build") == {"Ship the parser"}


def test_an_unknown_origin_still_draws_rather_than_disappearing(
    service: DashboardService,
) -> None:
    """A surface the map has not been taught about must not vanish from it."""
    _session(service.store, "sess_x", "From somewhere new", "some_future_surface")
    view = service.brain_view(principal_id=OWNER, user_id=USER)
    assert _types(view)["session"] == 1


def test_sessions_hang_from_their_project(service: DashboardService) -> None:
    """`project` had a colour defined and was never emitted."""
    project_id = new_id("proj_")
    service.store.create_project(project_id, "Alpha", "alpha", owner_user_id=USER)
    _session(service.store, "sess_p", "Scoped work", "chat")
    service.store.set_session_project("sess_p", project_id)

    view = service.brain_view(principal_id=OWNER, user_id=USER)

    assert _types(view)["project"] == 1
    assert any(
        edge.source == f"project:{project_id}" and edge.target == "session:sess_p"
        for edge in view.edges
    ), "the session must hang from its project, not from the principal"


def test_the_map_shows_what_an_answer_was_grounded_in(service: DashboardService) -> None:
    """`turn_sources` is the citation record and the map never read it.

    A file cited in two sessions is **one** node with two edges — the shared
    dependency is the relationship a map exists to reveal.
    """
    for session_id in ("sess_a", "sess_b"):
        _session(service.store, session_id, f"Work {session_id}", "chat")
        service.store.insert_turn(session_id, f"turn_{session_id}", "What does it say?")
        service.store.record_turn_sources(
            session_id=session_id,
            turn_id=f"turn_{session_id}",
            principal_id=OWNER,
            rows=[
                {
                    "source_id": f"src_{session_id}",
                    "ordinal": 0,
                    "kind": "file",
                    "title": "runbook.md",
                    "locator": "docs/runbook.md",
                    "tool_name": "read_file",
                    "detail": "",
                    "attachment_id": "",
                    "passage": "",
                }
            ],
        )

    view = service.brain_view(principal_id=OWNER, user_id=USER)

    cited = [n for n in view.nodes if n.node_id.startswith("context:")]
    assert len(cited) == 1, "the same file cited twice is one node"
    assert cited[0].node_type == "file", "a cited file should look like a file"
    assert cited[0].label == "runbook.md"
    grounded = [e for e in view.edges if e.target == cited[0].node_id]
    assert {e.source for e in grounded} == {"session:sess_a", "session:sess_b"}


def test_a_citation_whose_file_is_gone_says_so_rather_than_vanishing(
    service: DashboardService,
) -> None:
    """MEM-14 — the unresolved half of the reference graph, on the map.

    Dropping the node would leave the conversation looking as though it were
    grounded in nothing, when what actually happened is that it was grounded in
    something since deleted. That is a different fact and the more useful one.
    """
    (service.workspace_root / "docs").mkdir(parents=True, exist_ok=True)
    (service.workspace_root / "docs" / "kept.md").write_text("here", encoding="utf-8")
    _session(service.store, "sess_r", "Restore drill", "chat")
    service.store.insert_turn("sess_r", "turn_r", "What does it say?")
    service.store.record_turn_sources(
        session_id="sess_r",
        turn_id="turn_r",
        principal_id=OWNER,
        rows=[
            {
                "source_id": f"s{ordinal + 1}", "ordinal": ordinal, "kind": "file",
                "title": path, "locator": path, "tool_name": "read_file",
                "detail": "", "attachment_id": "", "passage": "",
            }
            for ordinal, path in enumerate(["docs/kept.md", "docs/deleted.md"])
        ],
    )

    view = service.brain_view(principal_id=OWNER, user_id=USER)

    status = {
        n.label: n.status for n in view.nodes if n.node_id.startswith("context:")
    }
    assert status == {"docs/kept.md": "cited", "docs/deleted.md": "missing"}


def test_an_attached_file_appears_as_a_file(service: DashboardService) -> None:
    _session(service.store, "sess_att", "Read this", "chat")
    attachment_id = new_id("att_")
    payload = b"%PDF-1.4 quarterly"
    service.store.save_attachment(
        attachment_id=attachment_id,
        kind="document",
        filename="quarterly.pdf",
        media_type="application/pdf",
        sha256=hashlib.sha256(payload).hexdigest(),
        data=payload,
        owner_principal_id=OWNER,
    )
    service.store.save_session_attachment_ref(
        session_id="sess_att", attachment_id=attachment_id,
        owner_principal_id=OWNER, turn_id="turn_1", source="uploaded",
    )

    view = service.brain_view(principal_id=OWNER, user_id=USER)

    node = next(n for n in view.nodes if n.node_id == f"attachment:{attachment_id}")
    assert node.node_type == "file"
    assert node.label == "quarterly.pdf"
    assert any(
        e.source == "session:sess_att" and e.target == node.node_id for e in view.edges
    )


def test_no_node_is_left_floating(service: DashboardService) -> None:
    """Every node must connect to something, or the map is a scatter plot.

    A memory whose source event has aged out of the map's window used to be
    drawn with no edge at all — a fact floating free of the work that produced
    it.
    """
    _session(service.store, "sess_m", "Chat", "chat")
    _tool_action(service.store, "sess_m", "memory_search")
    from raiker.memory.store import MemoryGovernance, write_memory

    write_memory(
        "The owner prefers the encrypted NAS target.",
        workspace_root=service.workspace_root,
        store=service.store,
        governance=MemoryGovernance(
            "evt_gone", "sess_m", None, "test", 1, 1, "until_forget", "approved", "test"
        ),
        owner_principal_id=OWNER,
    )

    view = service.brain_view(principal_id=OWNER, user_id=USER)
    connected = {e.source for e in view.edges} | {e.target for e in view.edges}
    floating = [n.node_id for n in view.nodes if n.node_id not in connected]
    assert floating == [], f"every node needs an anchor: {floating}"
