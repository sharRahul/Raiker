from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

import pytest

import raiker.models.registry as model_registry_module
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


def test_registries_load_from_packaged_resources_when_repo_config_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Non-editable installs do not carry the repo root next to ``raiker``."""
    missing = tmp_path / "missing-config.json"
    monkeypatch.setattr(model_registry_module, "_config_path", lambda _path: missing)

    model_registry = ModelProfileRegistry.load()
    connector_registry = ConnectorRegistry.load()

    assert any(
        profile.profile_id == "raiker-local-llama-cpp"
        for profile in model_registry.list_profiles()
    )
    assert connector_registry.get("channel.cli").display_name == "Command Line"


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


def test_packaged_config_resources_match_workspace_defaults() -> None:
    package_config = resources.files("raiker.config")
    assert json.loads(package_config.joinpath("model-profiles.json").read_text(encoding="utf-8")) == json.loads(
        Path("config/model-profiles.json").read_text(encoding="utf-8")
    )
    assert json.loads(
        package_config.joinpath("channel-connectors.json").read_text(encoding="utf-8")
    ) == json.loads(Path("config/channel-connectors.json").read_text(encoding="utf-8"))
