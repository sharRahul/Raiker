# mypy: disable-error-code="misc"
"""Model profiles, configured models, readiness, the local library and its
operations, defaults, fallbacks and the advisor (GCR-11).

One part of :class:`raiker.storage.sqlite.SQLiteStore`, which inherits it. Every method
is typed against the whole store (``self: SQLiteStore``), so a call into another
part is checked exactly as it was when every method lived in one class. mypy
reports that self-type as ``misc`` on a mixin, which is the one code this file
turns off.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from sqlcipher3 import dbapi2 as sqlite3  # type: ignore[import-untyped]

from raiker.contracts.ids import utc_now
from raiker.contracts.models import ModelProfile
from raiker.models.library import LocalModel
from raiker.models.local_operations import ModelOperation
from raiker.models.readiness import ModelReadiness, ModelReadinessKey, ModelReadinessState
from raiker.models.session_state import ModelSessionState
from raiker.models.setup import ModelSetupState, SetupState
from raiker.storage.sqlite import _OPERATION_COLUMNS

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore


class ModelStore:

    def upsert_model_profiles(self: SQLiteStore, profiles: list[ModelProfile]) -> None:
        now = utc_now()
        with self.connect() as connection:
            for profile in profiles:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO model_profiles
                    (profile_id, provider, model, build_phase, default_state, profile_json, loaded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        profile.profile_id,
                        profile.provider,
                        profile.model,
                        profile.build_phase,
                        profile.default_state,
                        json.dumps(profile.raw, sort_keys=True),
                        now,
                    ),
                )

    def load_model_setup_state(self: SQLiteStore, owner_principal_id: str) -> ModelSetupState:
        row = self._row(
            "SELECT * FROM model_setup_state WHERE owner_principal_id = ?",
            (owner_principal_id,),
        )
        if row is None:
            return ModelSetupState(owner_principal_id=owner_principal_id)
        return ModelSetupState(**dict(row))

    def save_model_operation(self: SQLiteStore, operation: ModelOperation) -> ModelOperation:
        self._execute(
            """INSERT OR REPLACE INTO model_operations
            (operation_id, owner_principal_id, kind, target, state, phase,
             progress_bytes, total_bytes, progress_percent, source_url, destination,
             error_code, error_detail, created_at, updated_at, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            tuple(operation.to_row().values()),
        )
        return operation

    def save_model_library_root(self: SQLiteStore, owner_principal_id: str, path: str) -> None:
        self._execute(
            "INSERT OR IGNORE INTO model_library_roots (owner_principal_id, path, created_at) VALUES (?, ?, ?)",
            (owner_principal_id, path, utc_now()),
        )

    def list_model_library_roots(self: SQLiteStore, owner_principal_id: str) -> list[str]:
        rows = self._rows(
            "SELECT path FROM model_library_roots WHERE owner_principal_id = ? ORDER BY path",
            (owner_principal_id,),
        )
        return [str(row["path"]) for row in rows]

    def delete_model_library_root(self: SQLiteStore, owner_principal_id: str, path: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM model_library_roots WHERE owner_principal_id = ? AND path = ?",
                (owner_principal_id, path),
            )
            connection.execute(
                "DELETE FROM local_models WHERE owner_principal_id = ? AND root_path = ?",
                (owner_principal_id, path),
            )
        return cursor.rowcount == 1

    def replace_local_models(self: SQLiteStore, owner_principal_id: str, models: list[LocalModel]) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM local_models WHERE owner_principal_id = ?", (owner_principal_id,)
            )
            connection.executemany(
                """INSERT INTO local_models
                (owner_principal_id, root_path, model_id, name, architecture, quantization,
                 primary_path, shard_count, expected_shards, complete, size_bytes, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        model.owner_principal_id,
                        model.root_path,
                        model.model_id,
                        model.name,
                        model.architecture,
                        model.quantization,
                        model.primary_path,
                        model.shard_count,
                        model.expected_shards,
                        int(model.complete),
                        model.size_bytes,
                        model.indexed_at,
                    )
                    for model in models
                ],
            )

    def list_local_models(self: SQLiteStore, owner_principal_id: str) -> list[LocalModel]:
        rows = self._rows(
            "SELECT * FROM local_models WHERE owner_principal_id = ? ORDER BY name, model_id",
            (owner_principal_id,),
        )
        return [LocalModel(**(dict(row) | {"complete": bool(row["complete"])})) for row in rows]

    def list_model_operations(self: SQLiteStore, owner_principal_id: str) -> list[ModelOperation]:
        rows = self._rows(
            "SELECT * FROM model_operations WHERE owner_principal_id = ? ORDER BY created_at DESC",
            (owner_principal_id,),
        )
        return [ModelOperation(**dict(row)) for row in rows]

    def require_model_operation(self: SQLiteStore, owner_principal_id: str, operation_id: str) -> ModelOperation:
        row = self._row(
            "SELECT * FROM model_operations WHERE owner_principal_id = ? AND operation_id = ?",
            (owner_principal_id, operation_id),
        )
        if row is None:
            raise KeyError("model_operation_not_found")
        return ModelOperation(**dict(row))

    def transition_model_operation(
        self: SQLiteStore,
        owner_principal_id: str,
        operation_id: str,
        *,
        expected_states: Sequence[str],
        **updates: Any,
    ) -> ModelOperation | None:
        """Move one operation, and only from a state the caller expected (GCR-20).

        Every lifecycle write used to be load, replace, save, so a worker that
        had already computed its progress row could store `running` over a
        cancellation the owner had asked for in between and the request was
        lost. This is the one write the lifecycle uses: an
        ``UPDATE ... WHERE state IN (...)`` that either moves the row or reports
        that somebody else moved it first. Returns the row as it now stands, or
        ``None`` when the expected state no longer held.
        """
        fields = {key: value for key, value in updates.items() if key in _OPERATION_COLUMNS}
        if not fields or not expected_states:
            return None
        fields["updated_at"] = utc_now()
        assignments = ", ".join(f"{key} = ?" for key in fields)
        placeholders = ", ".join("?" for _ in expected_states)
        with self.connect() as connection:
            cursor = connection.execute(
                f"UPDATE model_operations SET {assignments} "  # noqa: S608 -- allowlisted column names only
                f"WHERE owner_principal_id = ? AND operation_id = ? AND state IN ({placeholders})",
                (*fields.values(), owner_principal_id, operation_id, *expected_states),
            )
            if cursor.rowcount != 1:
                return None
            row = connection.execute(
                "SELECT * FROM model_operations WHERE owner_principal_id = ? AND operation_id = ?",
                (owner_principal_id, operation_id),
            ).fetchone()
        return None if row is None else ModelOperation(**dict(row))

    def update_model_operation(self: SQLiteStore, operation_id: str, **updates: Any) -> None:
        fields = {key: value for key, value in updates.items() if key in _OPERATION_COLUMNS}
        if not fields:
            return
        fields["updated_at"] = utc_now()
        assignments = ", ".join(f"{key} = ?" for key in fields)
        self._execute(
            f"UPDATE model_operations SET {assignments} WHERE operation_id = ?",
            (*fields.values(), operation_id),
        )

    def fail_running_model_operations(self: SQLiteStore) -> int:
        """Fail every non-terminal model operation. **Startup only.**

        GCR-25 — a pull, conversion or deploy is a durable row executed by an
        in-process worker. The row outlives the process; the worker does not. A
        host that stopped mid-download therefore came back reporting work that
        was still `queued` or `running` and had nobody advancing it, and the
        owner's only signal was a progress bar that never moved again.

        `queued` is included deliberately. It used to be left alone, which was
        right while a process was live — a queued row is one a dispatcher is
        about to pick up. At startup nothing has been dispatched yet, so a
        queued row is abandoned by definition and would otherwise sit there for
        the life of the install. The state named here is terminal and
        retryable, so the owner's next move is one press.
        """
        changed = self._execute(
            """UPDATE model_operations SET state = 'failed', phase = 'recovery',
            error_code = 'host_restarted', error_detail = 'The host stopped before this operation completed.',
            updated_at = ? WHERE state IN ('queued', 'running', 'cancel_requested')""",
            (utc_now(),),
        )
        return changed

    def delete_model_operation(self: SQLiteStore, owner_principal_id: str, operation_id: str) -> bool:
        changed = self._execute(
            "DELETE FROM model_operations WHERE owner_principal_id = ? AND operation_id = ?",
            (owner_principal_id, operation_id),
        )
        return changed == 1

    def save_model_setup_state(self: SQLiteStore, state: ModelSetupState) -> ModelSetupState:
        now = utc_now()
        created_at = state.created_at or now
        saved = ModelSetupState(
            owner_principal_id=state.owner_principal_id,
            status=state.status,
            step=state.step,
            path=state.path,
            selected_profile_id=state.selected_profile_id,
            selected_model=state.selected_model,
            created_at=created_at,
            updated_at=now,
        )
        self._execute(
            """INSERT OR REPLACE INTO model_setup_state
            (owner_principal_id, status, step, path, selected_profile_id, selected_model, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                saved.owner_principal_id,
                saved.status,
                saved.step,
                saved.path,
                saved.selected_profile_id,
                saved.selected_model,
                saved.created_at,
                saved.updated_at,
            ),
        )
        return saved

    def load_setup_state(self: SQLiteStore, owner_principal_id: str) -> SetupState:
        row = self._row(
            "SELECT * FROM setup_state WHERE owner_principal_id = ?",
            (owner_principal_id,),
        )
        if row is None:
            return SetupState(owner_principal_id=owner_principal_id)
        values = dict(row)
        values["model_deferred"] = bool(values["model_deferred"])
        values["background_service_enabled"] = bool(values["background_service_enabled"])
        return SetupState(**values)

    def save_setup_state(self: SQLiteStore, state: SetupState) -> SetupState:
        now = utc_now()
        saved = SetupState(
            **(state.to_dict() | {"created_at": state.created_at or now, "updated_at": now})
        )
        self._execute(
            """INSERT OR REPLACE INTO setup_state
            (owner_principal_id, status, stage, selected_profile_id, selected_model,
             model_deferred, privacy_mode, privacy_acknowledged_at, backup_mode,
             backup_target, backup_verified_at, background_service_enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                saved.owner_principal_id,
                saved.status,
                saved.stage,
                saved.selected_profile_id,
                saved.selected_model,
                int(saved.model_deferred),
                saved.privacy_mode,
                saved.privacy_acknowledged_at,
                saved.backup_mode,
                saved.backup_target,
                saved.backup_verified_at,
                int(saved.background_service_enabled),
                saved.created_at,
                saved.updated_at,
            ),
        )
        return saved

    def save_principal_model_state(self: SQLiteStore, principal_id: str, state: ModelSessionState) -> None:
        self._execute(
            """INSERT OR REPLACE INTO principal_model_control
            (principal_id, profile_id, model, reasoning_enabled, reasoning_effort, reasoning_mode,
             reasoning_budget_tokens, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                principal_id,
                state.profile_id,
                state.model,
                int(state.reasoning_enabled),
                state.reasoning_effort,
                state.reasoning_mode,
                state.reasoning_budget_tokens,
                utc_now(),
            ),
        )

    def load_principal_model_state(self: SQLiteStore, principal_id: str) -> ModelSessionState | None:
        row = self._row(
            "SELECT * FROM principal_model_control WHERE principal_id = ?",
            (principal_id,),
        )
        if row is None:
            return None
        return ModelSessionState(
            session_id=principal_id,
            profile_id=str(row["profile_id"]),
            model=str(row["model"]) if row["model"] else None,
            reasoning_enabled=bool(row["reasoning_enabled"]),
            reasoning_effort=row["reasoning_effort"],
            reasoning_mode=row["reasoning_mode"],
            reasoning_budget_tokens=row["reasoning_budget_tokens"],
        )

    def save_configured_model(self: SQLiteStore, principal_id: str, profile_id: str, model: str) -> None:
        now = utc_now()
        self._execute(
            """INSERT INTO principal_configured_models
            (principal_id, profile_id, model, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(principal_id, profile_id, model)
            DO UPDATE SET updated_at = excluded.updated_at""",
            (principal_id, profile_id, model, now, now),
        )

    def save_model_readiness(self: SQLiteStore, readiness: ModelReadiness) -> None:
        """Persist redacted reachability evidence for one exact model target."""

        def redact(value: Any) -> Any:
            if isinstance(value, dict):
                return {
                    str(key): (
                        "[redacted]"
                        if any(
                            marker in str(key).casefold()
                            for marker in (
                                "authorization",
                                "api_key",
                                "apikey",
                                "secret",
                                "token",
                                "credential",
                            )
                        )
                        else redact(item)
                    )
                    for key, item in value.items()
                }
            if isinstance(value, list):
                return [redact(item) for item in value]
            return value

        key = readiness.key
        self._execute(
            """INSERT INTO model_readiness
            (owner_principal_id, profile_id, model, endpoint_fingerprint,
             state, checked_at, expires_at, summary, reason_code, remediation, evidence_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(owner_principal_id, profile_id, model, endpoint_fingerprint)
            DO UPDATE SET state = excluded.state,
              checked_at = excluded.checked_at,
              expires_at = excluded.expires_at,
              summary = excluded.summary,
              reason_code = excluded.reason_code,
              remediation = excluded.remediation,
              evidence_json = excluded.evidence_json""",
            (
                key.owner_principal_id,
                key.profile_id,
                key.model,
                key.endpoint_fingerprint,
                readiness.state.value,
                readiness.checked_at,
                readiness.expires_at,
                readiness.summary,
                readiness.reason_code,
                readiness.remediation,
                json.dumps(redact(readiness.evidence), sort_keys=True, separators=(",", ":")),
            ),
        )

    @staticmethod
    def _model_readiness_from_row(row: sqlite3.Row) -> ModelReadiness:
        try:
            evidence = json.loads(str(row["evidence_json"]))
        except (TypeError, ValueError):
            evidence = {}
        return ModelReadiness(
            key=ModelReadinessKey(
                owner_principal_id=str(row["owner_principal_id"]),
                profile_id=str(row["profile_id"]),
                model=str(row["model"]),
                endpoint_fingerprint=str(row["endpoint_fingerprint"]),
            ),
            state=ModelReadinessState(str(row["state"])),
            checked_at=str(row["checked_at"]) if row["checked_at"] else None,
            expires_at=str(row["expires_at"]) if row["expires_at"] else None,
            summary=str(row["summary"]),
            reason_code=str(row["reason_code"]),
            remediation=str(row["remediation"]),
            evidence=evidence if isinstance(evidence, dict) else {},
        )

    def load_model_readiness(self: SQLiteStore, key: ModelReadinessKey) -> ModelReadiness | None:
        row = self._row(
            """SELECT * FROM model_readiness
            WHERE owner_principal_id = ? AND profile_id = ? AND model = ?
              AND endpoint_fingerprint = ?""",
            (
                key.owner_principal_id,
                key.profile_id,
                key.model,
                key.endpoint_fingerprint,
            ),
        )
        return self._model_readiness_from_row(row) if row is not None else None

    def list_model_readiness(
        self: SQLiteStore,
        owner_principal_id: str,
        profile_id: str | None = None,
    ) -> list[ModelReadiness]:
        query = "SELECT * FROM model_readiness WHERE owner_principal_id = ?"
        params: list[str] = [owner_principal_id]
        if profile_id is not None:
            query += " AND profile_id = ?"
            params.append(profile_id)
        query += " ORDER BY profile_id, model, endpoint_fingerprint"
        rows = self._rows(query, params)
        return [self._model_readiness_from_row(row) for row in rows]

    def invalidate_model_readiness(
        self: SQLiteStore,
        owner_principal_id: str,
        profile_id: str,
        *,
        reason_code: str = "readiness_invalidated",
    ) -> int:
        affected = self._execute(
            """UPDATE model_readiness
            SET state = ?, expires_at = ?, reason_code = ?,
                summary = ?, remediation = ?
            WHERE owner_principal_id = ? AND profile_id = ?""",
            (
                ModelReadinessState.STALE.value,
                utc_now(),
                reason_code,
                "This model connection must be checked again.",
                "Check this model again before sending.",
                owner_principal_id,
                profile_id,
            ),
        )
        return affected

    def save_surface_model_default(
        self: SQLiteStore, principal_id: str, surface: str, profile_id: str, model: str
    ) -> None:
        """Remember which model a work surface should start on.

        A preference, not an authority: the turn this produces still carries an
        explicit profile and model, and the readiness gate judges that pair.
        """
        self._execute(
            """INSERT OR REPLACE INTO principal_surface_models
            (principal_id, surface, profile_id, model, updated_at)
            VALUES (?, ?, ?, ?, ?)""",
            (principal_id, surface, profile_id, model, utc_now()),
        )

    def load_surface_model_default(self: SQLiteStore, principal_id: str, surface: str) -> tuple[str, str] | None:
        """The surface's default, or None when it has no opinion of its own."""
        row = self._row(
            """SELECT profile_id, model FROM principal_surface_models
            WHERE principal_id = ? AND surface = ?""",
            (principal_id, surface),
        )
        return None if row is None else (str(row["profile_id"]), str(row["model"]))

    def list_surface_model_defaults(self: SQLiteStore, principal_id: str) -> list[tuple[str, str, str]]:
        rows = self._rows(
            """SELECT surface, profile_id, model FROM principal_surface_models
            WHERE principal_id = ? ORDER BY surface""",
            (principal_id,),
        )
        return [(str(row["surface"]), str(row["profile_id"]), str(row["model"])) for row in rows]

    def clear_surface_model_default(self: SQLiteStore, principal_id: str, surface: str) -> None:
        self._execute(
            "DELETE FROM principal_surface_models WHERE principal_id = ? AND surface = ?",
            (principal_id, surface),
        )

    #
    # Whether a local model runtime exists on this machine is a fact about the
    # host, not about a principal, so these rows are not owner-scoped.  They are
    # written by an explicit detection pass and only ever read back here, which
    # is what lets a status read answer "is Ollama installed" without a probe.

    def save_local_runtime_presence(
        self: SQLiteStore, runtime: str, *, present: bool, executable: str | None
    ) -> None:
        self._execute(
            """INSERT INTO local_runtime_presence
            (runtime, present, executable, detected_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(runtime) DO UPDATE SET
              present = excluded.present,
              executable = excluded.executable,
              detected_at = excluded.detected_at""",
            (runtime, 1 if present else 0, executable, utc_now()),
        )

    def load_local_runtime_presence(self: SQLiteStore) -> dict[str, dict[str, Any]]:
        """Every detection result on record, keyed by runtime name.

        A runtime absent from this mapping has never been detected, which is a
        third answer distinct from present and absent: nothing has looked yet.
        """
        rows = self._rows(
            "SELECT runtime, present, executable, detected_at FROM local_runtime_presence",
        )
        return {
            str(row["runtime"]): {
                "present": bool(row["present"]),
                "executable": (str(row["executable"]) if row["executable"] else None),
                "detected_at": str(row["detected_at"]),
            }
            for row in rows
        }

    def list_configured_models(self: SQLiteStore, principal_id: str) -> list[tuple[str, str]]:
        rows = self._rows(
            """SELECT profile_id, model FROM principal_configured_models
            WHERE principal_id = ?
            ORDER BY created_at, profile_id, model""",
            (principal_id,),
        )
        return [(str(row["profile_id"]), str(row["model"])) for row in rows]

    def set_configured_models(
        self: SQLiteStore, principal_id: str, profile_id: str, models: list[str], *, keep: str | None = None
    ) -> list[str]:
        """Replace the models this owner keeps available for one profile.

        A model became "configured" only by being selected as the default, so a
        provider serving six models could offer exactly one of them to a picker
        and the owner had to go back to Models to swap. This is the same list,
        written directly: everything named here stays offered, everything else
        for this profile stops being.

        ``keep`` is the model the owner currently has selected. Removing it here
        would leave the selection pointing at something no list mentions, so it
        is retained whatever the request says.
        """
        wanted: list[str] = []
        for model in [*models, *( [keep] if keep else [] )]:
            trimmed = model.strip()
            if trimmed and trimmed not in wanted:
                wanted.append(trimmed)
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM principal_configured_models WHERE principal_id = ? AND profile_id = ?",
                (principal_id, profile_id),
            )
            connection.executemany(
                """INSERT INTO principal_configured_models
                (principal_id, profile_id, model, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)""",
                [(principal_id, profile_id, model, now, now) for model in wanted],
            )
        return wanted

    def save_provider_catalogue(
        self: SQLiteStore, principal_id: str, profile_id: str, models: list[str]
    ) -> list[str]:
        """Record what a provider published, so the next failure is not a loss.

        A catalogue was probed on demand and never written
        down, so a provider that was briefly unreachable made its models vanish
        from every picker — the only copy was the one in flight. This is the
        last answer the provider actually gave, in the order it gave it.

        An empty listing is *not* written. A provider returning nothing is
        indistinguishable here from one that failed in a way the caller did not
        classify, and replacing a known catalogue with emptiness is exactly the
        disappearance this exists to prevent.
        """
        wanted: list[str] = []
        for model in models:
            trimmed = model.strip()
            if trimmed and trimmed not in wanted:
                wanted.append(trimmed)
        if not wanted:
            return self.list_provider_catalogue(principal_id, profile_id)
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM principal_provider_catalogue "
                "WHERE principal_id = ? AND profile_id = ?",
                (principal_id, profile_id),
            )
            connection.executemany(
                """INSERT INTO principal_provider_catalogue
                (principal_id, profile_id, model, position, listed_at)
                VALUES (?, ?, ?, ?, ?)""",
                [
                    (principal_id, profile_id, model, position, now)
                    for position, model in enumerate(wanted)
                ],
            )
        return wanted

    def list_provider_catalogue(self: SQLiteStore, principal_id: str, profile_id: str) -> list[str]:
        """The last catalogue this provider published, in its own order."""
        rows = self._rows(
            """SELECT model FROM principal_provider_catalogue
            WHERE principal_id = ? AND profile_id = ?
            ORDER BY position""",
            (principal_id, profile_id),
        )
        return [str(row[0]) for row in rows]

    def provider_catalogue_listed_at(self: SQLiteStore, principal_id: str, profile_id: str) -> str | None:
        """When the stored catalogue was published, or ``None`` when there is none.

        The age is the point: a picker may offer a remembered catalogue, but it
        must be able to say the answer is remembered rather than current.
        """
        row = self._row(
            """SELECT listed_at FROM principal_provider_catalogue
            WHERE principal_id = ? AND profile_id = ? LIMIT 1""",
            (principal_id, profile_id),
        )
        return str(row[0]) if row is not None else None

    def forget_provider_catalogue(self: SQLiteStore, principal_id: str, profile_id: str) -> int:
        """Drop what one provider published, and say how many rows went.

        The counterpart to :meth:`save_provider_catalogue`, and the reason it
        exists: a remembered catalogue is right for a provider that is briefly
        unreachable and wrong for one the owner has disconnected. Without this,
        removing a credential left that account's models in every picker — a
        list Raiker can no longer reach, presented exactly like one it can,
        which is the disappearance defect pointing the other way.
        """
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM principal_provider_catalogue "
                "WHERE principal_id = ? AND profile_id = ?",
                (principal_id, profile_id),
            )
            return int(cursor.rowcount or 0)

    def is_configured_model(self: SQLiteStore, principal_id: str, profile_id: str, model: str) -> bool:
        row = self._row(
            """SELECT 1 FROM principal_configured_models
            WHERE principal_id = ? AND profile_id = ? AND model = ?""",
            (principal_id, profile_id, model),
        )
        return row is not None

    def save_model_fallback_sequence(self: SQLiteStore, session_id: str, profile_ids: list[str]) -> None:
        """Persist the ordered, user-owned model fallback sequence for ``session_id``.

        The list is stored verbatim (deduplication/validation is the caller's job).
        An empty list clears the sequence.
        """
        self._execute(
            """
            INSERT OR REPLACE INTO model_fallback_sequence
            (session_id, profile_ids_json, updated_at)
            VALUES (?, ?, ?)
            """,
            (session_id, json.dumps(list(profile_ids)), utc_now()),
        )

    def load_model_fallback_sequence(self: SQLiteStore, session_id: str) -> list[str]:
        """Return the ordered fallback profile ids for ``session_id`` ([] if unset)."""
        row = self._row(
            "SELECT profile_ids_json FROM model_fallback_sequence WHERE session_id = ?",
            (session_id,),
        )
        if row is None:
            return []
        try:
            value = json.loads(row["profile_ids_json"])
        except (ValueError, TypeError):
            return []
        return [str(item) for item in value] if isinstance(value, list) else []

    def save_principal_model_fallback_sequence(
        self: SQLiteStore, principal_id: str, profile_ids: list[str]
    ) -> None:
        self._execute(
            """INSERT OR REPLACE INTO principal_model_fallback_sequence
            (principal_id, profile_ids_json, updated_at) VALUES (?, ?, ?)""",
            (principal_id, json.dumps(list(profile_ids)), utc_now()),
        )

    def load_principal_model_fallback_sequence(self: SQLiteStore, principal_id: str) -> list[str]:
        row = self._row(
            "SELECT profile_ids_json FROM principal_model_fallback_sequence WHERE principal_id = ?",
            (principal_id,),
        )
        try:
            value = json.loads(row["profile_ids_json"]) if row else []
        except (TypeError, ValueError):
            value = []
        return [str(item) for item in value] if isinstance(value, list) else []

    def save_model_advisor(self: SQLiteStore, session_id: str, profile_id: str | None) -> None:
        """Persist the user-owned advisor model profile id (None/empty clears it).

        Storing the id grants nothing — the consult path is gated by the
        ``advisor_model_runtime`` capability, its decision mode, and provider
        policy at call time. Validation is the caller's job.
        """
        with self.connect() as connection:
            if not profile_id:
                connection.execute("DELETE FROM model_advisor WHERE session_id = ?", (session_id,))
                return
            connection.execute(
                """
                INSERT OR REPLACE INTO model_advisor (session_id, profile_id, updated_at)
                VALUES (?, ?, ?)
                """,
                (session_id, profile_id, utc_now()),
            )

    def load_model_advisor(self: SQLiteStore, session_id: str) -> str | None:
        """Return the persisted advisor profile id for ``session_id`` (None if unset)."""
        row = self._row("SELECT profile_id FROM model_advisor WHERE session_id = ?", (session_id,))
        return str(row["profile_id"]) if row is not None else None

    def save_principal_model_advisor(self: SQLiteStore, principal_id: str, profile_id: str | None) -> None:
        with self.connect() as connection:
            if not profile_id:
                connection.execute(
                    "DELETE FROM principal_model_advisor WHERE principal_id = ?", (principal_id,)
                )
                return
            connection.execute(
                """INSERT OR REPLACE INTO principal_model_advisor (principal_id, profile_id, updated_at)
                VALUES (?, ?, ?)""",
                (principal_id, profile_id, utc_now()),
            )

    def load_principal_model_advisor(self: SQLiteStore, principal_id: str) -> str | None:
        row = self._row(
            "SELECT profile_id FROM principal_model_advisor WHERE principal_id = ?",
            (principal_id,),
        )
        return str(row["profile_id"]) if row is not None else None
