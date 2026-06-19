from __future__ import annotations


class ModelProviderError(Exception):
    """Base class for safe-to-log model provider errors."""


class ProviderConfigurationError(ModelProviderError):
    pass


class ProviderPolicyError(ModelProviderError):
    pass


class ProviderConnectionError(ModelProviderError):
    pass


class ProviderTimeoutError(ModelProviderError):
    pass

class ProviderAuthenticationError(ModelProviderError):
    pass


class ProviderRateLimitError(ModelProviderError):
    pass


class ProviderModelNotFoundError(ModelProviderError):
    pass


class ProviderUnsupportedCapabilityError(ModelProviderError):
    pass


class ProviderResponseValidationError(ModelProviderError):
    pass


class ProviderStreamError(ModelProviderError):
    pass


class ProviderCancelledError(ModelProviderError):
    pass


def safe_error(message: str) -> str:
    redacted = message.replace("Authorization", "[redacted-header]")
    for marker in ("Bearer ", "api_key", "api-key"):
        if marker in redacted:
            return "provider_error_redacted"
    return redacted[:240]
