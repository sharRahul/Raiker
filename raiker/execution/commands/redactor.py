from __future__ import annotations

import codecs
from collections.abc import Iterable

from raiker.context.redaction import (
    REDACTED_ACCOUNT,
    REDACTED_CARD,
    REDACTED_CREDENTIAL,
    REDACTED_EMAIL,
    REDACTED_ID,
    REDACTED_PRIVATE_KEY,
    REDACTED_SECRET,
    REDACTED_TOKEN,
    redact_text,
)

_PLACEHOLDERS = (
    REDACTED_ACCOUNT,
    REDACTED_CARD,
    REDACTED_CREDENTIAL,
    REDACTED_EMAIL,
    REDACTED_ID,
    REDACTED_PRIVATE_KEY,
    REDACTED_SECRET,
    REDACTED_TOKEN,
)
_PRIVATE_KEY_BEGIN = "-----BEGIN"
_PRIVATE_KEY_END = "-----END"
_PRIVATE_KEY_END_TAIL = "PRIVATE KEY-----"
_DEFAULT_MAX_PENDING_CHARACTERS = 64 * 1024


class StreamingRedactor:
    """Redact a byte stream without releasing an undecidable suffix.

    The existing text redactor is the one policy contract. This adapter keeps a
    complete-line boundary because every ordinary pattern is line-local. A
    private-key start marker keeps the whole structured value pending until its
    end marker arrives, and exact registered-secret prefixes move the boundary
    backward when they could cross it. Bytes leave only after no current or
    future chunk can change their classification; invalid UTF-8 is handled by
    one incremental decoder across chunks.
    """

    def __init__(
        self,
        *,
        registered: Iterable[str] = (),
        locator_value: bool = False,
        identifier_value: bool = False,
        digest_value: bool = False,
        max_pending_characters: int = _DEFAULT_MAX_PENDING_CHARACTERS,
    ) -> None:
        if max_pending_characters < 1:
            raise ValueError("max_pending_characters_must_be_positive")
        self._registered = tuple(sorted({value for value in registered if value}, key=len, reverse=True))
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._pending = ""
        self._finished = False
        self._max_pending_characters = max_pending_characters
        self._suppression_until: str | None = None
        self._mode = {
            "locator_value": locator_value,
            "identifier_value": identifier_value,
            "digest_value": digest_value,
        }
        self.redaction_count = 0

    def feed(self, data: bytes) -> bytes:
        if self._finished:
            raise RuntimeError("streaming_redactor_finished")
        self._pending += self._decoder.decode(data, final=False)
        if self._suppression_until is not None:
            self._consume_suppressed_input()
            if self._suppression_until is not None:
                self._pending = ""
                return b""
        cut = self._pending.rfind("\n") + 1
        if cut == 0:
            if len(self._pending) > self._max_pending_characters:
                self._begin_fail_closed_suppression()
                return REDACTED_SECRET.encode("utf-8")
            return b""
        begin = self._pending.rfind(_PRIVATE_KEY_BEGIN, 0, cut)
        end = self._pending.rfind(_PRIVATE_KEY_END, 0, cut)
        if begin > end:
            cut = begin
        cut = self._registered_secret_boundary(cut)
        if cut == 0:
            if len(self._pending) > self._max_pending_characters:
                self._begin_fail_closed_suppression()
                return REDACTED_SECRET.encode("utf-8")
            return b""
        ready, self._pending = self._pending[:cut], self._pending[cut:]
        return self._redact(ready)

    def _begin_fail_closed_suppression(self) -> None:
        self._suppression_until = (
            _PRIVATE_KEY_END_TAIL if _PRIVATE_KEY_BEGIN in self._pending else "\n"
        )
        self._pending = ""
        self.redaction_count += 1

    def _consume_suppressed_input(self) -> None:
        assert self._suppression_until is not None
        boundary = self._pending.find(self._suppression_until)
        if boundary == -1:
            return
        if self._suppression_until == _PRIVATE_KEY_END_TAIL:
            self._pending = self._pending[boundary + len(self._suppression_until) :]
            self._suppression_until = "\n"
            self._consume_suppressed_input()
            return
        self._pending = self._pending[boundary:]
        self._suppression_until = None

    def _registered_secret_boundary(self, cut: int) -> int:
        """Move *cut* before any exact secret that might cross it."""
        for secret in self._registered:
            start = max(0, cut - len(secret) + 1)
            crossing = self._pending.find(secret, start)
            if crossing != -1 and crossing < cut < crossing + len(secret):
                cut = min(cut, crossing)
            maximum = min(len(secret) - 1, cut)
            for length in range(maximum, 0, -1):
                if self._pending[cut - length : cut] == secret[:length]:
                    cut -= length
                    break
        return cut

    def finish(self) -> bytes:
        if self._finished:
            return b""
        self._finished = True
        self._pending += self._decoder.decode(b"", final=True)
        if self._suppression_until is not None:
            self._pending = ""
            self._suppression_until = None
            return b""
        ready, self._pending = self._pending, ""
        return self._redact(ready)

    def _redact(self, text: str) -> bytes:
        for secret in self._registered:
            text = text.replace(secret, REDACTED_CREDENTIAL)
        redacted, _changed = redact_text(text, **self._mode)
        self.redaction_count += sum(redacted.count(placeholder) for placeholder in _PLACEHOLDERS)
        return redacted.encode("utf-8")


def stream_redact(
    *parts: bytes,
    registered: Iterable[str] = (),
    locator_value: bool = False,
    identifier_value: bool = False,
    digest_value: bool = False,
) -> bytes:
    redactor = StreamingRedactor(
        registered=registered,
        locator_value=locator_value,
        identifier_value=identifier_value,
        digest_value=digest_value,
    )
    return b"".join([*(redactor.feed(part) for part in parts), redactor.finish()])
