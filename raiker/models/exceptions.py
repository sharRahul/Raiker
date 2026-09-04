from __future__ import annotations

import re


class ModelProviderError(Exception):
    """Base class for safe-to-log model provider errors."""


class ProviderConfigurationError(ModelProviderError):
    pass


class ProviderPolicyError(ModelProviderError):
    pass


class ProviderWorkspaceRequiredError(ModelProviderError):
    """BUG-272 — the key is valid and needs a workspace named alongside it.

    Its own class rather than a configuration error, because the two send the
    owner to different places: a misconfiguration is Raiker's settings, and this
    is the shape of the credential they pasted.

    Carries two reason codes rather than two classes, because both are repaired
    in the same place — the connection's *Workspace ID* field — and every caller
    that catches one wants the other:

    * ``provider_workspace_required`` — no workspace was named at all;
    * ``provider_workspace_invalid`` — one was named and the provider refused it.
    """


class ProviderConnectionError(ModelProviderError):
    pass


class ProviderTimeoutError(ModelProviderError):
    pass

class ProviderAuthenticationError(ModelProviderError):
    pass


class ProviderRateLimitError(ModelProviderError):
    pass


class ProviderQuotaExhaustedError(ModelProviderError):
    """The account is reachable and authenticated but has nothing left to spend.

    Distinct from a rate limit (waiting fixes that) and from an authentication
    failure (a new key fixes that). Only adding credit or raising the account's
    quota fixes this, so it must not be reported as either.
    """


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
    "ProviderQuotaExhaustedError": "provider_quota_exhausted",
    "ProviderWorkspaceRequiredError": "provider_workspace_required",
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

# Statuses a provider may use to say "your account cannot pay for this". The
# status alone is never enough — 400 and 429 are also ordinary failures — so a
# marker below has to appear in the body as well, except for 402, whose whole
# meaning is Payment Required.
_QUOTA_STATUSES = frozenset({400, 402, 403, 429})

# Deliberately specific. A bare "quota" would swallow Gemini's per-minute rate
# limit ("Quota exceeded for quota metric …"), which a retry does fix, so only
# wording that names money or a spent allowance counts.
_QUOTA_MARKERS: tuple[str, ...] = (
    "insufficient_quota",
    "insufficient quota",
    "exceeded your current quota",
    "credit balance",
    "purchase credits",
    "insufficient credits",
    "not enough credits",
    "billing details",
    "billing_hard_limit_reached",
    "plans & billing",
    "plans and billing",
    "payment required",
)


# BUG-272 — an identity-linked key needs a workspace named on every request.
#
# Anthropic answers a perfectly valid key with HTTP 400 and a body that says
# exactly what is missing. Without this the owner met `provider_http_error:http_400`
# on a key that is not broken and has nothing to rotate — the same shape as
# FIXED-355, where a rejected key was reported as a network failure.
#
# Classified from the body for the same reason quota is: the status alone means
# nothing (400 is also an ordinary bad request), and the fix is the owner's to
# make rather than a retry's.
# BUG-277 — the markers matched one wording, and the provider sends another.
#
# A live round on 2026-09-04 pasted an identity-linked key and met
# `provider_http_error:http_400` → *"Anthropic could not be reached. Check that
# it is running and reachable from this device."* The provider had answered in
# full, and precisely:
#
#     This API key is not scoped to a workspace, so this request must include
#     the anthropic-workspace-id header with the ID of the workspace to use.
#
# Not one of the three literals below it matched, so every repair FIXED-370 and
# FIXED-372 built — the classification, the Workspace ID field, the remediation
# that names it — was unreachable for the message the provider actually sends.
#
# **So this is no longer a list of sentences.** A list of sentences is a bet that
# a message Raiker does not control will keep its wording, and that bet has now
# been lost once. The classification is a *conjunction* instead: the body has to
# mention the workspace **and** say that one is absent. Both halves are the
# stable part of any phrasing of this refusal; the sentence around them is not.
# Widening a match is normally the wrong direction, and it is right here for one
# reason worth stating: the alternative it replaces is not a stricter answer, it
# is *no* answer — an owner sent to debug a network that is working.

#: The subject the refusal has to be about. Both spellings, and the header name,
#: because a message may name only the header it wanted.
_WORKSPACE_SUBJECTS: tuple[str, ...] = (
    "workspace",
    "workspace_id",
    "workspace-id",
)

#: What the message has to say about that subject for it to be a *missing* one.
#: Every entry is a way of saying "there isn't one and there needs to be".
_WORKSPACE_ABSENT_MARKERS: tuple[str, ...] = (
    "is required",
    "are required",
    "must include",
    "must be included",
    "must specify",
    "must provide",
    "not scoped",
    "no workspace",
    "missing",
    "identity-linked",
    "identity linked",
)


# BUG-274 — the owner named a workspace and the provider would not have it.
#
# The second half of the same conversation: once Raiker can send a workspace id,
# it can send a wrong one, and that has to read as "fix this field" rather than
# as the missing-workspace message, which would send the owner to add something
# they have already added.
_WORKSPACE_INVALID_MARKERS: tuple[str, ...] = (
    "must be a valid workspace id",
    "must be a valid workspace_id",
    "invalid workspace id",
    "invalid workspace_id",
    "workspace not found",
)


def needs_workspace_id(status: int, body: str) -> bool:
    """True when the provider refused because no workspace was named.

    ``body`` is read only to classify; nothing from it is kept, exactly as in
    :func:`is_quota_exhausted`. The caller raises a fixed reason code, so a
    provider that names an organisation or an account in this message cannot
    carry it into an event, an API response, or the readiness record.
    """
    if status != 400:
        return False
    haystack = body.casefold()
    if any(marker in haystack for marker in _WORKSPACE_INVALID_MARKERS):
        # A rejected id is not a missing one. Checked first because the two
        # bodies share vocabulary and only this one names a value the owner
        # already supplied.
        return False
    # BUG-277 — both halves, not one sentence. A 400 that mentions a workspace
    # but says nothing about one being absent is an ordinary bad request and
    # keeps its own classification; a 400 that says something is required but
    # never names a workspace is about some other field.
    return any(subject in haystack for subject in _WORKSPACE_SUBJECTS) and any(
        marker in haystack for marker in _WORKSPACE_ABSENT_MARKERS
    )


def workspace_id_rejected(status: int, body: str) -> bool:
    """True when the provider refused the workspace the owner named.

    Read under the same rule as :func:`needs_workspace_id`: the body decides the
    classification and nothing from it survives the call, so a message naming an
    organisation cannot reach an event or a readiness record.
    """
    if status != 400:
        return False
    haystack = body.casefold()
    return any(marker in haystack for marker in _WORKSPACE_INVALID_MARKERS)


def is_quota_exhausted(status: int, body: str) -> bool:
    """True when this response means the account is out of credit or quota.

    ``body`` is read only to classify; nothing from it is ever kept. The caller
    raises a fixed reason code, so a provider that puts an account identifier or
    an email address in its billing message cannot carry it into an event, an
    API response, or the readiness record.
    """
    if status not in _QUOTA_STATUSES:
        return False
    if status == 402:
        return True
    haystack = body.casefold()
    return any(marker in haystack for marker in _QUOTA_MARKERS)

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


def stream_failure(exc: Exception) -> Exception:
    """The exception a streaming adapter should raise for *exc* (BUG-72).

    A stream adapter used to answer every failure with one code. Anything the
    transport or the HTTP status had already classified — an expired key, an
    exhausted balance, a rate limit, a closed connection — arrived at the owner
    as ``provider_stream_failed``, which says only that a stream ended and sends
    them to debug the wrong thing. So:

    * an already-classified provider error is returned **unchanged**, keeping
      the code its own layer chose;
    * anything else is wrapped in :class:`ProviderStreamError` **carrying the
      underlying exception type** — ``provider_stream_failed:TimeoutError`` —
      so the class is still in the reason code rather than only in a traceback
      nobody kept. The type name is class metadata, never provider text, so
      this cannot carry a credential or a body fragment into an event.
    """
    if isinstance(exc, ModelProviderError):
        return exc
    return ProviderStreamError(f"provider_stream_failed:{type(exc).__name__}")


# Owner-facing sentence per reason-code family, with the repair. A raw code as
# the whole answer is the defect FIXED-01 removed from the Models page; a turn
# that fails must not put one back in the transcript (BUG-72).
_PROVIDER_ERROR_SENTENCES: tuple[tuple[str, str], ...] = (
    (
        "provider_auth_failed",
        "the provider rejected the saved credential. Update the key on Models, then try again.",
    ),
    (
        "provider_authentication_failed",
        "the provider rejected the saved credential. Update the key on Models, then try again.",
    ),
    (
        "provider_quota_exhausted",
        "the provider accepted the credential but the account has no credit or quota left. "
        "Add credit or raise the quota, then try again.",
    ),
    (
        "provider_rate_limited",
        "the provider is rate limiting this account right now. Wait a moment and try again.",
    ),
    (
        # BUG-274 — the workspace the owner named was refused. Its own entry
        # rather than a shared one, because asking again for a value already
        # supplied is the answer that helps nobody.
        "provider_workspace_invalid",
        "the provider did not recognise the workspace named with this key. "
        "Check the workspace ID on the connection in Models.",
    ),
    (
        # BUG-272 — the credential is fine and there is nothing to rotate.
        # BUG-274 made it actionable: Raiker can send the workspace, so the
        # remediation names the field rather than another key.
        "provider_workspace_required",
        "the provider needs a workspace named on every request for this kind of key. "
        "Add the workspace ID to the connection in Models; the key itself is fine.",
    ),
    (
        # BUG-76 — the circuit breaker, not a provider answer. Saying so is the
        # whole point: the owner is not waiting on a flaky network, they are
        # looking at a component Raiker has stopped calling until it recovers.
        "provider_contained",
        "every model this turn could use has been contained after repeated failures. "
        "Raiker will retry one call after a short pause; resume it yourself in Settings "
        "→ Security & sign-in if you have fixed it.",
    ),
    (
        "provider_timeout",
        "the provider did not answer in time. Try again, or choose a different model on Models.",
    ),
    (
        "model_not_found",
        "the selected model does not exist on that provider. Choose a model on Models.",
    ),
    (
        "provider_capability_unsupported",
        "the selected model cannot do what this turn needed. "
        "Choose a different model on Models.",
    ),
    (
        "provider_misconfigured",
        "the model profile is incomplete. Check the connection on Models.",
    ),
    (
        "provider_policy_denied",
        "the current model policy blocks that provider. Review it on Permissions.",
    ),
    (
        "provider_invalid_response",
        "the provider returned a response Raiker could not read. "
        "Try again; if it repeats, choose a different model.",
    ),
    (
        "provider_cancelled",
        "the request was cancelled before the provider answered.",
    ),
    (
        "provider_stream_failed",
        "the connection to the provider ended before the answer did. Try again.",
    ),
    (
        "provider_connection_failed",
        "Raiker could not reach the provider. "
        "Check the network and the egress allowlist, then try again.",
    ),
    (
        "provider_unavailable",
        "the provider is returning errors of its own. Try again shortly.",
    ),
    (
        "provider_http_error",
        "the provider refused the request. Run the readiness check on Models to see why.",
    ),
    # BUG-207 — the remediation for this one is on the composer, not on Models.
    # The default sentence sends the owner to run a readiness check, which will
    # pass: the model is reachable, it just will not think in either spelling
    # this provider offers.
    (
        "reasoning_unsupported",
        "this model would not think before answering, in any form this provider "
        "offers. Set Thinking back to default, or choose a model that supports it.",
    ),
)


def provider_error_sentence(code: str) -> str:
    """One plain sentence explaining *code* and what to do about it."""
    base = code.split(":", 1)[0]
    for prefix, sentence in _PROVIDER_ERROR_SENTENCES:
        if base == prefix:
            return sentence
    return "the provider did not complete the request. Run the readiness check on Models."


def provider_failure_message(code: str) -> str:
    """The turn-level answer shown when no provider could complete the turn.

    Leads with what happened in the owner's language and keeps the machine code
    where support and the audit trail can still read it.
    """
    return (
        f"I could not finish that: {provider_error_sentence(code)} "
        f"(model_unavailable: {code})"
    )
