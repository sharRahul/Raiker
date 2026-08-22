"""Token *counts* must survive redaction; token *credentials* must not.

Regression cover for the live manual-test finding that the Chat context meter
rendered ``0 / NaN (NaN%)``: every key containing the substring "token" was
treated as a secret, so ``context_window_tokens`` reached the browser as the
string ``***REDACTED***`` and the normalised usage numbers were stripped out of
the audit record too.
"""

from __future__ import annotations

from raiker.api.redaction import assert_no_secrets_in_body, redact_response_body
from raiker.control.dashboard import ContextUsageView
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

    def test_a_bool_under_a_credential_shaped_key_survives(self) -> None:
        """Reversed on 2026-08-22, deliberately (FIXED-266).

        This asserted the opposite: that ``{"max_tokens": True}`` came back
        redacted. The rule it was defending is real and unchanged — the *count*
        exemption is integer-only, so a **string** under a count-shaped key can
        never ride out as "not a secret" (the test above). Extending that guard
        to booleans protected nothing and cost something:

        `True` and `False` cannot carry a credential. Replacing one does not hide
        a secret, it replaces a fact with a **non-empty string** — so every
        client testing the field for truthiness reads the *negation* of what the
        server said, confidently and silently. That is what happened to
        `inbound.secret_configured` on the Channels tab: the receiver was
        refusing every message and the page rendered "Secret set".

        A safety filter that turns a fact into its opposite is worse than one
        that drops it, so booleans are exempt by value regardless of the key.
        """
        assert redact_response_body({"max_tokens": True}) == {"max_tokens": True}
        assert redact_response_body({"secret_configured": False}) == {"secret_configured": False}
        # And the guard agrees with the middleware, rather than being stricter
        # than what the middleware actually emits.
        assert_no_secrets_in_body({"secret_configured": False})

    def test_the_secret_assertion_accepts_counts_and_rejects_credentials(self) -> None:
        assert_no_secrets_in_body({"context_window_tokens": 200_000, "output_tokens": 12})
        try:
            assert_no_secrets_in_body({"api_token": "value"})
        except AssertionError:
            return
        raise AssertionError("a credential-shaped key must still fail the assertion")


class TestContextUsageContractSurvivesRedaction:
    """BUG-68 — every count on the context contract must reach the browser.

    The popover formats these fields with ``Intl.NumberFormat``. A field the
    redactor replaces with ``"***REDACTED***"`` therefore renders as ``NaN``,
    which is exactly how ``session_input_tokens`` / ``session_output_tokens``
    surfaced. Asserting the *whole* contract rather than the two names that
    failed means the next count added to ``ContextUsageView`` is covered the day
    it is added.
    """

    @staticmethod
    def _populated_view() -> ContextUsageView:
        return ContextUsageView(
            session_id="sess_1",
            profile_id="anthropic-hosted",
            provider="anthropic",
            model="claude-sonnet-4-5-20250929",
            used_tokens=706,
            context_window_tokens=200_000,
            context_window_source="runtime",
            usage_source="provider",
            billable=True,
            session_cost="0.0031",
            provider_total_cost="0.0412",
            currency="USD",
            price_source="config",
            price_as_of="2026-01-01",
            session_turns=3,
            session_input_tokens=624,
            session_output_tokens=82,
            price_input_per_mtok="3.00",
            price_output_per_mtok="15.00",
            price_cache_write_per_mtok="3.75",
            price_cache_read_per_mtok="0.30",
            price_effective_from="2026-01-01",
        )

    def test_every_integer_field_survives_redact_response_body(self) -> None:
        body = self._populated_view().to_dict()
        redacted = redact_response_body(body)
        integer_fields = {
            name: value for name, value in body.items() if isinstance(value, int) and not isinstance(value, bool)
        }
        assert integer_fields, "the fixture must carry the contract's integer fields"
        for name, value in integer_fields.items():
            assert redacted[name] == value, f"{name} was redacted and would render as NaN"

    def test_the_two_names_that_regressed_are_named_explicitly(self) -> None:
        # Kept as its own assertion so a future refactor of the fixture cannot
        # quietly stop covering the pair BUG-68 was reported for.
        body = self._populated_view().to_dict()
        redacted = redact_response_body(body)
        assert redacted["session_input_tokens"] == 624
        assert redacted["session_output_tokens"] == 82
