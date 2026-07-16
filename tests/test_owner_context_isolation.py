from __future__ import annotations

import json
from pathlib import Path

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.context.gatherer import ContextGatherer
from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import VectorRecord
from raiker.memory.retrieval import retrieve_hybrid_memory
from raiker.memory.store import MemoryGovernance, list_memory, write_memory
from raiker.runtime.attachments import load_document, store_document, store_image
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.memory_tools import memory_get, memory_list, memory_search
from raiker.tools.vector_tools import vector_get
from raiker.vector import LOCAL_EMBEDDING_MODEL, embed_text


def _governance(owner: str) -> MemoryGovernance:
    return MemoryGovernance("evt", "session", None, "test", 1.0, 1.0, "until_forget", "approved", owner)


def test_memory_list_and_vector_retrieval_are_owner_scoped(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    alice = write_memory(
        "Alice confidential roadmap", workspace_root=tmp_path, store=store,
        governance=_governance("principal_alice"), owner_principal_id="principal_alice",
    )
    bob = write_memory(
        "Bob deployment checklist", workspace_root=tmp_path, store=store,
        governance=_governance("principal_bob"), owner_principal_id="principal_bob",
    )
    for memory, owner in ((alice, "principal_alice"), (bob, "principal_bob")):
        vector_id = new_id("vec_")
        store.insert_vector_record(VectorRecord(
            vector_id=vector_id, content_hash=memory.memory_id, content_preview="redacted",
            embedding_model=LOCAL_EMBEDDING_MODEL, dimensions=384, scope=memory.scope,
            sensitivity=memory.sensitivity, created_at=utc_now(),
            embedding=json.dumps(embed_text(memory.text, 384)), owner_principal_id=owner,
        ))
        store.link_memory_projection(
            memory.memory_id, "vector", vector_id, LOCAL_EMBEDDING_MODEL,
            owner_principal_id=owner,
        )

    assert [m.memory_id for m in list_memory(store=store, workspace_root=tmp_path, owner_principal_id="principal_alice")] == [alice.memory_id]
    results = retrieve_hybrid_memory(
        store=store, query="deployment checklist", owner_principal_id="principal_bob"
    )
    assert [result.memory_id for result in results] == [bob.memory_id]
    assert all("Alice" not in result.text for result in results)


def test_foreign_document_attachment_never_enters_prompt_context(  # type: ignore[no-untyped-def]
    tmp_path: Path, seed_account
) -> None:
    # Real accounts, because a turn is only owner-scoped for a real account.
    store = SQLiteStore(tmp_path)
    alice, _ = seed_account(tmp_path, "alice")
    bob, _ = seed_account(tmp_path, "bob")
    attachment = store_document(
        store, filename="alice.txt", media_type="text/plain", data=b"ALICE SECRET",
        owner_principal_id=alice,
    )

    assert load_document(store, attachment.attachment_id, owner_principal_id=bob) is None
    bundle = ContextGatherer().gather(
        workspace_root=tmp_path, session_id="missing", turn_id="turn", prompt_text="summarize",
        attachments=[{"type": "document", "attachment_id": attachment.attachment_id}],
        owner_principal_id=bob,
    )
    item = next(item for item in bundle.items if item.source.source_type == "attachment")
    assert item.metadata["attachment_status"] == "not_found"
    assert "ALICE SECRET" not in item.content


def test_direct_memory_and_vector_reads_require_the_calling_owner(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    memory = write_memory(
        "Alice private memory", workspace_root=tmp_path, store=store,
        governance=_governance("principal_alice"), owner_principal_id="principal_alice",
    )
    vector_id = new_id("vec_")
    store.insert_vector_record(VectorRecord(
        vector_id=vector_id, content_hash="hash", content_preview="Alice preview",
        embedding_model=LOCAL_EMBEDDING_MODEL, dimensions=384, scope="project",
        sensitivity="normal", created_at=utc_now(), owner_principal_id="principal_alice",
    ))

    assert memory_list(tmp_path, owner_principal_id="principal_bob")["count"] == 0
    assert memory_search(tmp_path, "private", owner_principal_id="principal_bob")["count"] == 0
    assert memory_get(tmp_path, memory.memory_id, owner_principal_id="principal_bob")["status"] == "failed"
    assert vector_get(tmp_path, vector_id, owner_principal_id="principal_bob")["status"] == "failed"


def test_foreign_image_attachment_never_resolves_for_delivery(  # type: ignore[no-untyped-def]
    tmp_path: Path, seed_account
) -> None:
    # Real accounts, because a turn is only owner-scoped for a real account.
    store = SQLiteStore(tmp_path)
    alice, _ = seed_account(tmp_path, "alice")
    bob, _ = seed_account(tmp_path, "bob")
    image = store_image(
        store, filename="alice.png", media_type="image/png", data=b"\x89PNG\r\n\x1a\n",
        owner_principal_id=alice,
    )
    bundle = ContextGatherer().gather(
        workspace_root=tmp_path, session_id="missing", turn_id="turn", prompt_text="describe",
        attachments=[{"type": "image", "attachment_id": image.attachment_id}],
        owner_principal_id=bob,
    )
    item = next(item for item in bundle.items if item.source.source_type == "attachment")
    assert item.metadata["attachment_status"] == "not_found"


def test_first_owner_backfills_legacy_prompt_data_created_before_an_account(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    attachment = store_document(
        store, filename="legacy.txt", media_type="text/plain", data=b"legacy",
    )
    before = store.load_attachment(attachment.attachment_id)
    assert before is not None
    assert before["owner_principal_id"] is None

    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)

    after = store.load_attachment(attachment.attachment_id)
    assert after is not None
    assert after["owner_principal_id"] == "principal_owner"


def test_cli_turn_keeps_its_project_context_and_model_selection(tmp_path: Path) -> None:
    """The terminal client's default user id is not a principal.

    ``UserMetadata`` defaults ``id`` to ``local_user``, and the orchestrator
    passes it straight through as ``owner_principal_id``. It is truthy but names
    no account, so treating any truthy value as "scoped" silently emptied every
    owner-scoped source for CLI turns. Scoping must key off a real account.
    """
    from raiker.contracts.models import UserMetadata
    from raiker.models.session_state import TERMINAL_MODEL_SESSION_ID, ModelSessionState

    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    store = SQLiteStore(tmp_path)
    owner_user_id = store.principal_user_id("principal_owner")
    store.create_project("proj_cli", "CLI", "cli", owner_user_id=owner_user_id)
    store.save_project_context(
        "proj_cli", instructions="CLI house rules.", attachment_ids=[], memory_enabled=False
    )
    store.save_active_project("proj_cli", owner_user_id)
    store.create_session("sess_cli", str(tmp_path), user_id=owner_user_id)
    store.save_model_session_state(ModelSessionState(
        session_id=TERMINAL_MODEL_SESSION_ID, profile_id="anthropic-hosted", model="claude-x",
    ))

    bundle = ContextGatherer().gather(
        workspace_root=tmp_path, session_id="sess_cli", turn_id="turn_cli",
        prompt_text="hello", owner_principal_id=UserMetadata().id,
    )
    content = "\n".join(item.content for item in bundle.items)

    assert "CLI house rules." in content
    assert "profile_id: anthropic-hosted" in content
