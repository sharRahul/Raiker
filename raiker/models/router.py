from __future__ import annotations

from dataclasses import dataclass

from raiker.contracts.models import ClientMetadata, ModelProfile
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.models.mock import MockModelProvider
from raiker.models.registry import ModelProfileRegistry, RegistryError


@dataclass(frozen=True)
class ModelLaunchResult:
    status: str
    profile: ModelProfile | None
    message: str


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
        if profile.provider != "mock":
            raise RegistryError(f"provider_not_wired_in_phase_1:{profile.provider}")
        return MockModelProvider(model=profile.model).generate(prompt, context)

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
