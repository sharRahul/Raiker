from __future__ import annotations

import json
from typing import Any

from raiker.context.redaction import redact_text
from raiker.events.export import _is_secret_key, is_token_count_field

REDACTED_LABEL = "[REDACTED]"
REDACTED_VALUE = "***REDACTED***"

# Why free-form strings are scrubbed by *pattern* and not by keyword
# ------------------------------------------------------------------
# A value's **key** is the reliable signal that it holds a credential, and every
# such value is discarded whole below. A value's **words** are not: assistant
# replies, chat titles, and document excerpts talk about secrets, tokens, and
# passwords constantly without containing one.
#
# This layer used to replace the entire string whenever it merely contained the
# substring "secret", "token", "password", "bearer", or "authorization". That
# destroyed ordinary prose — a reply about an attached file came back as
# "(sample.md***REDACTED***comes directly from" because each streamed chunk
# holding the word was nuked, and a conversation titled from its first message
# appeared in Recent chats as literally "***REDACTED***".
#
# Free-form text is now handed to ``redact_text``, which matches real credential
# *shapes* (``sk-…``, ``ghp_…``, ``AKIA…``, ``Bearer …``, ``token=…``, PEM
# blocks, high-entropy runs) and substitutes only the matched span. Secrets are
# still caught, sentences survive, and nothing is silently lost: a redaction is
# always visible as a ``[REDACTED_*]`` marker in place.
#
# Deliberately unchanged: the keyword sweep in ``raiker/events/export.py`` still
# guards audit exports, which leave the machine in bulk and are read by
# machines, not people. There the cost of over-redaction is low and the value of
# belt-and-braces is high.
#
# Why locator fields get a narrower fallback
# ------------------------------------------
# The high-entropy fallback matches any 40+ character run of URL/base64
# characters — and ``/`` is one of them. A server-issued locator therefore trips
# it purely because its segments were joined: ``pdf_url``, ``events_path``,
# ``checkpoint_path`` and ``root_subpath`` all came back as
# ``[REDACTED_SECRET]``, leaving the client with nothing to fetch, open, or
# link to. (The file inspector's PDF pane is where this was first noticed.)
#
# The key is the signal, exactly as it is for token *counts* above: a field
# named ``*_url`` or ``*_path`` holds a locator, and only this layer knows that
# — ``redact_text`` sees a bare string. Those values are scanned with a fallback
# that spares a run whose every slash-separated segment is itself under the
# entropy threshold, so a credential embedded in a path is still its own
# over-length segment and is still redacted. Every specific credential shape
# (``sk-…``, ``ghp_…``, ``Bearer …``, ``token=…``, PEM blocks) is matched before
# the fallback and applies here unchanged. Free-form text is untouched by this
# and keeps the strict scan.

# Field-name suffixes whose values are locators. Deliberately a short, literal
# list of families the API actually emits (``pdf_url``, ``events_path``,
# ``root_subpath``, ``included_paths``) rather than a guess at future ones.
# Checked *after* the secret-key sweep, so a key naming a credential is still
# discarded whole even if it also ends in one of these.
_LOCATOR_KEY_SUFFIXES = ("_url", "_urls", "_uri", "_path", "_paths", "_subpath")


def is_locator_field(key: str) -> bool:
    """True when a field's name says its value is a URL or filesystem path."""
    lower = key.lower()
    return lower.endswith(_LOCATOR_KEY_SUFFIXES)


def _redact_value(value: Any, *, locator: bool = False) -> Any:
    if isinstance(value, dict):
        # A token *count* is an integer, never a credential. Without this the
        # models contract returned `context_window_tokens: "***REDACTED***"` and
        # the Chat context meter rendered "0 / NaN (NaN%)".
        return {
            k: (
                v
                if is_token_count_field(k, v)
                else REDACTED_VALUE
                if _is_secret_key(k)
                else _redact_value(v, locator=is_locator_field(k))
            )
            for k, v in value.items()
        }
    if isinstance(value, list):
        # A list under a locator key (``attachment_urls``) is a list of locators.
        return [_redact_value(item, locator=locator) for item in value]
    if isinstance(value, str):
        redacted, _changed = redact_text(value, locator_value=locator)
        return redacted
    return value


def redact_response_body(body: Any) -> Any:
    return _redact_value(body)


def assert_no_secrets_in_body(body: Any) -> None:
    """Assert that no secret-like data remains in an API response body."""
    _check_no_secrets(body)


def _check_no_secrets(value: Any, path: str = "$", *, locator: bool = False) -> None:
    # Mirrors _redact_value exactly, so the guard proves what the middleware
    # emits rather than a stricter rule the middleware never applied.
    if isinstance(value, dict):
        for k, v in value.items():
            if is_token_count_field(k, v):
                continue
            if _is_secret_key(k):
                raise AssertionError(f"Secret-like key at {path}.{k}: {k}")
            _check_no_secrets(v, f"{path}.{k}", locator=is_locator_field(k))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _check_no_secrets(item, f"{path}[{i}]", locator=locator)
    elif isinstance(value, str):
        redacted, changed = redact_text(value, locator_value=locator)
        if changed:
            raise AssertionError(f"Secret-like string at {path}: {value[:80]}")


def response_json_body(response_body: bytes) -> Any:
    try:
        return json.loads(response_body)
    except (json.JSONDecodeError, ValueError):
        return response_body.decode("utf-8", errors="replace")
