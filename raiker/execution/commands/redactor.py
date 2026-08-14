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


class StreamingRedactor:
    """Redact a byte stream without releasing an undecidable suffix.

    The existing text redactor is the one policy contract. This adapter keeps a
    conservative suffix large enough for every bounded rule and for the longest
    exact credential currently on loan. A private-key start marker keeps the
    whole structured value pending until its end marker arrives. Bytes only
    leave after the redactor has proved they cannot become part of a later
    match; invalid UTF-8 is handled by one incremental decoder across chunks.
    """

    def __init__(
        self,
        *,
        registered: Iterable[str] = (),
        locator_value: bool = False,
        identifier_value: bool = False,
        digest_value: bool = False,
        rule_window: int = 8192,
    ) -> None:
        self._registered = tuple(sorted({value for value in registered if value}, key=len, reverse=True))
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._pending = ""
        self._finished = False
        self._mode = {
            "locator_value": locator_value,
            "identifier_value": identifier_value,
            "digest_value": digest_value,
        }
        self._holdback = max(rule_window, *(len(value) + 1 for value in self._registered), 1)
        self.redaction_count = 0

    def feed(self, data: bytes) -> bytes:
        if self._finished:
            raise RuntimeError("streaming_redactor_finished")
        self._pending += self._decoder.decode(data, final=False)
        cut = max(0, len(self._pending) - self._holdback)
        if cut == 0:
            return b""
        begin = self._pending.rfind(_PRIVATE_KEY_BEGIN, 0, cut)
        end = self._pending.rfind(_PRIVATE_KEY_END, 0, cut)
        if begin > end:
            cut = begin
        if cut == 0:
            return b""
        ready, self._pending = self._pending[:cut], self._pending[cut:]
        return self._redact(ready)

    def finish(self) -> bytes:
        if self._finished:
            return b""
        self._finished = True
        self._pending += self._decoder.decode(b"", final=True)
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
