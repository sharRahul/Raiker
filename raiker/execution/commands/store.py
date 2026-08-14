from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from cryptography.fernet import InvalidToken

from raiker.auth.app_key import app_fernet
from raiker.contracts.ids import new_id, utc_now
from raiker.execution.commands.models import (
    TERMINAL_COMMAND_STATES,
    CommandChunk,
    CommandReceipt,
    CommandRequest,
    CommandState,
    StoredCommandRun,
    can_transition,
)
from raiker.storage.sqlite import SQLiteStore


class CommandStoreError(RuntimeError):
    pass


class ReceiptRequired(CommandStoreError):
    pass


class ReceiptImmutable(CommandStoreError):
    pass


class SequenceConflict(CommandStoreError):
    pass


class OutputQuotaExceeded(CommandStoreError):
    pass


class SecretMaterialRejected(CommandStoreError):
    pass


class MaterialUnavailable(CommandStoreError):
    pass


class CommandMaterialCipher:
    def __init__(
        self,
        workspace_root: str | Path,
        *,
        is_locked: Callable[[], bool] | None = None,
    ) -> None:
        self._workspace_root = workspace_root
        self._is_locked = is_locked or (lambda: False)

    def encrypt(self, material: dict[str, Any]) -> bytes:
        if self._is_locked():
            raise MaterialUnavailable("command_material_locked")
        plain = json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
        return app_fernet(self._workspace_root).encrypt(plain)

    def decrypt(self, encrypted: bytes) -> dict[str, Any]:
        if self._is_locked():
            raise MaterialUnavailable("command_material_locked")
        try:
            plain = app_fernet(self._workspace_root).decrypt(encrypted)
        except InvalidToken as exc:
            raise MaterialUnavailable("command_material_unreadable") from exc
        value = json.loads(plain)
        if not isinstance(value, dict):
            raise MaterialUnavailable("command_material_invalid")
        return value


_SECRET_PATTERNS = (
    re.compile(r"\bsk-(?:proj|ant|or-v1)-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{16,}\b"),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
)


class CommandStore:
    def __init__(
        self,
        sqlite: SQLiteStore,
        *,
        material_cipher: CommandMaterialCipher | None = None,
        registered_secrets: Iterable[str] = (),
        max_chunks_per_run: int = 10_000,
    ) -> None:
        if max_chunks_per_run <= 0:
            raise ValueError("command_chunk_quota_invalid")
        self.sqlite = sqlite
        self.material_cipher = material_cipher or CommandMaterialCipher(sqlite.paths.workspace_root)
        self.registered_secrets = tuple(value for value in registered_secrets if value)
        self.max_chunks_per_run = max_chunks_per_run

    def _reject_secrets(self, request: CommandRequest) -> None:
        material = json.dumps(request.execution_material(), sort_keys=True)
        safe_display = request.safe_display
        for secret in self.registered_secrets:
            if secret in material or secret in safe_display:
                raise SecretMaterialRejected("command_secret_literal_rejected")
        if any(pattern.search(material) or pattern.search(safe_display) for pattern in _SECRET_PATTERNS):
            raise SecretMaterialRejected("command_secret_pattern_rejected")

    def create(self, request: CommandRequest) -> StoredCommandRun:
        self._reject_secrets(request)
        encrypted = self.material_cipher.encrypt(request.execution_material())
        now = utc_now()
        with self.sqlite.connect() as connection:
            connection.execute(
                """INSERT INTO command_runs (
                    run_id, owner_principal_id, acting_principal_id, session_id, turn_id,
                    action_id, state, profile_id, safe_display, template_digest,
                    encrypted_execution_material, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    request.run_id,
                    request.owner_principal_id,
                    request.acting_principal_id,
                    request.session_id,
                    request.turn_id,
                    request.action_id,
                    CommandState.QUEUED.value,
                    request.environment_profile_id,
                    request.safe_display,
                    request.template_digest,
                    encrypted,
                    now,
                    now,
                ),
            )
        loaded = self.load(request.owner_principal_id, request.run_id)
        if loaded is None:  # pragma: no cover - INSERT and owner use the same immutable values
            raise CommandStoreError("command_create_failed")
        return loaded

    def create_finalizing(self, request: CommandRequest) -> StoredCommandRun:
        self.create(request)
        self.transition(request.owner_principal_id, request.run_id, CommandState.QUEUED, CommandState.STARTING)
        self.transition(request.owner_principal_id, request.run_id, CommandState.STARTING, CommandState.FINALIZING)
        loaded = self.load(request.owner_principal_id, request.run_id)
        assert loaded is not None
        return loaded

    def transition(
        self,
        owner_principal_id: str,
        run_id: str,
        current: CommandState,
        target: CommandState,
    ) -> bool:
        if target in TERMINAL_COMMAND_STATES:
            raise ReceiptRequired("command_terminal_receipt_required")
        if not can_transition(current, target):
            return False
        now = utc_now()
        started_at = now if target is CommandState.RUNNING else None
        with self.sqlite.connect() as connection:
            cursor = connection.execute(
                """UPDATE command_runs
                   SET state = ?, updated_at = ?, started_at = COALESCE(started_at, ?)
                   WHERE owner_principal_id = ? AND run_id = ? AND state = ?""",
                (target.value, now, started_at, owner_principal_id, run_id, current.value),
            )
        return cursor.rowcount == 1

    def finalize_with_receipt(
        self,
        owner_principal_id: str,
        run_id: str,
        terminal: CommandState,
        receipt: CommandReceipt,
    ) -> StoredCommandRun:
        if terminal not in TERMINAL_COMMAND_STATES or receipt.state is not terminal:
            raise ValueError("command_receipt_state_invalid")
        if receipt.run_id != run_id:
            raise ValueError("command_receipt_run_invalid")
        connection = self.sqlite.connect()
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        try:
            existing = connection.execute(
                "SELECT 1 FROM command_receipts WHERE owner_principal_id = ? AND run_id = ?",
                (owner_principal_id, run_id),
            ).fetchone()
            if existing is not None:
                raise ReceiptImmutable("command_receipt_immutable")
            cursor = connection.execute(
                """UPDATE command_runs SET state = ?, exit_code = ?, termination_reason = ?,
                   completed_at = ?, updated_at = ?, receipt_digest = ?
                   WHERE owner_principal_id = ? AND run_id = ? AND state = ?""",
                (
                    terminal.value,
                    receipt.exit_code,
                    receipt.termination_reason,
                    receipt.completed_at,
                    receipt.completed_at,
                    receipt.digest,
                    owner_principal_id,
                    run_id,
                    CommandState.FINALIZING.value,
                ),
            )
            if cursor.rowcount != 1:
                raise CommandStoreError("command_not_finalizing")
            connection.execute(
                """INSERT INTO command_receipts
                   (run_id, owner_principal_id, receipt_json, digest, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (run_id, owner_principal_id, receipt.canonical_json, receipt.digest, utc_now()),
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        loaded = self.load(owner_principal_id, run_id)
        if loaded is None:  # pragma: no cover
            raise CommandStoreError("command_finalize_failed")
        return loaded

    def append_chunk(self, owner_principal_id: str, chunk: CommandChunk) -> CommandChunk:
        connection = self.sqlite.connect()
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        try:
            row = connection.execute(
                """SELECT COUNT(*) AS count, COALESCE(MAX(sequence), 0) AS sequence,
                          COALESCE(MAX(end_byte_offset), 0) AS offset
                   FROM command_output_chunks
                   WHERE owner_principal_id = ? AND run_id = ?""",
                (owner_principal_id, chunk.run_id),
            ).fetchone()
            run = connection.execute(
                "SELECT 1 FROM command_runs WHERE owner_principal_id = ? AND run_id = ?",
                (owner_principal_id, chunk.run_id),
            ).fetchone()
            if run is None:
                raise CommandStoreError("command_run_not_found")
            assert row is not None
            if int(row["count"]) >= self.max_chunks_per_run:
                raise OutputQuotaExceeded("command_output_quota_exceeded")
            if chunk.sequence != int(row["sequence"]) + 1:
                raise SequenceConflict("command_chunk_sequence_conflict")
            start = int(row["offset"])
            end = start + chunk.byte_count
            connection.execute(
                """INSERT INTO command_output_chunks
                   (owner_principal_id, run_id, sequence, stream, text,
                    start_byte_offset, end_byte_offset, byte_count, emitted_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    owner_principal_id,
                    chunk.run_id,
                    chunk.sequence,
                    chunk.stream,
                    chunk.text,
                    start,
                    end,
                    chunk.byte_count,
                    chunk.emitted_at,
                ),
            )
            byte_column = "stderr_bytes" if chunk.stream == "stderr" else "stdout_bytes"
            connection.execute(
                f"UPDATE command_runs SET {byte_column} = {byte_column} + ?, updated_at = ? "
                "WHERE owner_principal_id = ? AND run_id = ?",
                (chunk.byte_count, utc_now(), owner_principal_id, chunk.run_id),
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        return CommandChunk(
            chunk.run_id,
            chunk.sequence,
            chunk.stream,
            chunk.text,
            chunk.byte_count,
            chunk.emitted_at,
            start,
            end,
        )

    def read_output(
        self, owner_principal_id: str, run_id: str, *, after: int = 0, limit: int = 500
    ) -> list[CommandChunk]:
        if limit <= 0 or limit > 5_000:
            raise ValueError("command_output_page_invalid")
        with self.sqlite.connect() as connection:
            rows = connection.execute(
                """SELECT run_id, sequence, stream, text, byte_count, emitted_at,
                          start_byte_offset, end_byte_offset
                   FROM command_output_chunks
                   WHERE owner_principal_id = ? AND run_id = ? AND sequence > ?
                   ORDER BY sequence ASC LIMIT ?""",
                (owner_principal_id, run_id, after, limit),
            ).fetchall()
        return [CommandChunk(**dict(row)) for row in rows]

    def update_runtime_summary(
        self,
        owner_principal_id: str,
        run_id: str,
        *,
        stdout_bytes: int,
        stderr_bytes: int,
        truncated: bool,
        redaction_count: int,
    ) -> None:
        """Publish bounded runtime counters without exposing execution material."""
        with self.sqlite.connect() as connection:
            cursor = connection.execute(
                """UPDATE command_runs
                   SET stdout_bytes = ?, stderr_bytes = ?, truncated = ?,
                       redaction_count = ?, updated_at = ?
                   WHERE owner_principal_id = ? AND run_id = ?""",
                (
                    max(0, stdout_bytes),
                    max(0, stderr_bytes),
                    int(truncated),
                    max(0, redaction_count),
                    utc_now(),
                    owner_principal_id,
                    run_id,
                ),
            )
        if cursor.rowcount != 1:
            raise CommandStoreError("command_run_not_found")

    def load(self, owner_principal_id: str, run_id: str) -> StoredCommandRun | None:
        with self.sqlite.connect() as connection:
            row = connection.execute(
                """SELECT run_id, owner_principal_id, acting_principal_id, session_id,
                          turn_id, action_id, state, profile_id, backend, safe_display,
                          template_digest, started_at, completed_at, lease_expires_at,
                          exit_code, termination_reason, stdout_bytes, stderr_bytes,
                          truncated, redaction_count, receipt_digest, created_at, updated_at
                   FROM command_runs WHERE owner_principal_id = ? AND run_id = ?""",
                (owner_principal_id, run_id),
            ).fetchone()
        return self._run(row) if row is not None else None

    def list_runs(
        self, owner_principal_id: str, *, session_id: str | None = None, limit: int = 100
    ) -> list[StoredCommandRun]:
        query = "SELECT * FROM command_runs WHERE owner_principal_id = ?"
        params: list[Any] = [owner_principal_id]
        if session_id is not None:
            query += " AND session_id = ?"
            params.append(session_id)
        query += " ORDER BY created_at DESC, run_id DESC LIMIT ?"
        params.append(limit)
        with self.sqlite.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._run(row) for row in rows]

    def list_recoverable(self, owner_principal_id: str) -> list[StoredCommandRun]:
        placeholders = ",".join("?" for _ in TERMINAL_COMMAND_STATES)
        terminal = [state.value for state in TERMINAL_COMMAND_STATES]
        with self.sqlite.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM command_runs WHERE owner_principal_id = ? "
                f"AND state NOT IN ({placeholders}) ORDER BY created_at ASC, run_id ASC",
                [owner_principal_id, *terminal],
            ).fetchall()
        return [self._run(row) for row in rows]

    def execution_material(self, owner_principal_id: str, run_id: str) -> dict[str, Any]:
        with self.sqlite.connect() as connection:
            row = connection.execute(
                """SELECT encrypted_execution_material FROM command_runs
                   WHERE owner_principal_id = ? AND run_id = ?""",
                (owner_principal_id, run_id),
            ).fetchone()
        if row is None:
            raise CommandStoreError("command_run_not_found")
        return self.material_cipher.decrypt(bytes(row["encrypted_execution_material"]))

    def get_receipt(self, owner_principal_id: str, run_id: str) -> CommandReceipt | None:
        with self.sqlite.connect() as connection:
            row = connection.execute(
                """SELECT receipt_json, digest FROM command_receipts
                   WHERE owner_principal_id = ? AND run_id = ?""",
                (owner_principal_id, run_id),
            ).fetchone()
        return CommandReceipt.from_json(row["receipt_json"], row["digest"]) if row else None

    def receipt_count(self, owner_principal_id: str, run_id: str) -> int:
        with self.sqlite.connect() as connection:
            row = connection.execute(
                """SELECT COUNT(*) AS count FROM command_receipts
                   WHERE owner_principal_id = ? AND run_id = ?""",
                (owner_principal_id, run_id),
            ).fetchone()
        return int(row["count"]) if row else 0

    def create_credential_delta(
        self,
        *,
        owner_principal_id: str,
        run_id: str,
        environment_profile_id: str,
        state: str,
        snapshot_handle: bytes,
        cleanup_scan_bundle: bytes,
        safe_manifest_json: str,
        delta_digest: str,
        scan_digest: str,
        scan_rule_version: str = "raiker-redaction-v1",
    ) -> None:
        if state not in {"scanning", "clean", "quarantined"}:
            raise ValueError("credential_delta_state_invalid")
        cipher = app_fernet(self.sqlite.paths.workspace_root)
        encrypted_snapshot = cipher.encrypt(snapshot_handle)
        encrypted_bundle = cipher.encrypt(cleanup_scan_bundle)
        with self.sqlite.connect() as connection:
            connection.execute(
                """INSERT INTO command_credential_deltas (
                    run_id, owner_principal_id, environment_profile_id, state,
                    encrypted_snapshot_handle, encrypted_cleanup_scan_bundle,
                    safe_manifest_json, delta_digest, scan_digest, scan_rule_version,
                    cleanup_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
                (
                    run_id,
                    owner_principal_id,
                    environment_profile_id,
                    state,
                    encrypted_snapshot,
                    encrypted_bundle,
                    safe_manifest_json,
                    delta_digest,
                    scan_digest,
                    scan_rule_version,
                    utc_now(),
                ),
            )

    def list_unresolved_deltas(
        self, owner_principal_id: str, environment_profile_id: str
    ) -> list[dict[str, Any]]:
        with self.sqlite.connect() as connection:
            rows = connection.execute(
                """SELECT run_id, owner_principal_id, environment_profile_id, state,
                          safe_manifest_json, delta_digest, scan_digest,
                          scan_rule_version, cleanup_status, created_at
                   FROM command_credential_deltas
                   WHERE owner_principal_id = ? AND environment_profile_id = ?
                     AND state NOT IN ('merged', 'discarded')
                   ORDER BY created_at ASC""",
                (owner_principal_id, environment_profile_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def resolve_credential_delta(
        self,
        owner_principal_id: str,
        run_id: str,
        *,
        decision_id: str,
        resolution: str,
    ) -> bool:
        if resolution not in {"merged", "discarded"}:
            raise ValueError("credential_delta_resolution_invalid")
        connection = self.sqlite.connect()
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        try:
            existing = connection.execute(
                "SELECT 1 FROM command_delta_receipts WHERE owner_principal_id = ? AND run_id = ?",
                (owner_principal_id, run_id),
            ).fetchone()
            if existing is not None:
                raise ReceiptImmutable("command_delta_receipt_immutable")
            row = connection.execute(
                """SELECT delta_digest, state FROM command_credential_deltas
                   WHERE owner_principal_id = ? AND run_id = ?""",
                (owner_principal_id, run_id),
            ).fetchone()
            if row is None:
                connection.rollback()
                return False
            if row["state"] in {"merged", "discarded"}:
                raise ReceiptImmutable("command_delta_receipt_immutable")
            now = utc_now()
            receipt_payload = {
                "cleanup_status": "crypto_erased",
                "decision_id": decision_id,
                "delta_digest": row["delta_digest"],
                "owner_principal_id": owner_principal_id,
                "resolution": resolution,
                "resolved_at": now,
                "run_id": run_id,
            }
            receipt_json = json.dumps(receipt_payload, sort_keys=True, separators=(",", ":"))
            receipt_digest = __import__("hashlib").sha256(receipt_json.encode()).hexdigest()
            cursor = connection.execute(
                """UPDATE command_credential_deltas
                   SET state = ?, decision_id = ?, cleanup_status = 'crypto_erased',
                       encrypted_snapshot_handle = X'', encrypted_cleanup_scan_bundle = X'',
                       resolved_at = ?
                   WHERE owner_principal_id = ? AND run_id = ?
                     AND state NOT IN ('merged', 'discarded')""",
                (resolution, decision_id, now, owner_principal_id, run_id),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                return False
            connection.execute(
                """INSERT INTO command_delta_receipts
                   (resolution_id, run_id, owner_principal_id, delta_digest,
                    receipt_json, digest, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    new_id("dres_"),
                    run_id,
                    owner_principal_id,
                    row["delta_digest"],
                    receipt_json,
                    receipt_digest,
                    now,
                ),
            )
            connection.commit()
            return True
        except BaseException:
            connection.rollback()
            raise

    def get_delta_receipt(self, owner_principal_id: str, run_id: str) -> dict[str, Any] | None:
        with self.sqlite.connect() as connection:
            row = connection.execute(
                """SELECT receipt_json, digest FROM command_delta_receipts
                   WHERE owner_principal_id = ? AND run_id = ?""",
                (owner_principal_id, run_id),
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(str(row["receipt_json"]))
        payload["digest"] = row["digest"]
        return payload

    @staticmethod
    def _run(row: Any) -> StoredCommandRun:
        return StoredCommandRun(
            run_id=row["run_id"],
            owner_principal_id=row["owner_principal_id"],
            acting_principal_id=row["acting_principal_id"],
            session_id=row["session_id"],
            turn_id=row["turn_id"],
            action_id=row["action_id"],
            state=CommandState(row["state"]),
            profile_id=row["profile_id"],
            backend=row["backend"],
            safe_display=row["safe_display"],
            template_digest=row["template_digest"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            lease_expires_at=row["lease_expires_at"],
            exit_code=row["exit_code"],
            termination_reason=row["termination_reason"],
            stdout_bytes=int(row["stdout_bytes"]),
            stderr_bytes=int(row["stderr_bytes"]),
            truncated=bool(row["truncated"]),
            redaction_count=int(row["redaction_count"]),
            receipt_digest=row["receipt_digest"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
