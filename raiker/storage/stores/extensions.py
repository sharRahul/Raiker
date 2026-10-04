# mypy: disable-error-code="misc"
"""MCP server profiles, skills, plugins, channels, connector profiles and
telemetry destinations (GCR-11).

One part of :class:`raiker.storage.sqlite.SQLiteStore`, which inherits it. Every method
is typed against the whole store (``self: SQLiteStore``), so a call into another
part is checked exactly as it was when every method lived in one class. mypy
reports that self-type as ``misc`` on a mixin, which is the one code this file
turns off.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

from sqlcipher3 import dbapi2 as sqlite3  # type: ignore[import-untyped]

from raiker.contracts.ids import utc_now
from raiker.contracts.models import (
    ChannelPairing,
    ConnectorProfile,
    PluginExecutionRecord,
    PluginInstallRecord,
    SkillCandidate,
)
from raiker.tools.mcp_review import decode_approved, fingerprints, settle_approved

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore


def _json_list(raw: Any) -> list[Any]:
    """A stored JSON array column, or an empty list for anything else."""
    try:
        value = json.loads(raw) if isinstance(raw, str) else []
    except (TypeError, ValueError):
        return []
    return value if isinstance(value, list) else []


class ExtensionStore:

    # Every row is owner-scoped by ``principal_id``: an account can only list,
    # resolve, or mutate the MCP servers it created. ``command`` is stored as a
    # JSON argv array (interpreter + workspace-relative script) — never a secret
    # and never a remote endpoint. Reads decode it back to a list.

    @staticmethod
    def _mcp_row(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        for key in ("command", "tools", "tool_schemas", "server_features"):
            raw = data.get(key)
            try:
                data[key] = json.loads(raw) if isinstance(raw, str) else []
            except (TypeError, ValueError):
                data[key] = []
        return data

    def create_mcp_server(
        self: SQLiteStore,
        *,
        server_id: str,
        principal_id: str,
        name: str,
        command: list[str],
        template: str | None = None,
        transport: str = "stdio",
        status: str = "created",
        last_connected_at: str | None = None,
        tools: list[str] | None = None,
        tool_schemas: list[dict[str, Any]] | None = None,
        server_features: list[str] | None = None,
        endpoint_url: str | None = None,
        auth_ref: str | None = None,
        protocol_version: str | None = None,
    ) -> str:
        """Upsert one owner-scoped MCP server profile.

        Keyed by ``server_id`` (INSERT OR REPLACE), and additionally unique per
        ``(principal_id, name)`` so re-building the same-named server for the
        same owner refreshes the single profile instead of accumulating rows.
        ``tools`` is the JSON-encoded list of tool names from the last successful
        handshake (names only — never arguments or output). ``endpoint_url`` is
        the remote HTTP URL for an ``http`` transport; ``auth_ref`` names where
        the owner token lives (never the token itself).
        """
        tool_list = list(tools) if tools is not None else None
        declarations = list(tool_schemas) if tool_schemas is not None else None
        self._execute(
            """INSERT OR REPLACE INTO mcp_servers
               (server_id, principal_id, name, command, template, transport,
                status, created_at, last_connected_at, tools, tool_count,
                endpoint_url, auth_ref, protocol_version, tool_schemas,
                server_features)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                server_id,
                principal_id,
                name,
                json.dumps(list(command)),
                template,
                transport,
                status,
                utc_now(),
                last_connected_at,
                json.dumps(tool_list) if tool_list is not None else None,
                len(tool_list) if tool_list is not None else 0,
                endpoint_url,
                auth_ref,
                protocol_version,
                json.dumps(declarations) if declarations is not None else None,
                json.dumps(list(server_features)) if server_features is not None else None,
            ),
        )
        return server_id

    def update_mcp_server_runtime(
        self: SQLiteStore,
        server_id: str,
        principal_id: str,
        *,
        status: str,
        tools: list[str] | None = None,
        tool_schemas: list[dict[str, Any]] | None = None,
        server_features: list[str] | None = None,
        last_connected_at: str | None = None,
        protocol_version: str | None = None,
    ) -> bool:
        """Owner-scoped update of only the *runtime* fields of a profile — status,
        discovered tool names, and last-connected time — without touching its
        identity/transport/endpoint columns (so a re-test never wipes a stored
        remote endpoint or auth reference). Returns False if the row is missing
        or owned by another principal.

        ``tools=None`` means "this operation discovered nothing", not "this
        server has no tools": a `tools/call` session never enumerates, so it
        leaves the stored list alone. Overwriting it emptied the profile after
        every call — visible as `TOOLS (0)` on a connected server, and fatal to
        the projected tool set, which is built from exactly that list (BUG-12).
        """
        tool_list = list(tools) if tools is not None else None
        declarations = list(tool_schemas) if tool_schemas is not None else None
        with self.connect() as connection:
            approved_json: str | None = None
            if tool_list is not None:
                # DEC-15 step 10 — an enumeration never widens what the owner
                # accepted; it only fills in the record the first time
                # (`raiker.tools.mcp_review.settle_approved`).
                previous = connection.execute(
                    "SELECT tools, tool_schemas, approved_tools FROM mcp_servers "
                    "WHERE server_id = ? AND principal_id = ?",
                    (server_id, principal_id),
                ).fetchone()
                if previous is not None:
                    approved_json = json.dumps(
                        settle_approved(
                            decode_approved(previous["approved_tools"]),
                            previous_tools=_json_list(previous["tools"]),
                            previous_schemas=_json_list(previous["tool_schemas"]),
                            tools=tool_list,
                            tool_schemas=declarations,
                        ),
                        sort_keys=True,
                    )
            cursor = connection.execute(
                """UPDATE mcp_servers
                   SET status = ?,
                       last_connected_at = ?,
                       tools = COALESCE(?, tools),
                       tool_count = COALESCE(?, tool_count),
                       tool_schemas = COALESCE(?, tool_schemas),
                       server_features = COALESCE(?, server_features),
                       protocol_version = COALESCE(?, protocol_version),
                       approved_tools = COALESCE(?, approved_tools)
                   WHERE server_id = ? AND principal_id = ?""",
                (
                    status,
                    last_connected_at,
                    json.dumps(tool_list) if tool_list is not None else None,
                    len(tool_list) if tool_list is not None else None,
                    json.dumps(declarations) if declarations is not None else None,
                    json.dumps(list(server_features)) if server_features is not None else None,
                    protocol_version,
                    approved_json,
                    server_id,
                    principal_id,
                ),
            )
            return cursor.rowcount > 0

    def approve_mcp_tools(
        self: SQLiteStore, server_id: str, principal_id: str, names: Sequence[str]
    ) -> list[str] | None:
        """Accept ``names`` as this server declares them now (DEC-15 step 10).

        Owner-scoped. Returns the names that were held and are now accepted —
        a name the server does not offer, or one already accepted as it is, is
        not in the answer — or ``None`` when the profile is not the caller's.
        """
        with self.connect() as connection:
            row = connection.execute(
                "SELECT tools, tool_schemas, approved_tools FROM mcp_servers "
                "WHERE server_id = ? AND principal_id = ?",
                (server_id, principal_id),
            ).fetchone()
            if row is None:
                return None
            current = fingerprints(_json_list(row["tools"]), _json_list(row["tool_schemas"]))
            approved = decode_approved(row["approved_tools"])
            record = dict(current if approved is None else approved)
            accepted = sorted(
                name for name in set(names) if name in current and record.get(name) != current[name]
            )
            for name in accepted:
                record[name] = current[name]
            connection.execute(
                "UPDATE mcp_servers SET approved_tools = ? WHERE server_id = ? AND principal_id = ?",
                (json.dumps(record, sort_keys=True), server_id, principal_id),
            )
            return accepted

    def rename_mcp_server(self: SQLiteStore, server_id: str, principal_id: str, name: str) -> bool:
        """Owner-scoped rename of one MCP server profile. Returns False if the
        row is missing / owned by another principal, or if the new name is
        already taken by another of the caller's servers (unique per owner)."""
        with self.connect() as connection:
            clash = connection.execute(
                "SELECT 1 FROM mcp_servers WHERE principal_id = ? AND name = ? AND server_id != ?",
                (principal_id, name, server_id),
            ).fetchone()
            if clash is not None:
                return False
            cursor = connection.execute(
                "UPDATE mcp_servers SET name = ? WHERE server_id = ? AND principal_id = ?",
                (name, server_id, principal_id),
            )
            return cursor.rowcount > 0

    def delete_mcp_server(self: SQLiteStore, server_id: str, principal_id: str) -> bool:
        """Owner-scoped delete of one MCP server profile. Returns False if the
        row is missing or owned by another principal (isolation)."""
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM mcp_servers WHERE server_id = ? AND principal_id = ?",
                (server_id, principal_id),
            )
            return cursor.rowcount > 0

    def list_mcp_servers(self: SQLiteStore, principal_id: str) -> list[dict[str, Any]]:
        rows = self._rows(
            "SELECT * FROM mcp_servers WHERE principal_id = ? ORDER BY created_at DESC",
            (principal_id,),
        )
        return [self._mcp_row(row) for row in rows]

    def get_mcp_server(self: SQLiteStore, server_id: str, principal_id: str) -> dict[str, Any] | None:
        row = self._row(
            "SELECT * FROM mcp_servers WHERE server_id = ? AND principal_id = ?",
            (server_id, principal_id),
        )
        return self._mcp_row(row) if row else None

    def get_mcp_server_by_name(self: SQLiteStore, principal_id: str, name: str) -> dict[str, Any] | None:
        row = self._row(
            "SELECT * FROM mcp_servers WHERE principal_id = ? AND name = ?",
            (principal_id, name),
        )
        return self._mcp_row(row) if row else None

    def set_mcp_server_status(
        self: SQLiteStore,
        server_id: str,
        principal_id: str,
        status: str,
        last_connected_at: str | None = None,
    ) -> bool:
        """Owner-scoped status update. Returns False if the row is missing or is
        owned by another principal (isolation), so a status write can never
        touch another owner's server."""
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE mcp_servers SET status = ?, last_connected_at = ?
                   WHERE server_id = ? AND principal_id = ?""",
                (status, last_connected_at, server_id, principal_id),
            )
            return cursor.rowcount > 0


    @staticmethod
    def _skill_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        data = dict(row)
        raw = data.get("files_json")
        try:
            data["files"] = json.loads(raw) if isinstance(raw, str) else []
        except (TypeError, ValueError):
            data["files"] = []
        data["active"] = bool(data.get("active", 0))
        return data

    def upsert_skill(
        self: SQLiteStore,
        *,
        skill_id: str,
        principal_id: str,
        name: str,
        description: str,
        checksum: str,
        skill_md: str,
        source: str,
        source_ref: str | None = None,
        version: str | None = None,
        bundle: bytes | None = None,
        files: list[str] | None = None,
        byte_size: int = 0,
        active: bool = True,
    ) -> str:
        """Insert or refresh one owner-scoped skill, keyed by ``(owner, name)``.

        Re-importing the same skill replaces the stored document in place — its
        ``skill_id``, its created-at, and the owner's active/inactive choice all
        survive the refresh, so an update never silently re-enables a skill the
        owner had turned off.
        """
        now = utc_now()
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT skill_id, created_at, active, command_trigger FROM skills "
                "WHERE principal_id = ? AND name = ?",
                (principal_id, name),
            ).fetchone()
            resolved_id = str(existing["skill_id"]) if existing else skill_id
            created_at = str(existing["created_at"]) if existing else now
            resolved_active = bool(existing["active"]) if existing else active
            command_trigger = existing["command_trigger"] if existing else None
            connection.execute(
                """INSERT OR REPLACE INTO skills
                   (skill_id, principal_id, name, description, version, source, source_ref,
                    checksum, active, skill_md, bundle, files_json, byte_size,
                    created_at, updated_at, command_trigger)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    resolved_id,
                    principal_id,
                    name,
                    description,
                    version,
                    source,
                    source_ref,
                    checksum,
                    1 if resolved_active else 0,
                    skill_md,
                    bundle,
                    json.dumps(list(files or [])),
                    int(byte_size),
                    created_at,
                    now,
                    command_trigger,
                ),
            )
        return resolved_id

    def list_skills(self: SQLiteStore, principal_id: str) -> list[dict[str, Any]]:
        """Owner-scoped list, newest first. Bundles are excluded — the archive is
        only read on an explicit download."""
        rows = self._rows(
            """SELECT skill_id, principal_id, name, description, version, source,
                      source_ref, checksum, active, skill_md, files_json, byte_size,
                      created_at, updated_at, command_trigger
               FROM skills WHERE principal_id = ? ORDER BY created_at DESC""",
            (principal_id,),
        )
        return [row for row in (self._skill_row(r) for r in rows) if row is not None]

    def get_skill(self: SQLiteStore, skill_id: str, principal_id: str) -> dict[str, Any] | None:
        row = self._row(
            "SELECT * FROM skills WHERE skill_id = ? AND principal_id = ?",
            (skill_id, principal_id),
        )
        return self._skill_row(row)

    def get_skill_by_name(self: SQLiteStore, principal_id: str, name: str) -> dict[str, Any] | None:
        row = self._row(
            "SELECT * FROM skills WHERE principal_id = ? AND name = ?",
            (principal_id, name),
        )
        return self._skill_row(row)

    def rename_skill(self: SQLiteStore, skill_id: str, principal_id: str, name: str) -> bool:
        """Owner-scoped rename. False when the row is missing, owned by another
        principal, or the new name is already taken by another of the owner's
        skills (names are the prompt handle, so they stay unique per owner)."""
        with self.connect() as connection:
            clash = connection.execute(
                "SELECT 1 FROM skills WHERE principal_id = ? AND name = ? AND skill_id != ?",
                (principal_id, name, skill_id),
            ).fetchone()
            if clash is not None:
                return False
            cursor = connection.execute(
                "UPDATE skills SET name = ?, updated_at = ? WHERE skill_id = ? AND principal_id = ?",
                (name, utc_now(), skill_id, principal_id),
            )
            return cursor.rowcount > 0

    def set_skill_active(self: SQLiteStore, skill_id: str, principal_id: str, active: bool) -> bool:
        """Owner-scoped activate/deactivate. A deactivated skill stays stored but
        is withheld from every turn's context."""
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE skills SET active = ?, updated_at = ? WHERE skill_id = ? AND principal_id = ?",
                (1 if active else 0, utc_now(), skill_id, principal_id),
            )
            return cursor.rowcount > 0

    def seeded_skill_names(self: SQLiteStore, principal_id: str) -> set[str]:
        """Shipped skills this owner has already been offered, installed or not."""
        rows = self._rows("SELECT name FROM skill_seeds WHERE principal_id = ?", (principal_id,))
        return {str(row["name"]) for row in rows}

    def record_skill_seed(self: SQLiteStore, principal_id: str, name: str) -> None:
        self._execute(
            "INSERT OR IGNORE INTO skill_seeds (principal_id, name, seeded_at) VALUES (?, ?, ?)",
            (principal_id, name, utc_now()),
        )

    def delete_skill(self: SQLiteStore, skill_id: str, principal_id: str) -> bool:
        """Owner-scoped delete. False when the row is missing or owned by another
        principal (isolation)."""
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM skills WHERE skill_id = ? AND principal_id = ?",
                (skill_id, principal_id),
            )
            return cursor.rowcount > 0

    def has_connector_credential(self: SQLiteStore, principal_id: str, connector_id: str) -> bool:
        row = self._row(
            "SELECT 1 FROM connector_credentials WHERE principal_id = ? AND connector_id = ?",
            (principal_id, connector_id),
        )
        return row is not None

    def upsert_connector_profiles(self: SQLiteStore, profiles: list[ConnectorProfile]) -> None:
        now = utc_now()
        with self.connect() as connection:
            for profile in profiles:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO connector_profiles
                    (connector_id, channel_type, display_name, build_phase, default_state, interface_status, profile_json, loaded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        profile.connector_id,
                        profile.channel_type,
                        profile.display_name,
                        profile.build_phase,
                        profile.default_state,
                        profile.interface_status,
                        json.dumps(profile.raw, sort_keys=True),
                        now,
                    ),
                )

    #
    # Owner-scoped rows describing where governed events may be exported to.
    # A row holds an endpoint, the *name* of the environment variable an auth
    # header lives in, whether the owner opted into content, and how far the
    # export has got. It never holds a credential, and never holds an event.

    def create_telemetry_destination(
        self: SQLiteStore,
        *,
        destination_id: str,
        principal_id: str,
        name: str,
        endpoint_url: str,
        header_ref: str | None = None,
        include_content: bool = False,
    ) -> str:
        self._execute(
            """INSERT INTO telemetry_destinations
               (destination_id, principal_id, name, endpoint_url, header_ref,
                include_content, enabled, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
            (
                destination_id,
                principal_id,
                name,
                endpoint_url,
                header_ref,
                1 if include_content else 0,
                utc_now(),
            ),
        )
        return destination_id

    @staticmethod
    def _telemetry_row(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["include_content"] = bool(data.get("include_content", 0))
        data["enabled"] = bool(data.get("enabled", 1))
        # BUG-276 — a row written before the cadence column existed reads as
        # `off`, which is what it was: on demand only.
        data["delivery_cadence"] = str(data.get("delivery_cadence") or "off")
        return data

    def list_telemetry_destinations(self: SQLiteStore, principal_id: str) -> list[dict[str, Any]]:
        rows = self._rows(
            "SELECT * FROM telemetry_destinations WHERE principal_id = ?"
            " ORDER BY created_at DESC",
            (principal_id,),
        )
        return [self._telemetry_row(row) for row in rows]

    def get_telemetry_destination(
        self: SQLiteStore, destination_id: str, principal_id: str
    ) -> dict[str, Any] | None:
        row = self._row(
            "SELECT * FROM telemetry_destinations"
            " WHERE destination_id = ? AND principal_id = ?",
            (destination_id, principal_id),
        )
        return self._telemetry_row(row) if row else None

    def set_telemetry_destination_enabled(
        self: SQLiteStore, destination_id: str, principal_id: str, enabled: bool
    ) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE telemetry_destinations SET enabled = ?"
                " WHERE destination_id = ? AND principal_id = ?",
                (1 if enabled else 0, destination_id, principal_id),
            )
            return cursor.rowcount > 0

    def set_telemetry_destination_cadence(
        self: SQLiteStore,
        destination_id: str,
        principal_id: str,
        *,
        cadence: str,
        next_delivery_at: str | None,
    ) -> bool:
        """BUG-276 — how often this destination is delivered to, and when next.

        Both fields move together on purpose. A cadence with no next run would
        never fire, and a next run with no cadence would fire once and stop; a
        card that reads "every hour" has to be backed by a claim the host can
        actually see.
        """
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE telemetry_destinations"
                " SET delivery_cadence = ?, next_delivery_at = ?"
                " WHERE destination_id = ? AND principal_id = ?",
                (cadence, next_delivery_at, destination_id, principal_id),
            )
            return cursor.rowcount > 0

    def claim_due_telemetry_destinations(
        self: SQLiteStore,
        now: str,
        next_delivery_at: Callable[[dict[str, Any]], str],
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Atomically claim the destinations whose next delivery is due.

        The same shape as :meth:`claim_due_tasks`, and for the same reason: the
        host runs a tick worker and a nudged worker, and two of them seeing one
        due destination must not produce two deliveries. The claim *is* the
        advance — the row's next run moves forward inside the same statement
        that selects it, conditioned on the value that was read — so the loser
        of a race finds nothing to claim rather than sending a duplicate.

        ``next_delivery_at`` is passed in rather than computed here because the
        interval table belongs to the scheduler, not to storage.
        """
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM telemetry_destinations"
                " WHERE enabled = 1 AND delivery_cadence != 'off'"
                " AND next_delivery_at IS NOT NULL AND next_delivery_at <= ?"
                " ORDER BY next_delivery_at ASC LIMIT ?",
                (now, limit),
            ).fetchall()
            claimed: list[dict[str, Any]] = []
            for row in rows:
                record = self._telemetry_row(row)
                due = str(record["next_delivery_at"])
                if connection.execute(
                    "UPDATE telemetry_destinations SET next_delivery_at = ?"
                    " WHERE destination_id = ? AND next_delivery_at = ?",
                    (next_delivery_at(record), record["destination_id"], due),
                ).rowcount:
                    claimed.append(record)
        return claimed

    def delete_telemetry_destination(self: SQLiteStore, destination_id: str, principal_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM telemetry_destinations"
                " WHERE destination_id = ? AND principal_id = ?",
                (destination_id, principal_id),
            )
            return cursor.rowcount > 0

    def record_telemetry_attempt(
        self: SQLiteStore,
        destination_id: str,
        principal_id: str,
        *,
        status: str,
        exported: int = 0,
        cursor_timestamp: str | None = None,
        cursor_event_id: str | None = None,
        cursor_seq: int | None = None,
    ) -> bool:
        """Record the outcome of one export run.

        The cursor only moves on a delivery that actually landed, so a failed
        run re-sends rather than skipping the events it could not deliver.
        """
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE telemetry_destinations
                   SET last_status = ?,
                       last_attempt_at = ?,
                       exported_count = exported_count + ?,
                       cursor_timestamp = COALESCE(?, cursor_timestamp),
                       cursor_event_id = COALESCE(?, cursor_event_id),
                       cursor_seq = COALESCE(?, cursor_seq)
                   WHERE destination_id = ? AND principal_id = ?""",
                (
                    status,
                    utc_now(),
                    max(0, exported),
                    cursor_timestamp,
                    cursor_event_id,
                    cursor_seq,
                    destination_id,
                    principal_id,
                ),
            )
            return cursor.rowcount > 0

    def insert_plugin_install_record(self: SQLiteStore, record: PluginInstallRecord) -> None:
        self._execute(
            """
            INSERT OR REPLACE INTO plugin_install_records
            (record_id, plugin_id, version, trust_level, checksum, signature, source_url, commit_sha, permissions_json, status, installed_at, installed_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.record_id,
                record.plugin_id,
                record.version,
                record.trust_level,
                record.checksum,
                record.signature,
                record.source_url,
                record.commit_sha,
                record.permissions_json,
                record.status,
                record.installed_at,
                record.installed_by,
            ),
        )

    def list_plugin_install_records(self: SQLiteStore, status: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM plugin_install_records"
        params: list[Any] = []
        if status is not None:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY installed_at DESC"
        rows = self._rows(query, params)
        return [dict(row) for row in rows]

    def load_plugin_install_record(self: SQLiteStore, record_id: str) -> dict[str, Any] | None:
        row = self._row("SELECT * FROM plugin_install_records WHERE record_id = ?", (record_id,))
        return dict(row) if row else None

    def revoke_plugin_install_record(self: SQLiteStore, record_id: str) -> bool:
        """Flip an install record's status from ``installed`` to ``revoked``.

        Returns True only if a currently-installed record was updated. This is
        the fail-closed off-switch for the plugin install/execution slices; it
        never deletes the record or touches permissions.
        """
        changed = self._execute(
            "UPDATE plugin_install_records SET status = 'revoked' "
            "WHERE record_id = ? AND status = 'installed'",
            (record_id,),
        )
        return changed > 0


    def insert_channel_pairing(self: SQLiteStore, pairing: ChannelPairing) -> None:
        self._execute(
            """
            INSERT OR REPLACE INTO channel_pairings
            (pairing_id, connector_id, channel_type, display_name, paired_at, paired_by, enabled, sender_allowlist_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pairing.pairing_id,
                pairing.connector_id,
                pairing.channel_type,
                pairing.display_name,
                pairing.paired_at,
                pairing.paired_by,
                int(pairing.enabled),
                pairing.sender_allowlist_json,
            ),
        )

    def list_channel_pairings(self: SQLiteStore, enabled_only: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM channel_pairings"
        params: list[Any] = []
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY paired_at DESC"
        rows = self._rows(query, params)
        return [dict(row) for row in rows]

    def get_channel_pairing(self: SQLiteStore, pairing_id: str) -> dict[str, Any] | None:
        row = self._row("SELECT * FROM channel_pairings WHERE pairing_id = ?", (pairing_id,))
        return dict(row) if row is not None else None

    def get_channel_pairing_by_connector(self: SQLiteStore, connector_id: str) -> dict[str, Any] | None:
        """The pairing for one connector, or None.

        One pairing per connector by design: a second would make "is this channel
        linked" a question with two answers, and every enforcement point that
        reads the pairing would have to pick one.
        """
        row = self._row(
            "SELECT * FROM channel_pairings WHERE connector_id = ? ORDER BY paired_at DESC LIMIT 1",
            (connector_id,),
        )
        return dict(row) if row is not None else None

    def set_channel_pairing_enabled(self: SQLiteStore, pairing_id: str, enabled: bool) -> bool:
        """Enable or disable one pairing. Disabled is stored, not deleted: the
        owner's sender allowlist survives a pause and does not have to be typed
        again to resume."""
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE channel_pairings SET enabled = ? WHERE pairing_id = ?",
                (1 if enabled else 0, pairing_id),
            )
            return cursor.rowcount > 0

    def set_channel_pairing_allowlist(self: SQLiteStore, pairing_id: str, allowlist_json: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE channel_pairings SET sender_allowlist_json = ? WHERE pairing_id = ?",
                (allowlist_json, pairing_id),
            )
            return cursor.rowcount > 0

    def set_channel_pairing_routing(
        self: SQLiteStore,
        pairing_id: str,
        *,
        routing_mode: str,
        target_session_id: str | None,
        owner_sender_id: str | None,
        approval_relay_enabled: bool,
    ) -> bool:
        """Replace the inbound route as one atomic owner decision."""
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE channel_pairings
                   SET routing_mode = ?, target_session_id = ?, owner_sender_id = ?,
                       approval_relay_enabled = ?
                   WHERE pairing_id = ?""",
                (
                    routing_mode,
                    target_session_id,
                    owner_sender_id,
                    1 if approval_relay_enabled else 0,
                    pairing_id,
                ),
            )
            return cursor.rowcount > 0

    def set_channel_pairing_destination(
        self: SQLiteStore, pairing_id: str, delivery_url: str | None
    ) -> bool:
        """UX-MSG-04 — where this channel delivers, decided once by the owner.

        Changing the destination forgets the last test: a test proved the old
        destination, and the setup checklist must not count it for the new one.
        """
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE channel_pairings
                   SET delivery_url = ?, last_test_at = NULL, last_test_ok = NULL,
                       last_test_reason = NULL
                   WHERE pairing_id = ?""",
                (delivery_url, pairing_id),
            )
            return cursor.rowcount > 0

    def record_channel_pairing_test(
        self: SQLiteStore, pairing_id: str, *, ok: bool, reason_code: str | None
    ) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE channel_pairings
                   SET last_test_at = ?, last_test_ok = ?, last_test_reason = ?
                   WHERE pairing_id = ?""",
                (utc_now(), 1 if ok else 0, None if ok else (reason_code or "failed"), pairing_id),
            )
            return cursor.rowcount > 0

    # ── Channel receipts (UX-MSG-06) ─────────────────────────────────────────
    #
    # One row per channel message or test delivery, with each stage as its own
    # timestamp. Stages are written forward only and never reset, so a row can
    # say "processed" and "reply not delivered" at once — which is the case the
    # review names: a completed task is not a delivered reply.

    CHANNEL_RECEIPT_STAGES = (
        "received_at",
        "accepted_at",
        "queued_at",
        "processed_at",
        "reply_queued_at",
        "delivered_at",
        "failed_at",
    )
    #: Rows kept per connector. Receipts are a recent-activity ledger; the
    #: audit log is the permanent record.
    CHANNEL_RECEIPTS_KEPT = 200

    def insert_channel_receipt(
        self: SQLiteStore,
        *,
        receipt_id: str,
        connector_id: str,
        pairing_id: str | None,
        direction: str,
        kind: str,
        sender_role: str | None = None,
        conversation_scope: str | None = None,
        routing_mode: str | None = None,
        stages: dict[str, str] | None = None,
        reason_code: str | None = None,
    ) -> None:
        values: dict[str, Any] = {
            "receipt_id": receipt_id,
            "connector_id": connector_id,
            "pairing_id": pairing_id,
            "direction": direction,
            "kind": kind,
            "sender_role": sender_role,
            "conversation_scope": conversation_scope,
            "routing_mode": routing_mode,
            "reason_code": reason_code,
            "created_at": utc_now(),
        }
        for stage, at in (stages or {}).items():
            if stage in self.CHANNEL_RECEIPT_STAGES:
                values[stage] = at
        columns = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        with self.connect() as connection:
            connection.execute(
                f"INSERT INTO channel_receipts ({columns}) VALUES ({marks})",  # noqa: S608 - keys are fixed above
                tuple(values.values()),
            )
            connection.execute(
                """DELETE FROM channel_receipts
                   WHERE connector_id = ? AND receipt_id NOT IN (
                     SELECT receipt_id FROM channel_receipts WHERE connector_id = ?
                     ORDER BY created_at DESC, rowid DESC LIMIT ?)""",
                (connector_id, connector_id, self.CHANNEL_RECEIPTS_KEPT),
            )

    def advance_channel_receipt(
        self: SQLiteStore,
        receipt_id: str,
        *,
        stages: dict[str, str],
        session_id: str | None = None,
        reason_code: str | None = None,
    ) -> bool:
        """Record later stages. A stage already written keeps its first time."""
        sets: list[str] = []
        params: list[Any] = []
        for stage, at in stages.items():
            if stage not in self.CHANNEL_RECEIPT_STAGES:
                continue
            sets.append(f"{stage} = COALESCE({stage}, ?)")
            params.append(at)
        if session_id is not None:
            sets.append("session_id = ?")
            params.append(session_id)
        if reason_code is not None:
            sets.append("reason_code = ?")
            params.append(reason_code)
        if not sets:
            return False
        params.append(receipt_id)
        with self.connect() as connection:
            cursor = connection.execute(
                f"UPDATE channel_receipts SET {', '.join(sets)} WHERE receipt_id = ?",  # noqa: S608 - columns are whitelisted
                tuple(params),
            )
            return cursor.rowcount > 0

    def list_channel_receipts(
        self: SQLiteStore, connector_id: str, *, limit: int = 5
    ) -> list[dict[str, Any]]:
        rows = self._rows(
            """SELECT * FROM channel_receipts WHERE connector_id = ?
               ORDER BY created_at DESC, rowid DESC LIMIT ?""",
            (connector_id, max(1, min(int(limit), 50))),
        )
        return [dict(row) for row in rows]

    def delete_channel_pairing(self: SQLiteStore, pairing_id: str) -> bool:
        """Unpair. Both executors and the inbound receiver read the pairing table,
        so deleting the row is what actually stops a channel — there is no state
        where the page says unpaired and a message still gets through."""
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM channel_pairings WHERE pairing_id = ?", (pairing_id,)
            )
            return cursor.rowcount > 0

    def set_skill_command(
        self: SQLiteStore, skill_id: str, principal_id: str, trigger: str | None
    ) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE skills SET command_trigger = ?, updated_at = ? "
                "WHERE skill_id = ? AND principal_id = ?",
                (trigger, utc_now(), skill_id, principal_id),
            )
            return cursor.rowcount == 1

    def get_active_skill_by_command(
        self: SQLiteStore, principal_id: str, trigger: str
    ) -> dict[str, Any] | None:
        row = self._row(
            """SELECT * FROM skills
               WHERE principal_id = ? AND command_trigger = ? AND active = 1""",
            (principal_id, trigger),
        )
        return dict(row) if row is not None else None


    def insert_plugin_execution_record(self: SQLiteStore, record: PluginExecutionRecord) -> None:
        self._execute(
            """
            INSERT OR REPLACE INTO plugin_execution_records
            (execution_id, plugin_id, version, trust_level, permissions_json, entrypoint, status, started_at, completed_at, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.execution_id,
                record.plugin_id,
                record.version,
                record.trust_level,
                record.permissions_json,
                record.entrypoint,
                record.status,
                record.started_at,
                record.completed_at,
                record.created_by,
            ),
        )

    def list_plugin_execution_records(self: SQLiteStore, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._rows(
            "SELECT * FROM plugin_execution_records ORDER BY COALESCE(started_at, created_by) DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in rows]


    def insert_skill_candidate(self: SQLiteStore, candidate: SkillCandidate) -> None:
        self._execute(
            """
            INSERT OR REPLACE INTO skill_candidates
            (candidate_id, name, description, source_workflow_json, suggested_tools_json, provenance, status, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate.candidate_id,
                candidate.name,
                candidate.description,
                candidate.source_workflow_json,
                candidate.suggested_tools_json,
                candidate.provenance,
                candidate.status,
                candidate.created_by,
                candidate.created_at,
            ),
        )

    def list_skill_candidates(
        self: SQLiteStore, status: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM skill_candidates"
        params: list[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._rows(query, params)
        return [dict(row) for row in rows]
