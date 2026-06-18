from __future__ import annotations

import json
from pathlib import Path

from raiker.contracts.models import ConnectorProfile
from raiker.models.registry import RegistryError


def _config_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.exists():
        return candidate
    return Path.cwd() / path


class ConnectorRegistry:
    def __init__(self, profiles: list[ConnectorProfile]) -> None:
        self.profiles = profiles

    @classmethod
    def load(cls, path: str | Path = "config/channel-connectors.json") -> ConnectorRegistry:
        data = json.loads(_config_path(path).read_text(encoding="utf-8"))
        if data.get("schema_version") != "1.0" or not isinstance(data.get("connectors"), list):
            raise RegistryError("invalid_connector_registry")
        required = {
            "connector_id",
            "channel_type",
            "display_name",
            "build_phase",
            "default_state",
            "transport",
            "auth_method",
            "interface_status",
            "requires_pairing",
            "requires_sender_allowlist",
            "requires_network",
            "setup_ui",
            "capability_policy_template",
        }
        profiles: list[ConnectorProfile] = []
        for entry in data["connectors"]:
            missing = required - set(entry)
            if missing:
                raise RegistryError(
                    f"connector_profile_missing_fields:{sorted(missing)}", entry=entry
                )
            if entry["interface_status"] != "equal_primary_when_enabled":
                raise RegistryError("connector_not_equal_primary", entry=entry)
            profiles.append(
                ConnectorProfile(
                    connector_id=entry["connector_id"],
                    channel_type=entry["channel_type"],
                    display_name=entry["display_name"],
                    build_phase=entry["build_phase"],
                    default_state=entry["default_state"],
                    transport=entry["transport"],
                    auth_method=entry["auth_method"],
                    interface_status=entry["interface_status"],
                    requires_pairing=bool(entry["requires_pairing"]),
                    requires_sender_allowlist=bool(entry["requires_sender_allowlist"]),
                    requires_network=bool(entry["requires_network"]),
                    setup_ui=entry["setup_ui"],
                    capability_policy_template=entry["capability_policy_template"],
                    raw=entry,
                )
            )
        ids = {profile.connector_id for profile in profiles}
        if "channel.apple_mobile" not in ids or "channel.android_mobile" not in ids:
            raise RegistryError("mobile_connector_profiles_missing")
        return cls(profiles)

    def list_profiles(self) -> list[ConnectorProfile]:
        return list(self.profiles)

    def get(self, connector_id: str) -> ConnectorProfile:
        for profile in self.profiles:
            if profile.connector_id == connector_id:
                return profile
        raise RegistryError(f"unknown_connector:{connector_id}")
