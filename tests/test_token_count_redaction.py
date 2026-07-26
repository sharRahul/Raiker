"""Token *counts* must survive redaction; token *credentials* must not.

Regression cover for the live manual-test finding that the Chat context meter
rendered ``0 / NaN (NaN%)``: every key containing the substring "token" was
treated as a secret, so ``context_window_tokens`` reached the browser as the
string ``***REDACTED***`` and the normalised usage numbers were stripped out of
the audit record too.
"""

from __future__ import annotations

from raiker.api.redaction import assert_no_secrets_in_body, redact_response_body
from raiker.events.export import redact_event_payload


class TestTokenCountRedaction:
    def test_context_window_survives_the_models_response(self) -> None:
        body = {"profiles": [{"profile_id": "anthropic-hosted", "context_window_tokens": 200_000}]}
        assert redact_response_body(body)["profiles"][0]["context_window_tokens"] == 200_000

    def test_normalised_usage_counts_survive_the_event_log(self) -> None:
        payload = {
            "input_tokens": 2694,
            "output_tokens": 37,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        }
        assert redact_event_payload(payload) == payload

    def test_credentials_named_token_are_still_redacted(self) -> None:
        body = {"api_token": "sk-ant-secret", "owner_token": "abc123", "authorization": "Bearer x"}
        redacted = redact_response_body(body)
        assert redacted == {
            "api_token": "***REDACTED***",
            "owner_token": "***REDACTED***",
            "authorization": "***REDACTED***",
        }

    def test_a_count_key_holding_a_string_is_still_redacted(self) -> None:
        # The exemption is count-shaped keys with integer values only. A string
        # under one of those names cannot ride out as "not a secret".
        assert redact_response_body({"input_tokens": "sk-ant-leak"}) == {
            "input_tokens": "***REDACTED***"
        }

    def test_a_count_key_holding_a_bool_is_still_redacted(self) -> None:
        assert redact_response_body({"max_tokens": True}) == {"max_tokens": "***REDACTED***"}

    def test_the_secret_assertion_accepts_counts_and_rejects_credentials(self) -> None:
        assert_no_secrets_in_body({"context_window_tokens": 200_000, "output_tokens": 12})
        try:
            assert_no_secrets_in_body({"api_token": "value"})
        except AssertionError:
            return
        raise AssertionError("a credential-shaped key must still fail the assertion")
