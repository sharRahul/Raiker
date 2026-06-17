from __future__ import annotations

import json

import pytest

from raiker.channels.registry import ConnectorRegistry
from raiker.models.registry import RegistryError


def test_connector_registry_lists_disabled_mobile_profiles() -> None:
    registry = ConnectorRegistry.load()
    profiles = {profile.connector_id: profile for profile in registry.list_profiles()}
    assert profiles["channel.apple_mobile"].default_state == "disabled"
    assert profiles["channel.android_mobile"].default_state == "disabled"
    assert all(profile.interface_status == "equal_primary_when_enabled" for profile in profiles.values())


def test_invalid_connector_registry_structured_error(tmp_path) -> None:  # type: ignore[no-untyped-def]
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema_version": "1.0", "connectors": [{"connector_id": "bad"}]}), encoding="utf-8")
    with pytest.raises(RegistryError):
        ConnectorRegistry.load(bad)
