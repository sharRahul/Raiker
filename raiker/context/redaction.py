from __future__ import annotations

import re
from collections.abc import Callable

REDACTED_SECRET = "[REDACTED_SECRET]"
REDACTED_CREDENTIAL = "[REDACTED_CREDENTIAL]"
REDACTED_TOKEN = "[REDACTED_TOKEN]"
REDACTED_EMAIL = "[REDACTED_EMAIL]"
REDACTED_PRIVATE_KEY = "[REDACTED_PRIVATE_KEY]"
REDACTED_CARD = "[REDACTED_CARD]"
REDACTED_ACCOUNT = "[REDACTED_ACCOUNT]"
REDACTED_ID = "[REDACTED_ID]"

# A lowercase snake_case identifier (two or more words joined by underscores).
# Machine-readable reason codes / capability ids look like this and carry no
# entropy, so the high-entropy fallback must not mistake them for secrets. Real
# credentials (API keys, base64/hex tokens) always carry mixed case and/or
# digits and never match this shape.
_SNAKE_IDENTIFIER = re.compile(r"[a-z]+(?:_[a-z]+)+")

# A server-issued record identifier: a lowercase prefix followed by underscore-
# joined lowercase-alphanumeric segments (`sess_inbox_principal_user_e8b7…`,
# `task_f9d9…`). Offered only for values whose *key* names an id (see
# ``raiker/api/redaction.py``), never for free-form text: the shape is loose
# enough that a lowercase secret containing an underscore would match it, and
# only the caller knows the field is an id rather than prose.
_SERVER_ISSUED_ID = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)+")


def _is_segmented_path(token: str) -> bool:
    """True for a run that is only long because its *segments* were joined.

    ``sessions/sess_…/attachments/att_…/preview/pdf`` and
    ``home/user/.raiker/events/sess_…/turn_….jsonl`` are not opaque blobs: no
    part of either carries 40 characters of entropy, and the run reached the
    fallback only because slashes joined them. A credential is the opposite —
    its entropy lives in one unbroken segment — so a key embedded in a path
    (``v1/keys/<44 chars>``) still fails this test and is still redacted.

    This is deliberately *not* applied to free-form text. It is offered only for
    values the API says are locators (see ``raiker/api/redaction.py``), because
    a base64 secret containing a slash could otherwise split into two
    under-threshold halves and slip through.
    """
    return "/" in token and all(len(part) < 40 for part in token.split("/"))


def _redact_high_entropy(match: re.Match[str]) -> str:
    token = match.group(0)
    if _SNAKE_IDENTIFIER.fullmatch(token):
        return token
    return REDACTED_SECRET


def _redact_high_entropy_in_locator(match: re.Match[str]) -> str:
    """The fallback as applied to a value the caller has declared a locator."""
    token = match.group(0)
    if _is_segmented_path(token):
        return token
    return _redact_high_entropy(match)


def _redact_high_entropy_in_identifier(match: re.Match[str]) -> str:
    """The fallback as applied to a value the caller has declared an id.

    A record id is long because its prefixes were joined, exactly like a path:
    ``sess_inbox_principal_user_<16 hex>`` crosses 40 characters without holding
    40 characters of entropy anywhere. Anything under an id key that does *not*
    look like a server-issued id — mixed case, base64 padding, a dash-separated
    token — still redacts.
    """
    token = match.group(0)
    if _SERVER_ISSUED_ID.fullmatch(token):
        return token
    return _redact_high_entropy(match)


def _redact_spoken_credential(match: re.Match[str]) -> str:
    """Redact "the password is hunter2" but not "the secret is out".

    The pattern already requires the credential word to sit *immediately* before
    the copula, so prose with an intervening noun ("the secret project code is
    ORCHID-9") never reaches here. This second filter drops the remaining false
    positives by keeping ordinary short English words, which no credential is.
    """
    value = match.group("value")
    if value.isalpha() and len(value) < 12:
        return match.group(0)
    return REDACTED_SECRET


# Ordered (pattern, replacement) pairs. Private keys and known token shapes are matched
# before the broad high-entropy fallback so they get specific placeholders. Each pattern is
# deterministic and never raises on unusual input.
_PATTERNS: tuple[tuple[re.Pattern[str], Callable[[re.Match[str]], str] | str], ...] = (
    (
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
        REDACTED_PRIVATE_KEY,
    ),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"), REDACTED_TOKEN),
    (re.compile(r"\bghp_[A-Za-z0-9]{20,}"), REDACTED_TOKEN),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"), REDACTED_TOKEN),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), REDACTED_TOKEN),
    (
        re.compile(r"\bauthorization\s*:\s*bearer\s+[A-Za-z0-9._\-]{8,}", re.IGNORECASE),
        REDACTED_TOKEN,
    ),
    (re.compile(r"\bbearer\s+[A-Za-z0-9._\-]{8,}", re.IGNORECASE), REDACTED_TOKEN),
    (
        re.compile(
            r"\b(?:api[_-]?key|secret|token|password|passwd|pwd)\s*[:=]\s*['\"]?[^\s'\"]{3,}",
            re.IGNORECASE,
        ),
        REDACTED_SECRET,
    ),
    # Credentials disclosed in prose rather than as an assignment ("the token is
    # abc123"). The keyword must be the word immediately before the copula, so
    # sentences that merely mention a secret ("the secret project code is
    # ORCHID-9") are untouched; the callable then spares plain English values.
    (
        re.compile(
            r"\b(?:api[_-]?key|secret|token|password|passwd|pwd)s?\s+(?:is|was)\s*[:=]?\s*"
            r"['\"]?(?P<value>[^\s'\"]{2,}[^\s'\".,;:!?])",
            re.IGNORECASE,
        ),
        _redact_spoken_credential,
    ),
    (
        re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
        REDACTED_EMAIL,
    ),
    # Bank/card-like numbers
    (re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"), REDACTED_CARD),
    (
        re.compile(
            r"\b(?:account|iban|bic|swift|routing)\s*[:=#]?\s*['\"]?[A-Z0-9]{8,}\b", re.IGNORECASE
        ),
        REDACTED_ACCOUNT,
    ),
    # Medical identifiers (NHS/SSN-like patterns)
    (re.compile(r"\b\d{3}[-\s]?\d{3}[-\s]?\d{4}\b"), REDACTED_ID),
    # High-entropy fallback for long opaque strings (kept last so specific shapes
    # win). A callable replacement spares lowercase snake_case reason codes /
    # capability ids, which are long but carry no secret entropy.
    (re.compile(r"\b[A-Za-z0-9+/_\-]{40,}\b"), _redact_high_entropy),
)

# The same rules with a path-aware fallback, used only for values whose *key*
# declares them a locator. Every specific credential shape above still applies:
# a ``token=…`` query parameter or a ``Bearer …`` string inside a URL is matched
# before the fallback is ever reached.
_LOCATOR_PATTERNS: tuple[tuple[re.Pattern[str], Callable[[re.Match[str]], str] | str], ...] = (
    _PATTERNS[:-1] + ((_PATTERNS[-1][0], _redact_high_entropy_in_locator),)
)

# The same rules with an id-aware fallback, used only for values whose *key*
# declares them a record identifier.
_IDENTIFIER_PATTERNS: tuple[tuple[re.Pattern[str], Callable[[re.Match[str]], str] | str], ...] = (
    _PATTERNS[:-1] + ((_PATTERNS[-1][0], _redact_high_entropy_in_identifier),)
)


def _redact_high_entropy_in_digest(match: re.Match[str]) -> str:
    value = match.group(0)
    if re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", value):
        return value
    return _redact_high_entropy(match)


_DIGEST_PATTERNS: tuple[tuple[re.Pattern[str], Callable[[re.Match[str]], str] | str], ...] = (
    _PATTERNS[:-1] + ((_PATTERNS[-1][0], _redact_high_entropy_in_digest),)
)


# ── Exact secrets, registered while they are in use ──────────────────────────
#
# The pattern scan below recognises credential *shapes*. That is the right tool
# for text nobody warned us about, and the wrong one for a credential we are
# knowingly handing to a child process: a GitHub token echoed back by a command,
# split across a wrapped line, or embedded in a remote URL may not look like a
# token by the time it reaches a log.
#
# So a caller that is about to lend a secret registers the exact value first.
# Every redaction pass then removes that literal wherever it appears, whatever
# shape it has taken, for exactly as long as the loan lasts. The registry holds
# values in memory only, is never persisted, and is emptied by the same
# ``finally`` that ends the loan.
_ACTIVE_SECRETS: dict[str, int] = {}
_SECRETS_LOCK = __import__("threading").Lock()

#: Below this length a "secret" is too short to remove safely — redacting a
#: four-character value would blank out unrelated text everywhere it occurred.
MIN_REGISTERED_SECRET = 8


def remember_secret(value: str) -> None:
    """Redact this exact value from every scan until it is forgotten.

    Reference-counted, so two overlapping loans of the same token do not have the
    first ``forget_secret`` stop redacting it for the second.
    """
    text = (value or "").strip()
    if len(text) < MIN_REGISTERED_SECRET:
        return
    with _SECRETS_LOCK:
        _ACTIVE_SECRETS[text] = _ACTIVE_SECRETS.get(text, 0) + 1


def forget_secret(value: str) -> None:
    text = (value or "").strip()
    with _SECRETS_LOCK:
        remaining = _ACTIVE_SECRETS.get(text, 0) - 1
        if remaining > 0:
            _ACTIVE_SECRETS[text] = remaining
        else:
            _ACTIVE_SECRETS.pop(text, None)


def registered_secret_count() -> int:
    """How many secrets are on loan. For tests and diagnostics; never the values."""
    with _SECRETS_LOCK:
        return len(_ACTIVE_SECRETS)


def _strip_registered_secrets(text: str) -> tuple[str, bool]:
    with _SECRETS_LOCK:
        secrets = sorted(_ACTIVE_SECRETS, key=len, reverse=True)
    changed = False
    for secret in secrets:
        if secret in text:
            text = text.replace(secret, REDACTED_CREDENTIAL)
            changed = True
    return text, changed


def redact_text(
    text: str,
    *,
    locator_value: bool = False,
    identifier_value: bool = False,
    digest_value: bool = False,
) -> tuple[str, bool]:
    """Mask obvious secrets/tokens/emails/private keys in ``text``.

    Returns ``(redacted_text, changed)``. Deterministic and total: it never raises on
    unusual input and never removes the whole item, it only substitutes sensitive spans.

    ``locator_value`` says the caller knows this string is a URL or filesystem
    path, and ``identifier_value`` that it is a server-issued record id — facts
    only the caller has, from the field's key. Each relaxes the high-entropy
    fallback for one shape and nothing else; every credential shape is still
    matched. Both default off, so free-form text (model output, chat titles,
    document excerpts) keeps the strict scan.
    """

    if not isinstance(text, str):
        text = str(text)
    patterns = _PATTERNS
    if locator_value:
        patterns = _LOCATOR_PATTERNS
    elif identifier_value:
        patterns = _IDENTIFIER_PATTERNS
    elif digest_value:
        patterns = _DIGEST_PATTERNS
    # Registered secrets come out first, and unconditionally. A value we knowingly
    # lent must not depend on a shape heuristic recognising it — this pass runs on
    # every mode, including the relaxed locator/identifier ones, because a token
    # embedded in a remote URL is exactly the case those modes relax for.
    redacted, _ = _strip_registered_secrets(text)
    for pattern, replacement in patterns:
        redacted = pattern.sub(replacement, redacted)
    return redacted, redacted != text
