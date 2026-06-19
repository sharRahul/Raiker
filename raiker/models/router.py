from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from raiker.contracts.models import ClientMetadata, ModelProfile
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.models.contracts import ModelMessage, ModelResponse, ToolSpec
from raiker.models.mock import MockModelProvider
from raiker.models.providers import LlamaCppServerProvider, ProviderConnectionError
from raiker.models.registry import ModelProfileRegistry, RegistryError


@dataclass(frozen=True)
class ModelLaunchResult:
    status: str
    profile: ModelProfile | None
    message: str


def _provider_for(profile: ModelProfile) -> MockModelProvider | LlamaCppServerProvider:
    if profile.provider == "mock":
        return MockModelProvider(model=profile.model)
    if profile.provider == "llama.cpp":
        raw = profile.raw
        return LlamaCppServerProvider(
            model=str(raw.get("served_model_name", profile.model)),
            endpoint=str(raw.get("endpoint", "http://127.0.0.1:8080")),
            timeout=float(raw.get("timeout_seconds", 120.0)),
            temperature=float(raw.get("temperature", 0.2)),
            max_tokens=int(raw.get("max_tokens", 1024)),
            tool_call_mode=str(raw.get("tool_call_protocol", "openai")),
            allow_remote=not bool(profile.local_only),
        )
    raise RegistryError(f"provider_not_wired:{profile.provider}")


class ModelRouter:
    def __init__(
        self, registry: ModelProfileRegistry, writer: EventLogWriter | None = None
    ) -> None:
        self.registry = registry
        self.writer = writer

    def generate(
        self, provider: str, model: str, prompt: str, context: dict[str, object] | None = None
    ) -> str:
        profile = self.registry.resolve(provider, model)
        return _provider_for(profile).generate(prompt, context)

    def chat(
        self,
        provider: str,
        model: str,
        messages: Sequence[ModelMessage],
        tools: Sequence[ToolSpec] | None = None,
    ) -> ModelResponse:
        profile = self.registry.resolve(provider, model)
        return _provider_for(profile).chat(messages, tools)

    def default_provider(self, *, health_timeout: float = 1.0) -> tuple[str, str]:
        """Pick Raiker's native default backend: a reachable llama.cpp server, else mock.

        Keeps test/offline runs deterministic — with no server reachable, this returns the
        mock provider and never performs a model call.
        """

        for profile in self.registry.list_profiles():
            if profile.provider != "llama.cpp":
                continue
            try:
                provider = _provider_for(profile)
                if isinstance(provider, LlamaCppServerProvider) and provider.health(
                    timeout=health_timeout
                ):
                    return profile.provider, profile.model
            except (ProviderConnectionError, RegistryError, ValueError):
                continue
        return "mock", "mock-deterministic"

    def launch(
        self,
        provider: str,
        model: str,
        *,
        session_id: str,
        turn_id: str | None,
        client: ClientMetadata,
    ) -> ModelLaunchResult:
        if self.writer is not None:
            self.writer.append(
                make_event(
                    session_id=session_id,
                    turn_id=turn_id,
                    event_type="model_launch_requested",
                    actor="model_router",
                    payload={"provider": provider, "model": model},
                    client=client,
                )
            )
        try:
            profile = self.registry.resolve(provider, model)
        except RegistryError as exc:
            if self.writer is not None:
                self.writer.append(
                    make_event(
                        session_id=session_id,
                        turn_id=turn_id,
                        event_type="model_launch_failed",
                        actor="model_router",
                        payload={"provider": provider, "model": model, "error": str(exc)},
                        client=client,
                    )
                )
            return ModelLaunchResult("failed", None, str(exc))
        if self.writer is not None:
            self.writer.append(
                make_event(
                    session_id=session_id,
                    turn_id=turn_id,
                    event_type="model_launch_completed",
                    actor="model_router",
                    payload={
                        "profile_id": profile.profile_id,
                        "provider": profile.provider,
                        "model": profile.model,
                    },
                    client=client,
                )
            )
        return ModelLaunchResult(
            "completed", profile, f"Resolved model profile {profile.profile_id}"
        )
