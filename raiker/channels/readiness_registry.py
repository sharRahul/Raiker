from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from raiker.channels.readiness import (
    DISABLED_RUNTIME_FLAGS,
    ExternalChannelsNotificationsReadinessContract,
    create_external_channels_notifications_readiness_contract,
)
from raiker.storage.sqlite import SQLiteStore

_RECORDS: dict[str, ExternalChannelsNotificationsReadinessContract] = {}


def _workspace_id(workspace_root: str | Path) -> str:
    return str(Path(workspace_root).resolve())


def create_channel_readiness_metadata(*, workspace_root: str | Path = ".", persist: bool = False, **kwargs: Any) -> ExternalChannelsNotificationsReadinessContract:
    record = create_external_channels_notifications_readiness_contract(workspace_id=_workspace_id(workspace_root), **kwargs)
    _RECORDS[record.readiness_id] = record
    if persist:
        store = SQLiteStore(workspace_root)
        with store.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO phase3_external_channels_notifications_readiness
                (readiness_id, target, status, blockers_json, disabled_runtime_flags_json, contract_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.readiness_id,
                    record.target_capability,
                    "metadata_only_blocked",
                    json.dumps(record.to_dict()["blockers"], sort_keys=True),
                    json.dumps(DISABLED_RUNTIME_FLAGS, sort_keys=True),
                    json.dumps(record.to_dict(), sort_keys=True),
                ),
            )
    return record


def list_channel_readiness_metadata(*, workspace_root: str | Path | None = None) -> list[ExternalChannelsNotificationsReadinessContract]:
    records = list(_RECORDS.values())
    if workspace_root is not None:
        workspace = _workspace_id(workspace_root)
        records = [record for record in records if record.workspace_id == workspace]
        if not records:
            records = [create_channel_readiness_metadata(workspace_root=workspace_root)]
    return sorted(records, key=lambda record: record.readiness_id)


def get_channel_readiness_metadata(readiness_id: str) -> ExternalChannelsNotificationsReadinessContract | None:
    return _RECORDS.get(readiness_id)


def channel_readiness_summary(*, workspace_root: str | Path = ".") -> dict[str, Any]:
    records = list_channel_readiness_metadata(workspace_root=workspace_root)
    latest = records[-1] if records else create_channel_readiness_metadata(workspace_root=workspace_root)
    return {
        "external_channels_notifications_readiness_contract_available": True,
        "external_channels_notifications_readiness_record_count": len(records),
        "latest_readiness_id": latest.readiness_id,
        "metadata_only": True,
        "ready_for_external_channels": False,
        **DISABLED_RUNTIME_FLAGS,
        "blocker_count": len(latest.blockers),
        "required_gate_count": len(latest.required_gates),
    }


def render_channel_readiness(*, workspace_root: str | Path = ".") -> str:
    summary = channel_readiness_summary(workspace_root=workspace_root)
    lines = [
        "External channels/notifications readiness:",
        "persistence: metadata_only_optional_sqlite",
        "external_channels_enabled: False",
    ]
    lines.extend(f"{key}: {value}" for key, value in summary.items())
    return "\n".join(lines)
