from __future__ import annotations

import json
from typing import Any

from raiker.context.redaction import redact_text
from raiker.events.export import SECRET_PATTERNS, _is_secret_key

REDACTED_LABEL = "[REDACTED]"


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: (_redact_value("***REDACTED***") if _is_secret_key(k) else _redact_value(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, str):
        redacted, changed = redact_text(value)
        if changed:
            return redacted
        if len(value) > 0 and any(p in value.lower() for p in SECRET_PATTERNS):
            return "***REDACTED***"
        return value
    return value


def redact_response_body(body: Any) -> Any:
    return _redact_value(body)


def assert_no_secrets_in_body(body: Any) -> None:
    """Assert that no secret-like data remains in an API response body."""
    _check_no_secrets(body)


def _check_no_secrets(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            if _is_secret_key(k):
                raise AssertionError(f"Secret-like key at {path}.{k}: {k}")
            _check_no_secrets(v, f"{path}.{k}")
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _check_no_secrets(item, f"{path}[{i}]")
    elif isinstance(value, str):
        redacted, changed = redact_text(value)
        if changed:
            raise AssertionError(f"Secret-like string at {path}: {value[:80]}")
        if len(value) > 0 and any(p in value.lower() for p in SECRET_PATTERNS):
            raise AssertionError(f"Secret-pattern string at {path}: {value[:80]}")


def response_json_body(response_body: bytes) -> Any:
    try:
        return json.loads(response_body)
    except (json.JSONDecodeError, ValueError):
        return response_body.decode("utf-8", errors="replace")
