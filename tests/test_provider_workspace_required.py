"""BUG-272 — a valid key reported as a bare HTTP status.

Found on 2026-09-03 while driving the live suite against a real Anthropic key.
The key was not broken and there was nothing to rotate: it is *identity-linked*,
and Anthropic requires a workspace named on every request made with one. The
provider said exactly that, and Raiker reported
`provider_http_error:http_400` — a code with no repair in it.

That is the same shape as
[FIXED-355](../docs/plans/FIXED_ITEMS.md), where a rejected key was reported as
a network failure: the owner is sent to debug the wrong thing.

Classified from the body, exactly as quota is, because the status alone means
nothing — 400 is also an ordinary bad request — and for the same reason nothing
from the body is kept: the reason code is fixed, so a provider that names an
organisation or an account in this message cannot carry it into an event.
"""

from __future__ import annotations

import pytest

from raiker.models.exceptions import (
    ProviderConnectionError,
    ProviderQuotaExhaustedError,
    ProviderWorkspaceRequiredError,
    needs_workspace_id,
    provider_error_code,
)

ANTHROPIC_BODY = (
    '{"type":"error","error":{"type":"invalid_request_error","message":'
    '"anthropic-workspace-id is required when authenticating with an identity-linked '
    'API key; send the id of the workspace this request acts in."},"request_id":null}'
)


class TestClassification:
    def test_the_real_body_is_recognised(self) -> None:
        assert needs_workspace_id(400, ANTHROPIC_BODY) is True

    @pytest.mark.parametrize(
        "body",
        [
            '{"error":"malformed json"}',
            '{"error":{"message":"max_tokens is required"}}',
            "",
        ],
    )
    def test_an_ordinary_bad_request_is_not(self, body: str) -> None:
        """400 is the busiest status a provider has; only the body says which one."""
        assert needs_workspace_id(400, body) is False

    @pytest.mark.parametrize("status", [401, 403, 429, 500])
    def test_only_a_400_is_considered(self, status: int) -> None:
        assert needs_workspace_id(status, ANTHROPIC_BODY) is False


class TestBothProvidersRaiseIt:
    def test_anthropic(self) -> None:
        from raiker.models.providers.anthropic_messages import _map_status

        exc = _map_status(400, model="claude-haiku-4-5-20251001", body=ANTHROPIC_BODY)
        assert isinstance(exc, ProviderWorkspaceRequiredError)
        assert provider_error_code(exc) == "provider_workspace_required:http_400"

    def test_openai_compatible(self) -> None:
        from raiker.models.providers.openai_compatible import _map_status

        exc = _map_status(400, model="gpt-x", body=ANTHROPIC_BODY)
        assert isinstance(exc, ProviderWorkspaceRequiredError)

    def test_an_ordinary_400_is_still_a_connection_error(self) -> None:
        from raiker.models.providers.anthropic_messages import _map_status

        exc = _map_status(400, model="m", body='{"error":"bad"}')
        assert isinstance(exc, ProviderConnectionError)
        assert not isinstance(exc, ProviderWorkspaceRequiredError)

    def test_it_does_not_steal_the_quota_case(self) -> None:
        """Anthropic answers an empty balance with 400 too, and that is a different repair."""
        from raiker.models.providers.anthropic_messages import _map_status

        exc = _map_status(400, model="m", body='{"error":{"message":"credit balance is too low"}}')
        assert isinstance(exc, ProviderQuotaExhaustedError)


class TestTheOwnerIsToldWhatToDo:
    def test_the_reason_code_carries_a_repair(self) -> None:
        from raiker.models.exceptions import _PROVIDER_ERROR_SENTENCES

        remedy = dict(_PROVIDER_ERROR_SENTENCES)["provider_workspace_required"]
        # Not "update the key": the key is fine, and its *shape* is the problem.
        assert "identity-linked" in remedy
        assert "rotate" not in remedy.lower()

    def test_nothing_from_the_body_reaches_the_code(self) -> None:
        """A provider that names an account in this message cannot leak it."""
        from raiker.models.providers.anthropic_messages import _map_status

        body = ANTHROPIC_BODY.replace("identity-linked", "identity-linked (acct_secret123)")
        code = provider_error_code(_map_status(400, model="m", body=body))
        assert code == "provider_workspace_required:http_400"
        assert "secret123" not in code
