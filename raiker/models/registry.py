from __future__ import annotations

import json
import os
from importlib import resources
from pathlib import Path, PurePath
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


class BuiltinConfigSource:
    """Where a built-in registry was actually read from, and why.

    GCR-45 — the answer used to depend on the current working directory, so the
    same install answered differently depending on where the owner happened to
    launch it from. It is reported now because a resolution nobody can see is a
    resolution nobody can check.
    """

    __slots__ = ("kind", "location")

    def __init__(self, kind: str, location: str) -> None:
        self.kind = kind
        self.location = location

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return f"BuiltinConfigSource(kind={self.kind!r}, location={self.location!r})"

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, BuiltinConfigSource)
            and other.kind == self.kind
            and other.location == self.location
        )

    def as_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "location": self.location}


def config_override_dir() -> Path | None:
    """The one explicit override for built-in config, or ``None``.

    An override is a decision the owner states, not a directory they happened to
    be standing in. ``RAIKER_CONFIG_DIR`` is that statement.
    """
    raw = os.environ.get("RAIKER_CONFIG_DIR", "").strip()
    return Path(raw).expanduser() if raw else None


def _builtin_resource_name(path: str | Path) -> str | None:
    return _BUILTIN_CONFIG_RESOURCES.get(PurePath(str(path)).as_posix())


def _config_path(path: str | Path) -> Path:
    """Resolve a caller-named config file on the filesystem.

    This is for a path the caller chose. A built-in registry does not come
    through here unless ``RAIKER_CONFIG_DIR`` named it: see
    :func:`resolve_builtin_config`.
    """
    candidate = Path(path)
    if candidate.exists():
        return candidate
    package_root = Path(__file__).resolve().parent.parent.parent
    packaged = package_root / path
    if packaged.exists():
        return packaged
    return candidate


def resolve_builtin_config(path: str | Path) -> BuiltinConfigSource:
    """Say where the built-in registry named by ``path`` will be read from.

    Order, and there are only two entries in it: the explicit
    ``RAIKER_CONFIG_DIR`` override, then the packaged resource that ships with
    Raiker. The current working directory is not consulted (GCR-45) — for an
    installed application it is incidental process state, and letting it win
    meant a stale checkout beside the terminal could silently replace the model
    registry.
    """
    resource_name = _builtin_resource_name(path)
    if resource_name is None:
        return BuiltinConfigSource("explicit_path", str(_config_path(path)))
    override_dir = config_override_dir()
    if override_dir is not None:
        override = override_dir / resource_name
        if override.exists():
            return BuiltinConfigSource("override", str(override))
    return BuiltinConfigSource("packaged", f"{_BUILTIN_CONFIG_PACKAGE}/{resource_name}")


def _read_config_text(path: str | Path) -> str:
    """Read a config file from its resolved, reportable source."""
    source = resolve_builtin_config(path)
    if source.kind == "packaged":
        resource_name = _builtin_resource_name(path)
        assert resource_name is not None  # noqa: S101 - kind == packaged implies it
        try:
            resource = resources.files(_BUILTIN_CONFIG_PACKAGE).joinpath(resource_name)
            if resource.is_file():
                return resource.read_text(encoding="utf-8")
        except ModuleNotFoundError:
            pass
        # No packaged resource: fall back to the repository copy an editable
        # checkout carries, so a source tree without an installed package still
        # runs. Still never the working directory.
        package_root = Path(__file__).resolve().parent.parent
        return (package_root / "config" / resource_name).read_text(encoding="utf-8")
    return Path(source.location).read_text(encoding="utf-8")


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
            else:
                # Env-configured endpoint (e.g. LM_STUDIO_BASE_URL): classify the
                # owner's configured URL when present so the control surfaces show
                # the real governing gate. When unset, report the profile's declared
                # off-machine intent (private_network) rather than "unknown" — the
                # factory still re-classifies and enforces policy at creation time.
                endpoint_env = str(entry.get("endpoint_env") or "")
                if endpoint_env:
                    configured = os.environ.get(endpoint_env, "").strip()
                    entry.setdefault(
                        "endpoint_kind",
                        classify_endpoint(configured) if configured else "private_network",
                    )
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
        # 1) Exact (provider, model) match wins.
        for profile in self.profiles:
            if profile.provider == normal_provider and profile.model == model:
                return profile
        # 2) Fall back to a provider profile that ships a placeholder model
        #    (openrouter/openai/gemini/ollama/vllm/lm-studio/openai-compatible all
        #    pick the concrete model at selection time). This makes the direct
        #    ModelRouter path (achat/aembed) consistent with the CLI `/model use`
        #    + gateway path, which already substitute the concrete model. Provider
        #    policy (gate, egress allowlist, API key) is still enforced later by
        #    the provider factory, so this only fills in the model name.
        if model and "<" not in model and ">" not in model:
            for profile in self.profiles:
                if profile.provider == normal_provider and _is_placeholder_model(profile.model):
                    return profile_with_model(profile, model)
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


def _is_placeholder_model(model: str) -> bool:
    """A profile ships a placeholder model when the concrete name is chosen later."""
    return not model or "<" in model or ">" in model


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
