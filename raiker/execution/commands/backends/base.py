from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from raiker.execution.commands.models import CommandFeatures, CommandRequest


class CommandBackendError(RuntimeError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


class CommandBackend(Protocol):
    features: CommandFeatures

    def start(self, request: CommandRequest) -> Any: ...


class UnavailableBackend:
    features = CommandFeatures(shell=False)

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code

    def start(self, request: CommandRequest) -> Any:
        del request
        raise CommandBackendError(self.reason_code)


class BackendRegistry:
    """Exact profile-to-backend routing; deliberately has no fallback path."""

    def __init__(self, backends: Mapping[str, CommandBackend]) -> None:
        self._backends = dict(backends)

    def start(self, request: CommandRequest) -> Any:
        backend = self._backends.get(request.environment_profile_id)
        if backend is None:
            raise CommandBackendError("selected_environment_unavailable")
        return backend.start(request)
