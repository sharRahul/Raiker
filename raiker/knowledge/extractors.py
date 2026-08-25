"""Bounded, local-only text extraction from stored managed knowledge files.

Every managed file is accepted for storage; only some are *readable*. This
module answers exactly one question — "can Raiker safely turn these bytes into
text on this machine?" — and answers it honestly. There is no remote extraction
path, no format sniffing that executes anything, and no claim of content search
for a format that could not be parsed.

The extractors themselves are the ones the attachment path already uses
(``raiker.runtime.attachments``): a decode for text, pypdf for PDF, stdlib
zip+XML for the OOXML formats. A file that fails validation, is encrypted, is
malformed, or has no local reader becomes **metadata-only**: its bytes stay
exactly as imported and only its catalogue metadata is searchable. Extracted
text is untrusted data, never instructions.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from raiker.runtime.attachments import (
    DOCUMENT_MEDIA_TYPES,
    DOCX_MEDIA_TYPE,
    MAX_DOCUMENT_TEXT_CHARS,
    PDF_MEDIA_TYPE,
    TEXT_DOCUMENT_MEDIA_TYPES,
    XLSX_MEDIA_TYPE,
    AttachmentValidationError,
    extract_document_text,
    validate_document,
)

#: Largest file, in bytes, this module will read into memory to extract. Larger
#: managed files stay stored and become metadata-only rather than becoming a
#: reason to hold 100 MB of someone else's spreadsheet in the process.
MAX_EXTRACTION_BYTES = 32_000_000

#: Filename suffixes mapped to the media type whose local reader handles them.
#: Consulted only when the declared media type has no reader — a browser that
#: sends ``application/octet-stream`` for a ``.md`` file should still get an
#: index, and a file named ``.pdf`` that is not one still fails validation.
_SUFFIX_MEDIA_TYPES: dict[str, str] = {
    ".txt": "text/plain",
    ".text": "text/plain",
    ".log": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".csv": "text/csv",
    ".pdf": PDF_MEDIA_TYPE,
    ".docx": DOCX_MEDIA_TYPE,
    ".xlsx": XLSX_MEDIA_TYPE,
}

#: Formats Raiker stores but deliberately does not parse. Named rather than left
#: to the default so the reason reported to the owner says "no safe local
#: reader" instead of the generic fallback.
_KNOWN_UNSUPPORTED_SUFFIXES: frozenset[str] = frozenset({".doc", ".xls", ".ppt", ".pps"})


@dataclass(frozen=True)
class ExtractionResult:
    """What could be read out of one managed file, and why not more."""

    #: The bounded extracted text. Empty whenever ``extracted`` is false.
    text: str
    #: Whether a safe local reader produced content for this file.
    extracted: bool
    #: Stable machine-readable reason when nothing was extracted.
    reason: str | None = None
    #: Whether the reader hit ``MAX_DOCUMENT_TEXT_CHARS`` and stopped early.
    truncated: bool = False
    #: The media type the reader actually dispatched on, which may have been
    #: resolved from the filename when the declared type had no reader.
    resolved_media_type: str | None = None


def resolve_extractable_media_type(relative_path: str, media_type: str) -> str | None:
    """The media type whose local reader applies, or ``None`` if there is none.

    The declared type wins when it has a reader. Otherwise the filename suffix
    decides, which is what makes a ``.md`` uploaded as ``application/octet-stream``
    readable without letting a suffix override a type Raiker can already parse.
    """
    declared = (media_type or "").split(";")[0].strip().lower()
    if declared in DOCUMENT_MEDIA_TYPES:
        return declared
    suffix = Path(relative_path).suffix.lower()
    if suffix in _KNOWN_UNSUPPORTED_SUFFIXES:
        return None
    return _SUFFIX_MEDIA_TYPES.get(suffix)


def extract_managed_file(
    path: str | Path,
    media_type: str,
    *,
    relative_path: str | None = None,
    max_chars: int = MAX_DOCUMENT_TEXT_CHARS,
) -> ExtractionResult:
    """Read *path* into bounded text, or explain why it stays metadata-only.

    Never raises for an unreadable file: an unparseable upload is a normal,
    expected outcome that must not cost the owner their stored original.
    """
    file_path = Path(path)
    name = relative_path or file_path.name
    resolved = resolve_extractable_media_type(name, media_type)
    if resolved is None:
        return ExtractionResult("", False, reason="no_local_extractor")
    try:
        size = file_path.stat().st_size
    except OSError:
        return ExtractionResult("", False, reason="file_unreadable")
    if size == 0:
        return ExtractionResult("", False, reason="file_empty")
    if size > MAX_EXTRACTION_BYTES:
        return ExtractionResult("", False, reason="file_too_large_to_extract")
    try:
        data = file_path.read_bytes()
    except OSError:
        return ExtractionResult("", False, reason="file_unreadable")
    try:
        validate_document(resolved, data)
        text = extract_document_text(resolved, data)
    except AttachmentValidationError as exc:
        return ExtractionResult("", False, reason=str(exc), resolved_media_type=resolved)
    except Exception:  # noqa: BLE001 - a malformed upload is data, not a crash
        return ExtractionResult("", False, reason="extraction_failed", resolved_media_type=resolved)
    if not text.strip():
        return ExtractionResult("", False, reason="no_extractable_text", resolved_media_type=resolved)
    bounded = text[: max(0, max_chars)]
    return ExtractionResult(
        bounded,
        True,
        truncated=len(bounded) < len(text),
        resolved_media_type=resolved,
    )


def _supported_media_types() -> frozenset[str]:
    """Every media type with a local reader, for surfaces that explain support."""
    return frozenset(TEXT_DOCUMENT_MEDIA_TYPES | {PDF_MEDIA_TYPE, DOCX_MEDIA_TYPE, XLSX_MEDIA_TYPE})


SUPPORTED_MEDIA_TYPES: frozenset[str] = _supported_media_types()
