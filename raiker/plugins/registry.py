from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import PluginInstallRecord
from raiker.storage.sqlite import SQLiteStore


@dataclass
class PluginPlanRegistry:
    _plans: list[dict[str, Any]] = field(default_factory=list)

    def add_plan(self, plan: dict[str, Any]) -> None:
        self._plans.append(dict(plan))

    def list_plans(self) -> list[dict[str, Any]]:
        return [dict(plan) for plan in self._plans]


def record_plugin_install(
    store: SQLiteStore,
    plugin_id: str,
    version: str,
    trust_level: str,
    permissions_json: str,
    checksum: str | None = None,
    signature: str | None = None,
    source_url: str | None = None,
    commit_sha: str | None = None,
    status: str = "installed",
    installed_by: str = "cli",
) -> PluginInstallRecord:
    record = PluginInstallRecord(
        record_id=new_id("plr_"),
        plugin_id=plugin_id,
        version=version,
        trust_level=trust_level,
        checksum=checksum,
        signature=signature,
        source_url=source_url,
        commit_sha=commit_sha,
        permissions_json=permissions_json,
        status=status,
        installed_at=utc_now(),
        installed_by=installed_by,
    )
    store.insert_plugin_install_record(record)
    return record
