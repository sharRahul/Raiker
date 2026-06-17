from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from raiker.contracts.models import ModelProfile


class RegistryError(ValueError):
    def __init__(self, message: str, *, entry: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.entry = entry


def _config_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.exists():
        return candidate
    return Path.cwd() / path


class ModelProfileRegistry:
    def __init__(self, profiles: list[ModelProfile]) -> None:
        self.profiles = profiles

    @classmethod
    def load(cls, path: str | Path = "config/model-profiles.json") -> ModelProfileRegistry:
        data = json.loads(_config_path(path).read_text(encoding="utf-8"))
        if data.get("schema_version") != "1.0" or not isinstance(data.get("profiles"), list):
            raise RegistryError("invalid_model_registry")
        profiles: list[ModelProfile] = []
        required = {
            "profile_id",
            "provider",
            "model",
            "build_phase",
            "default_state",
            "tui_launch_action",
            "local_only",
            "requires_network",
        }
        for entry in data["profiles"]:
            missing = required - set(entry)
            if missing:
                raise RegistryError(f"model_profile_missing_fields:{sorted(missing)}", entry=entry)
            profiles.append(
                ModelProfile(
                    profile_id=entry["profile_id"],
                    provider=entry["provider"],
                    model=entry["model"],
                    build_phase=entry["build_phase"],
                    default_state=entry["default_state"],
                    tui_launch_action=entry["tui_launch_action"],
                    local_only=bool(entry["local_only"]),
                    requires_network=bool(entry["requires_network"]),
                    raw=entry,
                )
            )
        return cls(profiles)

    def list_profiles(self) -> list[ModelProfile]:
        return list(self.profiles)

    def resolve(self, provider: str, model: str) -> ModelProfile:
        normal_provider = provider.replace("_", "-")
        aliases = {"llama-cpp": "llama.cpp"}
        normal_provider = aliases.get(normal_provider, normal_provider)
        for profile in self.profiles:
            if profile.provider == normal_provider and profile.model == model:
                return profile
        raise RegistryError(f"unknown_model_profile:{provider}:{model}")
