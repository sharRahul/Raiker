from __future__ import annotations

import re


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


# Class → base reason code, for failures that arrive without a code of their own
# (a provider raising a bare exception, or a transport error mid-stream).
_PROVIDER_ERROR_CLASS_CODES: dict[str, str] = {
    "ProviderAuthenticationError": "provider_auth_failed",
    "ProviderTimeoutError": "provider_timeout",
    "ProviderRateLimitError": "provider_rate_limited",
    "ProviderModelNotFoundError": "model_not_found",
    "ProviderConnectionError": "provider_connection_failed",
    "ProviderConfigurationError": "provider_misconfigured",
    "ProviderPolicyError": "provider_policy_denied",
    "ProviderResponseValidationError": "provider_invalid_response",
    "ProviderStreamError": "provider_stream_failed",
    "ProviderCancelledError": "provider_cancelled",
    "ProviderUnsupportedCapabilityError": "provider_capability_unsupported",
}

UNCLASSIFIED_PROVIDER_ERROR = "provider_error_unclassified"

# A reason code is a snake_case identifier with an optional ``:detail`` suffix,
# e.g. ``provider_auth_failed:http_401``. Provider messages that are prose
# ("connection refused") are not codes and must not become one.
_REASON_CODE = re.compile(r"^[a-z][a-z0-9_]*(:[A-Za-z0-9_.\-]+)?$")


def provider_error_code(exc: BaseException) -> str:
    """Return the provider's own safe reason code for a failed model call.

    Providers already classify their failures precisely: an invalid key raises
    ``provider_auth_failed:http_401``, a missing model ``model_not_found:…``, a
    refused connection ``provider_connection_failed``. Reporting all of them as
    one generic code sends the owner to debug their network when the real cause
    is their credential, so the specific code is preserved here.

    Only a code-shaped message is trusted. Prose, and any exception that is not
    a ``ModelProviderError``, is classified by exception type instead — an
    arbitrary message is not a vetted code and could carry detail that does not
    belong in an event payload. ``safe_error`` runs first regardless, so a
    provider that put a header or key fragment in its message cannot leak it.
    """
    if isinstance(exc, ModelProviderError):
        code = safe_error(str(exc)).strip()
        # A redacted message tells us nothing about the failure, so the
        # exception type is the better classifier than "something was redacted".
        if code != "provider_error_redacted" and _REASON_CODE.match(code):
            return code
    return _PROVIDER_ERROR_CLASS_CODES.get(type(exc).__name__, UNCLASSIFIED_PROVIDER_ERROR)
