from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

import pytest

from raiker.channels.registry import ConnectorRegistry
from raiker.models.registry import ModelProfileRegistry, resolve_builtin_config


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


def test_builtin_config_resolves_to_the_packaged_resource(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Non-editable installs do not carry the repo root next to ``raiker``."""
    monkeypatch.delenv("RAIKER_CONFIG_DIR", raising=False)
    monkeypatch.chdir(tmp_path)

    source = resolve_builtin_config("config/model-profiles.json")
    assert source.kind == "packaged"
    assert source.location == "raiker.config/model-profiles.json"

    assert any(
        profile.profile_id == "raiker-local-llama-cpp"
        for profile in ModelProfileRegistry.load().list_profiles()
    )
    assert ConnectorRegistry.load().get("channel.cli").display_name == "Command Line"


def test_a_config_directory_in_the_cwd_does_not_win(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GCR-45 — the working directory is not a configuration boundary.

    Raiker used to resolve `config/model-profiles.json` against the current
    working directory before the packaged registry. Launching the installed
    application from a stale checkout — or from any directory that happened to
    hold that name — therefore replaced the built-in model registry with no
    error, no warning, and a different answer depending on how it was started.
    """
    monkeypatch.delenv("RAIKER_CONFIG_DIR", raising=False)
    stray = tmp_path / "config"
    stray.mkdir()
    (stray / "model-profiles.json").write_text(
        '{"schema_version": "1.0", "description": "stray", "profiles": []}',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert resolve_builtin_config("config/model-profiles.json").kind == "packaged"
    assert ModelProfileRegistry.load().list_profiles()


def test_an_explicit_override_directory_wins_and_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An override is a decision the owner states, and it is reportable."""
    override = tmp_path / "raiker-config"
    override.mkdir()
    (override / "model-profiles.json").write_text(
        '{"schema_version": "1.0", "description": "override", "profiles": []}',
        encoding="utf-8",
    )
    monkeypatch.setenv("RAIKER_CONFIG_DIR", str(override))

    source = resolve_builtin_config("config/model-profiles.json")
    assert source.kind == "override"
    assert source.location == str(override / "model-profiles.json")
    assert ModelProfileRegistry.load().list_profiles() == []


def test_an_override_directory_without_the_file_falls_back_to_packaged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAIKER_CONFIG_DIR", str(tmp_path))
    assert resolve_builtin_config("config/channel-connectors.json").kind == "packaged"
    assert ConnectorRegistry.load().list_profiles()


def test_a_caller_named_path_is_still_a_filesystem_path(tmp_path: Path) -> None:
    """Only the two built-in names resolve as built-ins."""
    named = tmp_path / "my-profiles.json"
    named.write_text(
        '{"schema_version": "1.0", "description": "named", "profiles": []}',
        encoding="utf-8",
    )
    source = resolve_builtin_config(named)
    assert source.kind == "explicit_path"
    assert ModelProfileRegistry.load(named).list_profiles() == []


def test_the_builtin_config_has_exactly_one_copy() -> None:
    """There is no repository-root `config/` to drift from the packaged one.

    This used to compare the two byte for byte, because `config/` and
    `raiker/config/` held the same JSON and `_config_path` preferred the
    repository copy — so an edit applied to only one of them appeared to do
    nothing, with no error and no warning (FIXED-59). Keeping them in step was a
    guard against a duplication that did not need to exist: the packaged
    resource is what ships, resolves from any working directory, and is what a
    non-editable install has ever used.

    The duplicate is gone, so the invariant is stronger and simpler — the copy
    must not come back. A workspace-local `config/` is no longer an override at
    all (GCR-45); `RAIKER_CONFIG_DIR` is, and it is covered above.
    """
    package_config = resources.files("raiker.config")
    for name in ("model-profiles.json", "channel-connectors.json"):
        assert json.loads(package_config.joinpath(name).read_text(encoding="utf-8"))

    repo_root = Path(__file__).resolve().parent.parent
    for stray in (repo_root / "config", repo_root / "assets"):
        assert not stray.exists(), (
            f"{stray.name}/ is back at the repository root. The built-in copy lives in "
            "raiker/, and a second one silently wins over it for repo checkouts."
        )
