from __future__ import annotations

import re

REDACTED_SECRET = "[REDACTED_SECRET]"
REDACTED_TOKEN = "[REDACTED_TOKEN]"
REDACTED_EMAIL = "[REDACTED_EMAIL]"
REDACTED_PRIVATE_KEY = "[REDACTED_PRIVATE_KEY]"

# Ordered (pattern, replacement) pairs. Private keys and known token shapes are matched
# before the broad high-entropy fallback so they get specific placeholders. Each pattern is
# deterministic and never raises on unusual input.
_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
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
    (
        re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
        REDACTED_EMAIL,
    ),
    # Bank/card-like numbers
    (re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"), "[REDACTED_CARD]"),
    (re.compile(r"\b(?:account|iban|bic|swift|routing)\s*[:=#]?\s*['\"]?[A-Z0-9]{8,}\b", re.IGNORECASE), "[REDACTED_ACCOUNT]"),
    # Medical identifiers (NHS/SSN-like patterns)
    (re.compile(r"\b\d{3}[-\s]?\d{3}[-\s]?\d{4}\b"), "[REDACTED_ID]"),
    # High-entropy fallback for long opaque strings (kept last so specific shapes win).
    (re.compile(r"\b[A-Za-z0-9+/_\-]{40,}\b"), REDACTED_SECRET),
)


def redact_text(text: str) -> tuple[str, bool]:
    """Mask obvious secrets/tokens/emails/private keys in ``text``.

    Returns ``(redacted_text, changed)``. Deterministic and total: it never raises on
    unusual input and never removes the whole item, it only substitutes sensitive spans.
    """

    if not isinstance(text, str):
        text = str(text)
    redacted = text
    for pattern, replacement in _PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted, redacted != text
