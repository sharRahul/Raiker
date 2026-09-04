"""BUG-274 — the answer to an identity-linked key was "go and get another one".

FIXED-370 classified the refusal correctly and stopped there: the owner was told
their key was the wrong *kind* and sent to the provider's console for a
different one. For an owner who has only this key that is not a repair, it is a
dead end — and it was Raiker's dead end, because the provider had already said
what it wanted. An identity-linked key authenticates perfectly well; it acts
inside one workspace, and the request has to name which.

So Raiker names it. The workspace id is stored beside the key, sent as
``anthropic-workspace-id``, and refused before storage if it could not safely
become a header. Once one is named, a refusal means *that id* is wrong, which is
a different sentence with a different repair — asking again for a value the
owner has already supplied is the one answer that helps nobody.
"""

from __future__ import annotations

import pytest

from raiker.contracts.models import ModelProfile
from raiker.models.connections import (
    WORKSPACE_ID_INVALID_SHAPE,
    validated_workspace_id,
)
from raiker.models.exceptions import (
    ProviderConfigurationError,
    ProviderQuotaExhaustedError,
    ProviderWorkspaceRequiredError,
    needs_workspace_id,
    provider_error_code,
    workspace_id_rejected,
)
from raiker.models.factory import ModelProviderFactory, ProviderRuntimePolicy

INVALID_BODY = (
    '{"type":"error","error":{"type":"invalid_request_error","message":'
    '"anthropic-workspace-id header must be a valid workspace ID."},"request_id":null}'
)
MISSING_BODY = (
    '{"type":"error","error":{"type":"invalid_request_error","message":'
    '"anthropic-workspace-id is required when authenticating with an identity-linked '
    'API key; send the id of the workspace this request acts in."},"request_id":null}'
)

# BUG-277 — what the provider *actually* sends, captured from a live 400 on
# 2026-09-04. `MISSING_BODY` above was written from the header name and the
# concept rather than from a response, and it shares not one phrase with this:
# no "is required", no "identity-linked". Every literal the classifier matched
# was therefore matched only by the test that invented it, and the real refusal
# fell through to `provider_http_error:http_400` — which the Models page renders
# as "could not be reached", sending the owner to debug a working network.
#
# Kept as the first fixture any change to this classification is measured
# against. A body a provider was observed sending outranks one this repository
# wrote down.
LIVE_MISSING_BODY = (
    '{"type":"error","error":{"type":"invalid_request_error","message":'
    '"This API key is not scoped to a workspace, so this request must include the '
    "anthropic-workspace-id header with the ID of the workspace to use. Add the header, "
    'or use an API key that is scoped to a workspace."},"request_id":null}'
)


def _anthropic_profile() -> ModelProfile:
    return ModelProfile(
        profile_id="anthropic-test",
        provider="anthropic",
        model="claude-haiku-4-5-20251001",
        build_phase="phase_4",
        default_state="enabled",
        tui_launch_action="/model use anthropic-test",
        local_only=False,
        requires_network=True,
        raw={
            "endpoint": "https://api.anthropic.com",
            "endpoint_kind": "remote_hosted",
            "requires_api_key": True,
            "requires_egress_policy": True,
            "served_model_name": "claude-haiku-4-5-20251001",
        },
    )


def _factory(connection: dict[str, str]) -> ModelProviderFactory:
    return ModelProviderFactory(
        policy=ProviderRuntimePolicy(allow_hosted_provider=True),
        connection=connection,
    )


class TestTheShapeCheckIsAHeaderRule:
    """Not a guess at the provider's id format — a rule a header actually needs."""

    @pytest.mark.parametrize(
        "value",
        ["wrkspc_01ABCdef", "ws-1", "a" * 128, "team.one:prod", "  wrkspc_pad  "],
    )
    def test_an_ordinary_id_passes(self, value: str) -> None:
        assert validated_workspace_id(value) == value.strip()

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "   ",
            "a" * 129,
            "wrkspc_1\nx-admin: yes",  # a second header
            "wrkspc_1\r\nHost: elsewhere",
            "wrkspc 1",
            "wrkspc_é",
        ],
    )
    def test_anything_a_header_could_not_carry_is_refused(self, value: str) -> None:
        with pytest.raises(ValueError, match=WORKSPACE_ID_INVALID_SHAPE):
            validated_workspace_id(value)


class TestTheHeaderIsSentOnlyWhenNamed:
    def test_a_named_workspace_travels_with_the_key(self) -> None:
        provider = _factory({"api_key": "sk-test", "workspace_id": "wrkspc_01"}).create(
            _anthropic_profile()
        )
        assert provider._headers["anthropic-workspace-id"] == "wrkspc_01"
        assert provider._headers["x-api-key"] == "sk-test"

    def test_a_standard_key_is_not_sent_an_empty_workspace(self) -> None:
        """An empty header is not the same as no header, and would be refused."""
        provider = _factory({"api_key": "sk-test"}).create(_anthropic_profile())
        assert "anthropic-workspace-id" not in provider._headers

    def test_a_stored_value_that_no_longer_passes_fails_closed(self) -> None:
        """It is never sent unchecked; a misconfiguration is repaired, not risked."""
        with pytest.raises(ProviderConfigurationError, match=WORKSPACE_ID_INVALID_SHAPE):
            _factory({"api_key": "sk-test", "workspace_id": "a\nb"}).create(
                _anthropic_profile()
            )


class TestARejectedIdIsNotAMissingOne:
    def test_the_real_rejection_body_is_classified(self) -> None:
        assert workspace_id_rejected(400, INVALID_BODY) is True

    def test_and_is_not_read_as_the_missing_case(self) -> None:
        """Both bodies name the same header; only one names a value already given."""
        assert needs_workspace_id(400, INVALID_BODY) is False

    def test_the_missing_case_is_untouched(self) -> None:
        assert needs_workspace_id(400, MISSING_BODY) is True
        assert workspace_id_rejected(400, MISSING_BODY) is False

    @pytest.mark.parametrize("status", [401, 403, 429, 500])
    def test_only_a_400_is_considered(self, status: int) -> None:
        assert workspace_id_rejected(status, INVALID_BODY) is False

    @pytest.mark.parametrize("module", ["anthropic_messages", "openai_compatible"])
    def test_both_providers_raise_the_invalid_code(self, module: str) -> None:
        mapper = __import__(
            f"raiker.models.providers.{module}", fromlist=["_map_status"]
        )._map_status
        exc = mapper(400, model="m", body=INVALID_BODY)
        assert isinstance(exc, ProviderWorkspaceRequiredError)
        assert provider_error_code(exc) == "provider_workspace_invalid:http_400"

    def test_it_does_not_steal_the_quota_case(self) -> None:
        from raiker.models.providers.anthropic_messages import _map_status

        exc = _map_status(400, model="m", body='{"error":{"message":"credit balance is too low"}}')
        assert isinstance(exc, ProviderQuotaExhaustedError)

    def test_nothing_from_the_body_reaches_the_code(self) -> None:
        from raiker.models.providers.anthropic_messages import _map_status

        body = INVALID_BODY.replace("valid workspace ID", "valid workspace ID for acct_secret9")
        code = provider_error_code(_map_status(400, model="m", body=body))
        assert code == "provider_workspace_invalid:http_400"
        assert "secret9" not in code


class TestTheOwnerIsToldWhichRepairToMake:
    def test_the_two_answers_do_not_share_a_sentence(self) -> None:
        from raiker.models.exceptions import _PROVIDER_ERROR_SENTENCES

        sentences = dict(_PROVIDER_ERROR_SENTENCES)
        missing = sentences["provider_workspace_required"]
        invalid = sentences["provider_workspace_invalid"]
        assert missing != invalid
        # The missing case asks for a value; the invalid case asks them to check
        # the one they gave. Neither tells them to replace the key.
        assert "Add the workspace ID" in missing
        assert "did not recognise" in invalid
        assert "key itself is fine" in missing
        for sentence in (missing, invalid):
            assert "rotate" not in sentence.lower()

    def test_readiness_separates_them(self) -> None:
        from raiker.models.readiness import _is_workspace_invalid

        assert _is_workspace_invalid(
            ProviderWorkspaceRequiredError("provider_workspace_invalid:http_400")
        )
        assert not _is_workspace_invalid(
            ProviderWorkspaceRequiredError("provider_workspace_required:http_400")
        )

    def test_no_exception_reads_as_the_missing_case(self) -> None:
        """The safe default asks for a value rather than doubting one."""
        from raiker.models.readiness import _is_workspace_invalid

        assert not _is_workspace_invalid(None)


class TestTheRefusalIsClassifiedByWhatItMeansNotHowItIsWorded:
    """BUG-277 — the classifier matched three sentences, and the provider sends
    a fourth.

    A live round pasted an identity-linked key into the Models page and was told
    *"Anthropic could not be reached. Check that it is running and reachable from
    this device."* The provider had answered in full and precisely; Raiker had
    matched none of its literals and fallen back to `provider_http_error:http_400`,
    for which no guidance exists.

    Every repair FIXED-370 and FIXED-372 built was downstream of that match, so
    the whole of it — the classification, the Workspace ID field, the remediation
    naming that field — was unreachable for the message the provider sends.

    A list of exact sentences is a bet that a message Raiker does not control
    will keep its wording. The bet has been lost once, so the classification is
    now the conjunction that survives rewording: the body names a workspace,
    **and** says one is absent.
    """

    def test_the_body_the_provider_actually_sends_is_classified(self) -> None:
        assert needs_workspace_id(400, LIVE_MISSING_BODY) is True
        assert workspace_id_rejected(400, LIVE_MISSING_BODY) is False

    def test_it_reaches_the_owner_as_a_repair_rather_than_a_status(self) -> None:
        from raiker.models.providers.anthropic_messages import _map_status

        exc = _map_status(400, model="m", body=LIVE_MISSING_BODY)
        assert isinstance(exc, ProviderWorkspaceRequiredError)
        assert provider_error_code(exc) == "provider_workspace_required:http_400"

    @pytest.mark.parametrize("module", ["anthropic_messages", "openai_compatible"])
    def test_both_providers_classify_it(self, module: str) -> None:
        mapper = __import__(
            f"raiker.models.providers.{module}", fromlist=["_map_status"]
        )._map_status
        assert isinstance(
            mapper(400, model="m", body=LIVE_MISSING_BODY), ProviderWorkspaceRequiredError
        )

    def test_the_wording_it_used_to_match_still_matches(self) -> None:
        """Widened, not replaced. A provider that goes back to the old phrasing,
        or another that borrows it, is classified exactly as before."""
        assert needs_workspace_id(400, MISSING_BODY) is True

    def test_naming_a_workspace_is_not_enough_on_its_own(self) -> None:
        """The conjunction is what keeps this from swallowing ordinary 400s.

        Widening a match is normally the wrong direction; it is right here only
        because both halves have to hold, so a 400 that merely mentions a
        workspace keeps its own classification.
        """
        assert needs_workspace_id(400, '{"error":{"message":"your workspace is archived"}}') is False
        assert needs_workspace_id(400, '{"error":{"message":"max_tokens is required"}}') is False

    def test_a_rejected_id_still_wins_over_a_missing_one(self) -> None:
        """The invalid body says "must be a valid workspace ID", which now
        satisfies both halves of the missing test too. It is checked first, and
        this is the test that keeps it checked first — asking again for a value
        the owner already supplied is the one answer that helps nobody."""
        assert needs_workspace_id(400, INVALID_BODY) is False
        assert workspace_id_rejected(400, INVALID_BODY) is True

    def test_nothing_from_the_live_body_reaches_the_code(self) -> None:
        from raiker.models.providers.anthropic_messages import _map_status

        body = LIVE_MISSING_BODY.replace("a workspace", "workspace wrkspc_secret9")
        code = provider_error_code(_map_status(400, model="m", body=body))
        assert code == "provider_workspace_required:http_400"
        assert "secret9" not in code
