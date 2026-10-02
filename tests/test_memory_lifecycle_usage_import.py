"""UX-MEM-02, UX-MEM-05 and UX-MEM-08 — the Memory page's three server halves.

* An archived or expired record can be *listed* for the owner to restore or
  extend, and still cannot be recalled.
* A record says how many turns were given it and which was the latest, read
  from the per-turn recall ledger and scoped to the account that ran the turn.
* An import is a batch: every record gets a status before anything is written,
  the owner's per-record skips are honoured by the server, and the receipt can
  take the import back without touching a record the owner changed since.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.control.dashboard import DashboardService
from raiker.memory.store import MemoryGovernance, get_memory, search_memory, write_memory
from raiker.storage.sqlite import SQLiteStore

OWNER = "principal_owner"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def service(workspace: Path) -> DashboardService:
    return DashboardService(workspace)


def _seed(store: SQLiteStore, workspace: Path, text: str, scope: str = "project") -> str:
    return write_memory(
        text,
        workspace_root=workspace,
        scope=scope,
        governance=MemoryGovernance(
            "evt_seed", "sess_seed", "turn_seed", "agent", 0.9, 0.8, "until_forget", "approved", OWNER
        ),
        store=store,
        owner_principal_id=OWNER,
    ).memory_id


class TestInactiveRecordsAreListedNotRecalled:
    def test_archived_and_expired_records_list_only_when_asked(
        self, service: DashboardService, workspace: Path
    ) -> None:
        active = _seed(service.store, workspace, "Active fact about kettles.")
        archived = _seed(service.store, workspace, "Archived fact about kettles.")
        expired = _seed(service.store, workspace, "Expired fact about kettles.")
        assert service.set_memory_archived(archived, True, OWNER).ok
        assert service.set_memory_expiry(expired, "2000-01-01T00:00:00Z", OWNER).ok

        default = {m.memory_id for m in service.list_memories(acting_principal_id=OWNER)}
        assert default == {active}

        listed = {
            m.memory_id: m
            for m in service.list_memories(acting_principal_id=OWNER, include_inactive=True)
        }
        assert set(listed) == {active, archived, expired}
        assert listed[archived].archived_at is not None
        assert listed[expired].expires_at == "2000-01-01T00:00:00Z"

        # Listing is not recall: neither inactive record can be found by a turn.
        hits = {e.memory_id for e in search_memory("kettles", workspace_root=workspace, store=service.store)}
        assert hits == {active}

    def test_a_forgotten_record_is_not_listed_even_with_inactive(
        self, service: DashboardService, workspace: Path
    ) -> None:
        gone = _seed(service.store, workspace, "Forget me.")
        assert service.forget_memory_controlled(gone, OWNER).ok
        assert service.list_memories(acting_principal_id=OWNER, include_inactive=True) == []

    def test_export_still_carries_only_active_records(
        self, service: DashboardService, workspace: Path
    ) -> None:
        kept = _seed(service.store, workspace, "Kept.")
        archived = _seed(service.store, workspace, "Archived.")
        assert service.set_memory_archived(archived, True, OWNER).ok
        exported = service.export_memories(OWNER)
        assert [m["memory_id"] for m in exported.data["memories"]] == [kept]


class TestRecallUsage:
    def test_a_record_counts_the_turns_it_was_given_and_names_the_latest(
        self, service: DashboardService, workspace: Path
    ) -> None:
        memory_id = _seed(service.store, workspace, "Prefers tea.")
        never = _seed(service.store, workspace, "Owns a bicycle.")
        service.store.record_turn_recall(
            session_id="sess_a", turn_id="turn_1", principal_id=OWNER, memory_ids=[memory_id]
        )
        service.store.record_turn_recall(
            session_id="sess_b", turn_id="turn_9", principal_id=OWNER, memory_ids=[memory_id]
        )
        # Ordered by when the ledger wrote them; force the second to be later.
        with service.store.connect() as connection:
            connection.execute(
                "UPDATE turn_recalls SET created_at = '2030-01-01T00:00:00Z' WHERE turn_id = 'turn_9'"
            )

        rows = {m.memory_id: m for m in service.list_memories(acting_principal_id=OWNER)}
        used = rows[memory_id]
        assert used.recall_turn_count == 2
        assert used.last_recalled_session_id == "sess_b"
        assert used.last_recalled_turn_id == "turn_9"
        assert used.last_recalled_origin == "chat"
        assert used.last_used_at == "2030-01-01T00:00:00Z"

        unused = rows[never]
        assert unused.recall_turn_count == 0
        assert unused.last_recalled_turn_id is None
        assert unused.last_used_at is None

    def test_another_accounts_turns_are_never_linked(
        self, service: DashboardService, workspace: Path
    ) -> None:
        memory_id = _seed(service.store, workspace, "Prefers coffee.")
        service.store.record_turn_recall(
            session_id="sess_other", turn_id="turn_x", principal_id="principal_someone_else",
            memory_ids=[memory_id],
        )
        row = service.list_memories(acting_principal_id=OWNER)[0]
        assert row.recall_turn_count == 0
        assert row.last_recalled_session_id is None

    def test_no_principal_reads_no_usage(self, service: DashboardService) -> None:
        assert service.store.memory_recall_usage(["mem_x"], "") == {}


class TestImportPreviewNamesEveryRecord:
    def test_each_record_gets_a_status_and_nothing_is_written(
        self, service: DashboardService, workspace: Path
    ) -> None:
        _seed(service.store, workspace, "Deploys happen on Thursdays.")
        records = [
            {"text": "Deploys happen on Thursdays."},
            {"text": "deploys  happen on thursdays"},
            {"text": "Backups go to the NAS."},
            {"text": "Backups go to the NAS."},
        ]
        preview = service.preview_memory_import(records, OWNER)
        assert preview.ok
        statuses = [r["status"] for r in preview.data["records"]]
        assert statuses == ["duplicate", "similar", "new", "duplicate_in_file"]
        assert preview.data["similar_count"] == 1
        assert preview.data["new_count"] == 2
        assert preview.data["source_class"] == "foreign"
        # A similar record names the one it resembles, so the owner compares
        # two specific sentences rather than trusting a count.
        assert preview.data["records"][1]["memory_id"].startswith("mem_")
        assert len(service.list_memories(acting_principal_id=OWNER)) == 1

    def test_a_raiker_export_is_recognised_by_its_shape(
        self, service: DashboardService, workspace: Path
    ) -> None:
        _seed(service.store, workspace, "Exported fact.")
        exported = service.export_memories(OWNER).data["memories"]
        preview = service.preview_memory_import(exported, OWNER)
        assert preview.data["source_class"] == "raiker_export"


class TestImportIsABatchThatCanBeTakenBack:
    def test_the_owners_skips_are_honoured_and_counted(
        self, service: DashboardService
    ) -> None:
        result = service.import_memories(
            [{"text": "Keep this."}, {"text": "Skip this."}],
            OWNER,
            exclude_indices=frozenset({1}),
            file_name="notes.json",
        )
        assert result.ok
        assert result.data["imported"] == 1
        assert result.data["skipped_by_owner"] == 1
        assert result.data["batch_id"].startswith("mib_")
        listed = service.list_memories(acting_principal_id=OWNER)
        assert [m.text for m in listed] == ["Keep this."]
        # Said as an import wherever the record is read, not as the agent's.
        assert listed[0].source == "user_import"

        batches = service.list_memory_import_batches(OWNER).data["batches"]
        assert batches[0]["batch_id"] == result.data["batch_id"]
        assert batches[0]["file_name"] == "notes.json"
        assert batches[0]["imported"] == 1 and batches[0]["skipped"] == 1
        assert batches[0]["undone_at"] is None

    def test_an_import_that_wrote_nothing_has_no_receipt(self, service: DashboardService) -> None:
        assert service.import_memories([{"text": "Once."}], OWNER).ok
        again = service.import_memories([{"text": "Once."}], OWNER)
        assert again.data["batch_id"] == ""
        assert len(service.list_memory_import_batches(OWNER).data["batches"]) == 1

    def test_undo_forgets_what_the_batch_wrote_and_keeps_what_the_owner_changed(
        self, service: DashboardService, workspace: Path
    ) -> None:
        by_hand = _seed(service.store, workspace, "Written by hand.")
        result = service.import_memories(
            [{"text": "Imported one."}, {"text": "Imported two."}], OWNER
        )
        batch_id = result.data["batch_id"]
        rows = {m.text: m.memory_id for m in service.list_memories(acting_principal_id=OWNER)}
        assert service.edit_memory_controlled(rows["Imported two."], "Imported two, corrected.", OWNER).ok

        undone = service.undo_memory_import(batch_id, OWNER)
        assert undone.ok
        assert undone.data == {
            "batch_id": batch_id,
            "removed": 1,
            "kept_changed": 1,
            "already_gone": 0,
        }
        remaining = {m.text for m in service.list_memories(acting_principal_id=OWNER)}
        assert remaining == {"Written by hand.", "Imported two, corrected."}
        assert get_memory(rows["Imported one."], workspace_root=workspace) is None
        assert get_memory(by_hand, workspace_root=workspace) is not None

        again = service.undo_memory_import(batch_id, OWNER)
        assert not again.ok and again.reason_code == "import_batch_already_undone"
        settled = service.list_memory_import_batches(OWNER).data["batches"][0]
        assert settled["undone_at"] is not None

    def test_a_record_already_forgotten_is_counted_as_gone(
        self, service: DashboardService
    ) -> None:
        result = service.import_memories([{"text": "Short-lived."}], OWNER)
        memory_id = service.list_memories(acting_principal_id=OWNER)[0].memory_id
        assert service.forget_memory_controlled(memory_id, OWNER).ok
        undone = service.undo_memory_import(result.data["batch_id"], OWNER)
        assert undone.ok and undone.data["already_gone"] == 1 and undone.data["removed"] == 0

    def test_another_account_cannot_undo_or_see_a_batch(self, service: DashboardService) -> None:
        result = service.import_memories([{"text": "Mine."}], OWNER)
        assert service.store.get_memory_import_batch(
            result.data["batch_id"], owner_principal_id="principal_someone_else"
        ) is None
        assert service.store.list_memory_import_batches(owner_principal_id="principal_someone_else") == []
