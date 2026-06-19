from __future__ import annotations

from dataclasses import dataclass

from raiker.models.providers.llama_cpp_server import (
    DEFAULT_ENDPOINT,
    ProviderConnectionError,
    _http_get_ok,
)


@dataclass(frozen=True)
class ProviderHealth:
    provider: str
    available: bool
    enabled_for_runtime: bool
    detail: str


def check_local_provider(
    provider: str, *, endpoint: str = DEFAULT_ENDPOINT, timeout: float = 1.0
) -> ProviderHealth:
    """Probe a local inference provider.

    The native backend is the llama.cpp ``llama-server``; availability is determined by its
    HTTP ``/health`` endpoint. ``enabled_for_runtime`` stays False here — wiring a turn to the
    provider is a runtime/router concern, not a health check.
    """

    if provider not in {"llama.cpp", "llama_cpp", "llama-cpp"}:
        return ProviderHealth(provider, False, False, "unsupported_local_provider")
    try:
        available = _http_get_ok(endpoint, "/health", timeout)
    except ProviderConnectionError as exc:
        return ProviderHealth(provider, False, False, str(exc))
    detail = "llama_server_healthy" if available else "llama_server_unreachable"
    return ProviderHealth(provider, available, False, detail)
