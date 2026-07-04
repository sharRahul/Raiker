from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

from raiker.contracts.models import ModelProfile
from raiker.models.endpoint_policy import (
    EndpointPolicy,
    classify_endpoint,
    validate_endpoint_policy,
)


class RegistryError(ValueError):
    def __init__(self, message: str, *, entry: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.entry = entry


_BUILTIN_CONFIG_PACKAGE = "raiker.config"
_BUILTIN_CONFIG_RESOURCES = {
    "config/model-profiles.json": "model-profiles.json",
    "model-profiles.json": "model-profiles.json",
    "config/channel-connectors.json": "channel-connectors.json",
    "channel-connectors.json": "channel-connectors.json",
}


def _config_path(path: str | Path) -> Path:
    """Resolve a filesystem config file.

    Priority: an existing path as given (absolute, or relative to cwd), then
    the repository root next to the ``raiker`` package for editable installs
    and repo checkouts.
    """
    candidate = Path(path)
    if candidate.exists():
        return candidate
    cwd_candidate = Path.cwd() / path
    if cwd_candidate.exists():
        return cwd_candidate
    package_root = Path(__file__).resolve().parent.parent.parent
    packaged = package_root / path
    if packaged.exists():
        return packaged
    return cwd_candidate


def _read_config_text(path: str | Path) -> str:
    """Read built-in config with workspace overrides and packaged fallback."""
    config_path = _config_path(path)
    if config_path.exists():
        return config_path.read_text(encoding="utf-8")

    resource_name = _BUILTIN_CONFIG_RESOURCES.get(Path(path).as_posix())
    if resource_name is not None:
        try:
            resource = resources.files(_BUILTIN_CONFIG_PACKAGE).joinpath(resource_name)
            if resource.is_file():
                return resource.read_text(encoding="utf-8")
        except ModuleNotFoundError:
            pass

    return config_path.read_text(encoding="utf-8")


class ModelProfileRegistry:
    def __init__(self, profiles: list[ModelProfile]) -> None:
        self.profiles = profiles

    @classmethod
    def load(cls, path: str | Path = "config/model-profiles.json") -> ModelProfileRegistry:
        data = json.loads(_read_config_text(path))
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
            if not str(entry.get("model", "")):
                raise RegistryError("model_profile_missing_model", entry=entry)
            if bool(entry.get("reasoning_trace_visible", False)) and not bool(entry.get("supports_reasoning", False)):
                entry["reasoning_trace_visible"] = False
            endpoint = entry.get("endpoint") or entry.get("base_url")
            if endpoint:
                try:
                    validate_endpoint_policy(str(endpoint), EndpointPolicy(local_only=bool(entry["local_only"]), requires_network=bool(entry["requires_network"]), requires_egress_policy=bool(entry.get("requires_egress_policy", False)), requires_budget_policy=bool(entry.get("requires_budget_policy", False)), provider=str(entry["provider"]), allow_remote_http=bool(entry.get("allow_remote_http", False))))
                except Exception as exc:
                    raise RegistryError(str(exc), entry=entry) from exc
                entry.setdefault("endpoint_kind", classify_endpoint(str(endpoint)))
            entry.setdefault("reasoning_trace_visible", False)
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

    def resolve_profile_id(self, profile_id: str) -> ModelProfile:
        for profile in self.profiles:
            if profile.profile_id == profile_id:
                return profile
        raise RegistryError(f"unknown_model_profile_id:{profile_id}")

    def find(self, provider: str, model: str) -> list[ModelProfile]:
        normal_provider = provider.replace("_", "-")
        return [p for p in self.profiles if p.provider == normal_provider and p.model == model]

    def profiles_for_provider(self, provider: str) -> list[ModelProfile]:
        normal_provider = provider.replace("_", "-")
        aliases = {"llama-cpp": "llama.cpp"}
        normal_provider = aliases.get(normal_provider, normal_provider)
        return [p for p in self.profiles if p.provider == normal_provider]

    def register(self, profile: ModelProfile) -> None:
        """Add a runtime-resolved profile so ``resolve(provider, model)`` can find it."""
        self.profiles.append(profile)


def profile_with_model(profile: ModelProfile, model: str) -> ModelProfile:
    """Return a copy of ``profile`` with a concrete resolved model name."""
    return ModelProfile(
        profile_id=profile.profile_id,
        provider=profile.provider,
        model=model,
        build_phase=profile.build_phase,
        default_state=profile.default_state,
        tui_launch_action=profile.tui_launch_action,
        local_only=profile.local_only,
        requires_network=profile.requires_network,
        raw={**profile.raw, "model": model},
    )
