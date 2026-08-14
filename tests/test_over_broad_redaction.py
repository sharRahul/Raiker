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
        redacted = redact_response_body(
            {"answer": "mail bob@example.com or use sk-ant-AAAABBBBCCCCDDDD"}
        )
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


class TestServerIssuedLocatorsSurvive:
    """BUG-07 — server-issued locators came back as ``[REDACTED_SECRET]``.

    The high-entropy fallback matches any 40+ character run of URL/base64
    characters, and ``/`` is one of them, so a path tripped it purely because
    its segments were joined. The file inspector's ``pdf_url`` was where this
    was noticed, but it was never only that field: ``events_path``,
    ``checkpoint_path`` and ``root_subpath`` were being destroyed too, leaving
    the client with nothing to fetch, open, or link to.

    The field's *key* is the signal — the same mechanism FIXED-02 used for token
    counts. Locator-named fields get a fallback that spares a run whose every
    slash-separated segment is under the threshold; nothing else changes, and
    free-form text keeps the strict scan.
    """

    PDF_URL = (
        "/api/sessions/sess_10ba5586e6d74065847e7b219ee215b0"
        "/attachments/att_3f21c0d94b6e4d1fa0b7c2e58d9a4413/preview/pdf"
    )
    EVENTS_PATH = (
        "/home/user/.raiker/instances/work/events"
        "/sess_10ba5586e6d74065847e7b219ee215b0/turn_3f21c0d94b6e.jsonl"
    )

    def test_every_locator_field_survives_response_redaction(self) -> None:
        body = {
            "pdf_url": self.PDF_URL,
            "image_url": self.PDF_URL.replace("/pdf", "/image"),
            "events_path": self.EVENTS_PATH,
            "checkpoint_path": ".raiker/checkpoints/sess_10ba5586e6d74065847e7b219ee215b0/c.json",
            "root_subpath": "projects/quarterly-review-2026/workspace/drafts/current",
        }
        assert redact_response_body(body) == body

    def test_a_list_of_locators_survives(self) -> None:
        body = {"attachment_urls": [self.PDF_URL, self.EVENTS_PATH]}
        assert redact_response_body(body) == body

    def test_a_windows_locator_with_long_joined_segments_survives(self) -> None:
        path = (
            "C:\\Users\\owner\\AppData\\Local\\Temp"
            "\\raiker-pytest-terminal-prod-shape-20260814b\\workspace"
        )
        assert redact_response_body({"workspace_path": path}) == {"workspace_path": path}

    def test_a_token_segment_in_a_windows_locator_is_still_redacted(self) -> None:
        path = "C:\\work\\AAAABBBBCCCCDDDDEEEEFFFFGGGGHHHHIIIIJJJJKKKK\\receipt.json"
        redacted = redact_response_body({"receipt_path": path})["receipt_path"]
        assert "AAAABBBB" not in redacted

    def test_a_nested_locator_survives(self) -> None:
        body = {"response": {"events_path": self.EVENTS_PATH}}
        assert redact_response_body(body) == body

    def test_the_same_string_in_free_form_text_is_still_scanned_strictly(self) -> None:
        # Only a locator *field* gets the relaxed fallback. A path quoted inside
        # an assistant reply is untrusted text and keeps the strict rule.
        assert redact_response_body({"answer": self.PDF_URL}) != {"answer": self.PDF_URL}
        assert redact_text(self.PDF_URL)[1] is True

    def test_a_key_embedded_in_a_locator_is_still_redacted(self) -> None:
        # The exemption is per segment, so a credential riding in a URL is its
        # own over-length segment and still fails closed.
        body = {"download_url": "https://x.test/f/AAAABBBBCCCCDDDDEEEEFFFFGGGGHHHHIIIIJJJJKKKK"}
        redacted = redact_response_body(body)
        assert redacted != body
        assert "AAAABBBB" not in redacted["download_url"]

    def test_a_credential_query_parameter_is_still_redacted(self) -> None:
        body = {"callback_url": "https://x.test/cb?token=AAAABBBBCCCCDDDDEEEE"}
        redacted = redact_response_body(body)
        assert "AAAABBBB" not in redacted["callback_url"]

    def test_a_bearer_token_in_a_locator_is_still_redacted(self) -> None:
        body = {"api_url": "https://x.test/h/Bearer abcdefghijklmnopqrst"}
        assert "abcdefghijklmnopqrst" not in redact_response_body(body)["api_url"]

    def test_a_secret_named_key_still_wins_over_the_locator_rule(self) -> None:
        # ``_is_secret_key`` runs first: a field naming a credential is dropped
        # whole even when it also looks like a locator.
        assert redact_response_body({"secret_url": "https://x.test/anything"}) == {
            "secret_url": "***REDACTED***"
        }

    def test_an_opaque_token_with_slashes_is_still_redacted_in_a_locator(self) -> None:
        # Base64 secrets contain slashes. Under a locator key the segments are
        # what count, and a real secret keeps its entropy in one of them.
        body = {"asset_url": "aGVsbG8vd29ybGQvc2VjcmV0dG9rZW5sb25nZXJzdGlsbGhlcmVub3c="}
        assert redact_response_body(body) != body

    def test_a_credential_bearing_uri_is_still_redacted(self) -> None:
        # The one ``*_uri`` field the API emits is the TOTP provisioning URI,
        # whose query string carries the enrolment secret. Its route is
        # redaction-exempt, but the locator rule must not be what protects it:
        # the ``secret=`` pattern runs first and is unaffected.
        uri = "otpauth://totp/Raiker:owner?secret=JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
        assert "JBSWY3DP" not in redact_response_body({"provisioning_uri": uri})["provisioning_uri"]

    def test_the_guard_accepts_what_the_middleware_emits_for_locators(self) -> None:
        assert_no_secrets_in_body(redact_response_body({"pdf_url": self.PDF_URL}))


class TestUnprefixedLocatorFieldsSurvive:
    """The same failure for a field named ``path`` rather than ``*_path``.

    ``/api/model-library`` reports each approved root as ``{"path": …}``, and no
    suffix matches a bare name, so an owner who approved
    ``/home/user/models/library`` got ``/[REDACTED_SECRET]`` back: a root they
    could neither see nor remove, since removal is by path.
    """

    ROOT = "/home/user/.local/share/raiker/models/library/gguf"

    def test_a_bare_path_field_survives(self) -> None:
        body = {"roots": [{"path": self.ROOT}]}
        assert redact_response_body(body) == body

    def test_a_bare_url_field_survives(self) -> None:
        body = {"url": "/instances/quarterly-review-2026-workspace/attachments/preview"}
        assert redact_response_body(body) == body

    def test_a_credential_in_a_bare_path_field_is_still_redacted(self) -> None:
        body = {"path": "/var/keys/AAAABBBBCCCCDDDDEEEEFFFFGGGGHHHHIIIIJJJJKKKK"}
        redacted = redact_response_body(body)
        assert redacted != body
        assert "AAAABBBB" not in redacted["path"]

    def test_a_secret_named_key_still_wins_over_the_bare_locator_rule(self) -> None:
        assert redact_response_body({"token_path": "/var/keys/x"}) == {
            "token_path": "***REDACTED***"
        }


class TestServerIssuedIdentifiersSurvive:
    """FIXED-14 — the same failure, one field family further along.

    A record id is long for the same reason a path is: its prefixes were joined.
    ``sess_inbox_principal_user_<16 hex>`` is 42 characters without holding 40
    characters of entropy anywhere, so the fallback ate it and every task in the
    Inbox session came back with ``"session_id": "[REDACTED_SECRET]"`` — an id
    the client cannot open, link to, or stop work in.
    """

    INBOX = "sess_inbox_principal_user_e8b7bf68bd74bd5e"

    def test_a_long_inbox_session_id_survives(self) -> None:
        body = {"session_id": self.INBOX, "task_id": "task_f9d9572193994e1a91bbb188ee39008d"}
        assert redact_response_body(body) == body

    def test_a_list_of_ids_survives(self) -> None:
        body = {"task_ids": [self.INBOX, "turn_3f21c0d94b6e4d1fa0b7c2e58d9a4413"]}
        assert redact_response_body(body) == body

    def test_the_same_string_in_free_form_text_is_still_scanned_strictly(self) -> None:
        assert redact_response_body({"answer": self.INBOX}) != {"answer": self.INBOX}

    def test_an_opaque_value_under_an_id_key_is_still_redacted(self) -> None:
        # The exemption is a *shape*, not a blanket pass for `*_id`: anything
        # that is not a lowercase, underscore-joined record id fails closed.
        for value in (
            "AAAABBBBCCCCDDDDEEEEFFFFGGGGHHHHIIIIJJJJKKKK",
            "aGVsbG8gd29ybGQgc2VjcmV0IHRva2VuIGxvbmdlciBzdGlsbA==",
            "abcdefghij-klmnopqrst-uvwxyz0123-456789abcdef",
        ):
            assert redact_response_body({"external_id": value}) != {"external_id": value}

    def test_a_secret_named_key_still_wins_over_the_identifier_rule(self) -> None:
        assert redact_response_body({"token_id": "sess_inbox_principal_user_e8b7bf68"}) == {
            "token_id": "***REDACTED***"
        }

    def test_the_guard_accepts_what_the_middleware_emits_for_identifiers(self) -> None:
        assert_no_secrets_in_body(redact_response_body({"session_id": self.INBOX}))


def test_commit_revisions_and_digests_survive_only_in_named_fields() -> None:
    revision = "d" * 40
    digest = "a" * 64
    assert redact_response_body({"revision": revision, "toolchain_digest": digest}) == {
        "revision": revision,
        "toolchain_digest": digest,
    }
    assert redact_response_body({"answer": revision}) != {"answer": revision}
    assert redact_response_body({"revision": "sk-ant-AAAABBBBCCCCDDDD"}) != {
        "revision": "sk-ant-AAAABBBBCCCCDDDD"
    }
