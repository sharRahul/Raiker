"""Prose must survive the API redaction layer; credentials must not.

Regression cover for the live manual-test finding that an assistant reply about
an attached ``sample.md`` came back as
``(sample.md***REDACTED***comes directly from`` and the conversation's title in
Recent chats became literally ``***REDACTED***``. The response layer replaced
the **whole string** whenever it merely contained the substring "secret",
"token", "password", "bearer", or "authorization", so ordinary English was
destroyed.

The two halves of the fix are both asserted here: free-form text is scrubbed by
credential *shape* (so sentences survive), and a value under a secret-like
*key* is still discarded whole.
"""

from __future__ import annotations

import json

from raiker.api.redaction import assert_no_secrets_in_body, redact_response_body
from raiker.api.routes_prompts import _sse
from raiker.context.redaction import redact_text
from raiker.contracts.streaming import TEXT_DELTA, StreamEvent
from raiker.events.export import redact_event_payload

REPORTED_REPLY = (
    "I can see from the workspace context that there's an attached document "
    "(sample.md). The secret project code is ORCHID-9, which comes directly "
    "from the uploaded markdown file that was provided in the attachment."
)
REPORTED_TITLE = "What is the secret project code in the attached file?"


class TestLegitimateProseSurvives:
    def test_the_reported_assistant_reply_is_returned_verbatim(self) -> None:
        body = {"response": {"answer": REPORTED_REPLY}}
        assert redact_response_body(body)["response"]["answer"] == REPORTED_REPLY

    def test_the_reported_chat_title_is_returned_verbatim(self) -> None:
        body = {"sessions": [{"session_id": "sess_1", "title": REPORTED_TITLE}]}
        assert redact_response_body(body)["sessions"][0]["title"] == REPORTED_TITLE

    def test_a_streamed_text_delta_is_not_blanked(self) -> None:
        # The SSE path redacts per chunk, which is how one sentence ended up
        # with a hole punched through its middle.
        chunk = "The secret project code is "
        frame = _sse(StreamEvent(kind=TEXT_DELTA, text=chunk))
        assert json.loads(frame.removeprefix("data: "))["text"] == chunk

    def test_ordinary_mentions_of_credential_words_survive(self) -> None:
        prose = [
            "Rotate the API token before Friday.",
            "Authorization is handled by the gate manager.",
            "The password field must never be logged.",
            "Bearer of this note gets a biscuit.",
            "the secret is out",
        ]
        assert redact_response_body(prose) == prose

    def test_an_env_var_name_is_not_a_credential(self) -> None:
        # The *name* is remediation guidance and is published in the docs; only
        # the value it points at is sensitive, and that never enters a response.
        body = {"credential_env": "RAIKER_GITHUB_TOKEN", "credential_configured": True}
        assert redact_response_body(body)["credential_env"] == "RAIKER_GITHUB_TOKEN"


class TestCredentialsAreStillCaught:
    def test_an_api_key_inside_prose_is_masked_in_place(self) -> None:
        body = {"answer": "Use sk-ant-api03-AAAABBBBCCCCDDDDEEEE for the call."}
        answer = redact_response_body(body)["answer"]
        assert "sk-ant-api03" not in answer
        assert answer == "Use [REDACTED_TOKEN] for the call."

    def test_a_bearer_header_inside_prose_is_masked_in_place(self) -> None:
        body = {"answer": "Send Authorization: Bearer abcdef0123456789 to the API."}
        answer = redact_response_body(body)["answer"]
        assert "abcdef0123456789" not in answer
        assert answer.startswith("Send ") and answer.endswith(" to the API.")

    def test_an_assignment_inside_prose_is_masked(self) -> None:
        assert "hunter2xyz" not in redact_response_body("run with password=hunter2xyz")

    def test_a_credential_disclosed_in_prose_is_masked(self) -> None:
        assert "hunter2xyz" not in redact_response_body("the password is hunter2xyz")
        assert redact_response_body("the secret is out") == "the secret is out"

    def test_a_private_key_block_is_masked(self) -> None:
        pem = "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADAN\n-----END PRIVATE KEY-----"
        assert redact_response_body({"answer": pem})["answer"] == "[REDACTED_PRIVATE_KEY]"

    def test_a_value_under_a_secret_like_key_is_still_discarded_whole(self) -> None:
        body = {
            "api_token": "opaque-value-no-pattern-matches",
            "nested": {"password": "plain"},
            "items": [{"authorization": "x"}],
        }
        assert redact_response_body(body) == {
            "api_token": "***REDACTED***",
            "nested": {"password": "***REDACTED***"},
            "items": [{"authorization": "***REDACTED***"}],
        }


class TestTheAssertionGuardMatchesTheMiddleware:
    def test_prose_passes_the_guard(self) -> None:
        assert_no_secrets_in_body({"answer": REPORTED_REPLY, "title": REPORTED_TITLE})

    def test_an_embedded_credential_fails_the_guard(self) -> None:
        try:
            assert_no_secrets_in_body({"answer": "key sk-ant-api03-AAAABBBBCCCCDDDD"})
        except AssertionError:
            return
        raise AssertionError("a credential-shaped string must still fail the guard")

    def test_the_guard_accepts_what_the_middleware_emits(self) -> None:
        # Redaction is idempotent, so a body that has already passed through the
        # middleware never trips the guard on its own markers.
        redacted = redact_response_body({"answer": "mail bob@example.com or use sk-ant-AAAABBBBCCCCDDDD"})
        assert_no_secrets_in_body(redacted)
        assert redact_response_body(redacted) == redacted


class TestAuditExportKeepsItsKeywordSweep:
    """The asymmetry is deliberate — exports leave the machine in bulk."""

    def test_a_secret_word_still_blanks_a_string_in_an_event_payload(self) -> None:
        assert redact_event_payload({"note": "Bearer token"}) == {"note": "***REDACTED***"}


class TestRedactTextStillMatchesKnownShapes:
    def test_a_snake_case_reason_code_is_not_mistaken_for_a_secret(self) -> None:
        code = "provider_requires_explicit_policy_approval_for_hosted_models"
        assert redact_text(code) == (code, False)

    def test_prose_with_an_intervening_noun_is_left_alone(self) -> None:
        assert redact_text("The secret project code is ORCHID-9")[1] is False

    def test_trailing_sentence_punctuation_is_kept_outside_the_mask(self) -> None:
        assert redact_text("the password is hunter2xyz.")[0] == "the [REDACTED_SECRET]."


class TestServerIssuedApiPathsSurvive:
    """BUG-07 — the file inspector's PDF locator came back as a placeholder.

    A path is not one opaque run. It only reached the 40-character high-entropy
    fallback because its segments were joined by slashes, and redacting it
    replaced a working same-origin URL with ``[REDACTED_SECRET]`` — the browser
    then had nothing to point its PDF viewer at.
    """

    PDF_URL = (
        "/api/sessions/sess_10ba5586e6d74065847e7b219ee215b0"
        "/attachments/att_3f21c0d94b6e4d1fa0b7c2e58d9a4413/preview/pdf"
    )

    def test_a_preview_url_survives_response_redaction(self) -> None:
        body = {"kind": "pdf", "pdf_url": self.PDF_URL}
        assert redact_response_body(body) == body

    def test_a_long_api_path_is_not_a_secret(self) -> None:
        assert redact_text(self.PDF_URL) == (self.PDF_URL, False)

    def test_a_key_embedded_in_an_api_path_is_still_redacted(self) -> None:
        # The exemption is per segment, so a credential riding in the path is
        # its own over-length segment and still fails closed.
        embedded = "/api/v1/key/AAAABBBBCCCCDDDDEEEEFFFFGGGGHHHHIIIIJJJJKKKK"
        redacted, changed = redact_text(embedded)
        assert changed is True
        assert "AAAABBBB" not in redacted

    def test_an_opaque_token_with_slashes_is_still_redacted(self) -> None:
        # Base64 secrets contain slashes; sparing them is exactly what the
        # `api/` prefix requirement prevents.
        secret = "aGVsbG8vd29ybGQvc2VjcmV0/dG9rZW4vbG9uZ2VyL3N0aWxsL2hlcmU="
        assert redact_text(secret)[1] is True

    def test_a_bearer_token_in_an_api_path_is_still_redacted(self) -> None:
        assert redact_text("api/x?authorization=bearer abcdefghijklmnop")[1] is True
