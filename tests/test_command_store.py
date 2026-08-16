from __future__ import annotations

import json
from pathlib import Path

import pytest

from raiker.contracts.ids import utc_now
from raiker.execution.commands import (
    TERMINAL_COMMAND_STATES,
    CommandChunk,
    CommandMaterialCipher,
    CommandReceipt,
    CommandRequest,
    CommandState,
    CommandStore,
    CommandStoreError,
    MaterialUnavailable,
    OutputQuotaExceeded,
    ReceiptImmutable,
    ReceiptRequired,
    SecretMaterialRejected,
    SequenceConflict,
    can_transition,
)
from raiker.storage.sqlite import SQLiteStore


def request(**overrides: object) -> CommandRequest:
    values: dict[str, object] = {
        "run_id": "cmd_1",
        "owner_principal_id": "owner_a",
        "acting_principal_id": "agent_a",
        "session_id": "sess_a",
        "turn_id": "turn_a",
        "action_id": "act_a",
        "repository_id": None,
        "workspace_root": Path("C:/workspace"),
        "cwd": ".",
        "executable_template": "npm test",
        "argv_template": (),
        "safe_display": "npm test",
        "credential_bindings": (),
        "shell": True,
        "interactive": False,
        "background": False,
        "timeout_seconds": 30.0,
        "max_output_bytes": 100_000,
        "environment_profile_id": "container_default",
        "network_policy_id": None,
    }
    values.update(overrides)
    return CommandRequest(**values)  # type: ignore[arg-type]


def receipt_for(run_id: str, terminal: CommandState) -> CommandReceipt:
    return CommandReceipt.create(
        run_id=run_id,
        state=terminal,
        exit_code=0 if terminal is CommandState.SUCCEEDED else 1,
        termination_reason=terminal.value,
        completed_at=utc_now(),
        evidence={"backend": "test", "isolation": "fixture"},
    )


@pytest.fixture
def sqlite(tmp_path: Path) -> SQLiteStore:
    return SQLiteStore(tmp_path)


@pytest.fixture
def store(sqlite: SQLiteStore) -> CommandStore:
    return CommandStore(sqlite)


def test_request_requires_exactly_one_command_representation() -> None:
    with pytest.raises(ValueError, match="command_representation_invalid"):
        request(executable_template="npm test", argv_template=("npm", "test"))
    with pytest.raises(ValueError, match="command_representation_invalid"):
        request(executable_template="", argv_template=())


def test_authority_evidence_is_queryable_without_decrypting_execution_material(store: CommandStore) -> None:
    created = store.create(request(authority_kind="standing_grant", authority_id="grant_a"))

    assert created.authority_kind == "standing_grant"
    assert created.authority_id == "grant_a"


def test_digest_authority_is_not_mistaken_for_secret_material(store: CommandStore) -> None:
    digest = "a" * 64
    created = store.create(
        request(authority_kind="session_command_grant", authority_id=digest)
    )

    assert created.authority_id == digest


def test_secret_shaped_authority_is_rejected_before_persistence(store: CommandStore) -> None:
    with pytest.raises(SecretMaterialRejected, match="command_secret_pattern_rejected"):
        store.create(
            request(
                authority_kind="approval",
                authority_id="sk-examplecredentialvalue123456789",
            )
        )


@pytest.mark.parametrize("cwd", ("../escape", "/absolute", "C:/absolute"))
def test_request_rejects_uncontained_working_directory(cwd: str) -> None:
    with pytest.raises(ValueError, match="command_cwd_invalid"):
        request(cwd=cwd)


def test_request_rejects_unbounded_limits_and_unsafe_display() -> None:
    with pytest.raises(ValueError, match="command_timeout_invalid"):
        request(timeout_seconds=0)
    with pytest.raises(ValueError, match="command_output_limit_invalid"):
        request(max_output_bytes=0)
    with pytest.raises(ValueError, match="command_safe_display_invalid"):
        request(safe_display="")


def test_terminal_states_require_atomic_finalization() -> None:
    assert can_transition(CommandState.RUNNING, CommandState.FINALIZING)
    assert can_transition(CommandState.FINALIZING, CommandState.SUCCEEDED)
    assert not can_transition(CommandState.SUCCEEDED, CommandState.FAILED)


@pytest.mark.parametrize("terminal", TERMINAL_COMMAND_STATES)
def test_terminal_transition_requires_receipt_in_same_transaction(
    store: CommandStore, terminal: CommandState
) -> None:
    store.create(request())
    assert store.transition("owner_a", "cmd_1", CommandState.QUEUED, CommandState.STARTING)
    assert store.transition("owner_a", "cmd_1", CommandState.STARTING, CommandState.FINALIZING)
    with pytest.raises(ReceiptRequired):
        store.transition("owner_a", "cmd_1", CommandState.FINALIZING, terminal)
    store.finalize_with_receipt("owner_a", "cmd_1", terminal, receipt_for("cmd_1", terminal))
    assert store.receipt_count("owner_a", "cmd_1") == 1


def test_command_store_is_owner_scoped_and_chunks_are_monotonic(store: CommandStore) -> None:
    store.create(request())
    assert store.transition("owner_a", "cmd_1", CommandState.QUEUED, CommandState.STARTING)
    assert not store.transition("owner_a", "cmd_1", CommandState.QUEUED, CommandState.RUNNING)
    store.append_chunk("owner_a", CommandChunk("cmd_1", 1, "stdout", "one", 3, utc_now()))
    store.append_chunk("owner_a", CommandChunk("cmd_1", 2, "stderr", "two", 3, utc_now()))

    output = store.read_output("owner_a", "cmd_1", after=0)
    assert [row.sequence for row in output] == [1, 2]
    assert [(row.start_byte_offset, row.end_byte_offset) for row in output] == [(0, 3), (3, 6)]
    assert store.read_output("owner_a", "cmd_1", after=1)[0].sequence == 2
    assert store.list_runs("owner_b", session_id="sess_a") == []
    assert store.load("owner_b", "cmd_1") is None


def test_chunk_sequence_and_byte_count_are_fail_closed(store: CommandStore) -> None:
    store.create(request())
    store.append_chunk("owner_a", CommandChunk("cmd_1", 1, "stdout", "one", 3, utc_now()))
    with pytest.raises(SequenceConflict):
        store.append_chunk("owner_a", CommandChunk("cmd_1", 3, "stdout", "gap", 3, utc_now()))
    with pytest.raises(ValueError, match="command_chunk_byte_count_invalid"):
        CommandChunk("cmd_1", 2, "stdout", "é", 1, utc_now())


def test_output_quota_is_enforced_per_run(sqlite: SQLiteStore) -> None:
    store = CommandStore(sqlite, max_chunks_per_run=1)
    store.create(request())
    store.append_chunk("owner_a", CommandChunk("cmd_1", 1, "stdout", "one", 3, utc_now()))
    with pytest.raises(OutputQuotaExceeded):
        store.append_chunk("owner_a", CommandChunk("cmd_1", 2, "stdout", "two", 3, utc_now()))


def test_final_receipt_is_immutable_and_owner_scoped(store: CommandStore) -> None:
    store.create(request())
    store.transition("owner_a", "cmd_1", CommandState.QUEUED, CommandState.STARTING)
    store.transition("owner_a", "cmd_1", CommandState.STARTING, CommandState.FINALIZING)
    receipt = receipt_for("cmd_1", CommandState.SUCCEEDED)
    store.finalize_with_receipt("owner_a", "cmd_1", CommandState.SUCCEEDED, receipt)

    assert store.get_receipt("owner_b", "cmd_1") is None
    assert store.get_receipt("owner_a", "cmd_1") == receipt
    with pytest.raises(ReceiptImmutable):
        store.finalize_with_receipt("owner_a", "cmd_1", CommandState.SUCCEEDED, receipt)


def test_recoverable_list_excludes_terminal_runs(store: CommandStore) -> None:
    store.create(request(run_id="cmd_running"))
    store.create(request(run_id="cmd_final", action_id="act_b"))
    store.transition("owner_a", "cmd_final", CommandState.QUEUED, CommandState.STARTING)
    store.transition("owner_a", "cmd_final", CommandState.STARTING, CommandState.FINALIZING)
    store.finalize_with_receipt(
        "owner_a", "cmd_final", CommandState.FAILED, receipt_for("cmd_final", CommandState.FAILED)
    )

    assert [run.run_id for run in store.list_recoverable("owner_a")] == ["cmd_running"]


def test_registered_and_pattern_secrets_never_reach_the_database(sqlite: SQLiteStore) -> None:
    secret = "registered-value-123"
    store = CommandStore(sqlite, registered_secrets=(secret,))
    with pytest.raises(SecretMaterialRejected):
        store.create(request(executable_template=f"curl -H {secret} example.test", safe_display="curl [redacted]"))
    with pytest.raises(SecretMaterialRejected):
        store.create(
            request(
                run_id="cmd_2",
                action_id="act_2",
                executable_template="curl -H sk-proj-aabbccddeeff00112233 example.test",
                safe_display="curl [redacted]",
            )
        )

    values: list[str] = []
    with sqlite.connect() as connection:
        table_names = [
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        ]
        for table_name in table_names:
            quoted = table_name.replace('"', '""')
            for row in connection.execute(f'SELECT * FROM "{quoted}"').fetchall():
                for value in row:
                    if isinstance(value, bytes):
                        values.append(value.decode("utf-8", errors="ignore"))
                    elif isinstance(value, str):
                        values.append(value)
    dump = "\n".join(values)
    assert secret not in dump
    assert "sk-proj-aabbccddeeff00112233" not in dump


@pytest.mark.parametrize(
    "unsafe",
    (
        "password=correct-horse-battery-staple",
        "Authorization: Bearer abcdefghijklmnop",
        "operator@example.test",
        "4111 1111 1111 1111",
        "iban GB82WEST12345698765432",
        "123-456-7890",
        "A" * 40,
        "-----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY-----",
    ),
)
def test_every_redaction_rule_is_rejected_before_command_persistence(
    store: CommandStore, unsafe: str
) -> None:
    with pytest.raises(SecretMaterialRejected, match="command_secret_pattern_rejected"):
        store.create(request(executable_template=unsafe, safe_display="[protected command]"))


def test_encrypted_execution_material_is_not_plaintext(sqlite: SQLiteStore) -> None:
    store = CommandStore(sqlite)
    store.create(request())
    with sqlite.connect() as connection:
        row = connection.execute(
            "SELECT encrypted_execution_material FROM command_runs WHERE run_id = ?", ("cmd_1",)
        ).fetchone()
    assert row is not None
    assert b"npm test" not in bytes(row["encrypted_execution_material"])
    assert store.execution_material("owner_a", "cmd_1")["executable_template"] == "npm test"


def test_encrypted_material_fails_closed_while_cipher_is_locked(sqlite: SQLiteStore) -> None:
    unlocked = CommandStore(sqlite)
    unlocked.create(request())
    locked = CommandStore(
        sqlite,
        material_cipher=CommandMaterialCipher(sqlite.paths.workspace_root, is_locked=lambda: True),
    )
    with pytest.raises(MaterialUnavailable, match="command_material_locked"):
        locked.execution_material("owner_a", "cmd_1")


def test_command_migration_is_idempotent(tmp_path: Path) -> None:
    first = SQLiteStore(tmp_path)
    second = SQLiteStore(tmp_path)
    expected = {"command_runs", "command_output_chunks", "command_network_grants", "command_network_attempts", "command_receipts"}
    assert expected.issubset(first.table_names())
    assert expected.issubset(second.table_names())


def test_receipt_canonical_json_matches_digest() -> None:
    receipt = receipt_for("cmd_1", CommandState.SUCCEEDED)
    payload = json.loads(receipt.canonical_json)
    assert payload["run_id"] == "cmd_1"
    assert len(receipt.digest) == 64


def test_the_backend_column_names_what_ran_the_command(store: CommandStore) -> None:
    """BUG-197 — the row the owner browses must agree with the receipt.

    Every ``command_runs`` row carried ``backend = ''`` while the receipt
    recorded the real backend, so the immutable record knew what ran a command
    and the list did not.
    """
    created = store.create(request())
    assert created.backend == ""

    store.record_backend("owner_a", "cmd_1", "native")

    loaded = store.load("owner_a", "cmd_1")
    assert loaded is not None and loaded.backend == "native"
    assert store.list_runs("owner_a", session_id="sess_a")[0].backend == "native"


def test_recording_a_backend_for_an_unknown_run_fails_closed(store: CommandStore) -> None:
    with pytest.raises(CommandStoreError, match="command_run_not_found"):
        store.record_backend("owner_a", "cmd_missing", "native")


def test_a_backend_is_scoped_to_its_owner(store: CommandStore) -> None:
    store.create(request())
    with pytest.raises(CommandStoreError, match="command_run_not_found"):
        store.record_backend("owner_b", "cmd_1", "native")
