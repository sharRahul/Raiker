from __future__ import annotations

from pathlib import Path

import pytest

from raiker.channels.registry import ConnectorRegistry
from raiker.models.registry import ModelProfileRegistry


def test_model_registry_loads_from_foreign_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The installed `raiker` command must find built-in config from any cwd."""
    monkeypatch.chdir(tmp_path)
    registry = ModelProfileRegistry.load()
    assert any(p.profile_id == "raiker-local-llama-cpp" for p in registry.list_profiles())


def test_connector_registry_loads_from_foreign_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    registry = ConnectorRegistry.load()
    assert registry.list_profiles()


def test_workspace_local_config_still_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A workspace-local config/ copy takes priority over the packaged one."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "model-profiles.json").write_text(
        '{"schema_version": "1.0", "description": "local override", "profiles": []}',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    registry = ModelProfileRegistry.load()
    assert registry.list_profiles() == []
