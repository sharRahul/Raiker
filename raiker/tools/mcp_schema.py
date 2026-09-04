"""What a connected MCP server said its tools take — bounded before it is believed.

Discovery kept tool *names* and threw the rest of `tools/list` away, so every
projected `mcp__server__tool` was offered to the model as one untyped
``arguments`` object with a sentence Raiker wrote itself. The model had to guess
field names, and a server's own description of what its tool does never reached
the turn at all. Both reference coding agents pass the declared `inputSchema`
straight through; Raiker passed nothing.

Passing it through *raw* is the other mistake. A tool declaration is text an
outside program wrote: it lands in the model's tool catalogue, which is the one
place in a turn that is normally trusted, and it can be arbitrarily large,
arbitrarily deep, and can carry a `$ref` pointing anywhere. So a declaration is
**bounded and attributed** here before anything downstream sees it:

* **Attributed.** The server's own sentence is kept, and kept marked as the
  server's — Raiker's framing comes first, the declared text after it, so a
  description that reads like an instruction reads as *the server's* instruction.
* **Bounded.** Depth, property count, string length and total encoded size are
  all capped. A declaration that will not fit is dropped whole rather than
  truncated into a schema that lies about what the tool takes.
* **Closed.** Only JSON-Schema keywords a provider will act on survive; a
  ``$ref`` may point inside the same document and nowhere else.

A dropped or absent schema is not a failure: the tool is still projected with the
open ``arguments`` object it always had, and the server card says the server
declared none. Never silently degraded — the rule the MCP surface is built on.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

#: The longest declared description Raiker will carry into a tool catalogue.
#: Long enough for the paragraph a real server writes, short enough that a
#: hostile one cannot spend the turn's context on prose.
MAX_TEXT_CHARS = 400

#: The most nesting a declared schema may have. Six is deeper than any real
#: tool's arguments and shallow enough that recursion is bounded by construction.
MAX_DEPTH = 6

#: The most properties one object in a declared schema may have.
MAX_PROPERTIES = 48

#: The most items an ``enum``/``required``/``anyOf`` list may carry.
MAX_LIST_ITEMS = 64

#: The most one tool's encoded schema may cost. Beyond this the schema is
#: dropped and the tool falls back to the open object.
MAX_SCHEMA_BYTES = 8_000

#: JSON-Schema keywords that survive sanitisation. Everything else — including
#: ``$schema``, ``$id``, vendor extensions and unknown keys — is dropped, because
#: a keyword no provider acts on is weight in every request that carries it.
_ALLOWED_KEYWORDS = frozenset({
    "type", "properties", "required", "items", "enum", "const", "default",
    "description", "title", "format", "pattern", "minimum", "maximum",
    "exclusiveMinimum", "exclusiveMaximum", "minLength", "maxLength",
    "minItems", "maxItems", "uniqueItems", "additionalProperties",
    "anyOf", "oneOf", "allOf", "$ref", "$defs", "definitions", "nullable",
})

#: Keywords whose value is a list of subschemas.
_SUBSCHEMA_LISTS = frozenset({"anyOf", "oneOf", "allOf"})

#: Keywords whose value is a map of name → subschema.
_SUBSCHEMA_MAPS = frozenset({"properties", "$defs", "definitions"})

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WHITESPACE = re.compile(r"\s+")


def clean_text(value: Any, *, limit: int = MAX_TEXT_CHARS) -> str:
    """One line of declared prose: no control characters, no runaway length."""
    if not isinstance(value, str):
        return ""
    collapsed = _WHITESPACE.sub(" ", _CONTROL.sub(" ", value)).strip()
    return collapsed[:limit]


@dataclass(frozen=True)
class McpToolDeclaration:
    """One tool as its server declared it, after bounding.

    ``input_schema`` is ``None`` when the server declared none, when what it
    declared was not an object schema, or when the declaration exceeded the
    bounds above. All three read the same downstream — the tool takes an open
    object — and the reason is carried in :attr:`schema_reason` so the server
    card can say which it was.
    """

    name: str
    title: str = ""
    description: str = ""
    input_schema: dict[str, Any] | None = None
    schema_reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"name": self.name}
        if self.title:
            payload["title"] = self.title
        if self.description:
            payload["description"] = self.description
        if self.input_schema is not None:
            payload["input_schema"] = self.input_schema
        if self.schema_reason:
            payload["schema_reason"] = self.schema_reason
        return payload


def _sanitize_schema(value: Any, depth: int) -> Any:
    """Copy a declared subschema, keeping only what a provider will act on."""
    if depth > MAX_DEPTH:
        return None
    if isinstance(value, bool):
        # `additionalProperties: false` is a real and useful declaration.
        return value
    if not isinstance(value, dict):
        return None
    out: dict[str, Any] = {}
    for key, raw in value.items():
        if key not in _ALLOWED_KEYWORDS:
            continue
        if key in ("description", "title"):
            text = clean_text(raw)
            if text:
                out[key] = text
        elif key == "$ref":
            # A pointer inside this document is a declaration; one pointing at a
            # URL is a fetch instruction, and no schema Raiker carries gets to
            # ask a provider to go anywhere.
            if isinstance(raw, str) and raw.startswith("#/") and len(raw) <= 200:
                out[key] = raw
        elif key in _SUBSCHEMA_MAPS:
            if not isinstance(raw, dict):
                continue
            nested: dict[str, Any] = {}
            for prop, sub in list(raw.items())[:MAX_PROPERTIES]:
                if not isinstance(prop, str) or not prop:
                    continue
                cleaned = _sanitize_schema(sub, depth + 1)
                if cleaned is not None:
                    nested[clean_text(prop, limit=128)] = cleaned
            if nested:
                out[key] = nested
        elif key in _SUBSCHEMA_LISTS:
            if not isinstance(raw, list):
                continue
            branches = [
                cleaned
                for cleaned in (_sanitize_schema(sub, depth + 1) for sub in raw[:MAX_LIST_ITEMS])
                if cleaned is not None
            ]
            if branches:
                out[key] = branches
        elif key == "items":
            cleaned = _sanitize_schema(raw, depth + 1)
            if cleaned is not None:
                out[key] = cleaned
        elif key == "additionalProperties":
            if isinstance(raw, bool):
                out[key] = raw
            else:
                cleaned = _sanitize_schema(raw, depth + 1)
                if cleaned is not None:
                    out[key] = cleaned
        elif key in ("required", "enum"):
            if isinstance(raw, list):
                out[key] = [
                    item if not isinstance(item, str) else clean_text(item, limit=128)
                    for item in raw[:MAX_LIST_ITEMS]
                ]
        elif key == "type":
            if isinstance(raw, str):
                out[key] = clean_text(raw, limit=32)
            elif isinstance(raw, list):
                out[key] = [clean_text(item, limit=32) for item in raw[:8] if isinstance(item, str)]
        else:
            # Scalars: a number, a string, a bool. Anything structural would
            # have matched a branch above.
            if isinstance(raw, (int, float, bool)):
                out[key] = raw
            elif isinstance(raw, str):
                out[key] = clean_text(raw, limit=256)
    return out


def sanitize_declaration(raw: Any) -> McpToolDeclaration | None:
    """One entry of a `tools/list` result, bounded. ``None`` if it has no name."""
    if not isinstance(raw, dict):
        return None
    name = clean_text(raw.get("name"), limit=128)
    if not name:
        return None
    declared = raw.get("inputSchema")
    if declared is None:
        declared = raw.get("input_schema")
    schema: dict[str, Any] | None = None
    reason = ""
    if declared is None:
        reason = "not_declared"
    elif not isinstance(declared, dict):
        reason = "not_an_object_schema"
    else:
        cleaned = _sanitize_schema(declared, 1)
        if not isinstance(cleaned, dict) or not cleaned:
            reason = "not_an_object_schema"
        elif len(json.dumps(cleaned).encode("utf-8")) > MAX_SCHEMA_BYTES:
            # Dropped whole rather than truncated: half a schema would describe
            # arguments the tool does not take.
            reason = "too_large"
        else:
            cleaned.setdefault("type", "object")
            schema = cleaned
    return McpToolDeclaration(
        name=name,
        title=clean_text(raw.get("title"), limit=120),
        description=clean_text(raw.get("description")),
        input_schema=schema,
        schema_reason=reason,
    )


def declarations_from_payload(tools: Any) -> list[McpToolDeclaration]:
    """Every declaration in a `tools/list` result, in the order the server gave."""
    if not isinstance(tools, list):
        return []
    out: list[McpToolDeclaration] = []
    for entry in tools:
        declaration = sanitize_declaration(entry)
        if declaration is not None:
            out.append(declaration)
    return out


def encode_declarations(declarations: list[McpToolDeclaration]) -> str:
    """The stored form: compact JSON, one object per declaration."""
    return json.dumps([declaration.as_dict() for declaration in declarations])


def decode_declarations(stored: Any) -> list[McpToolDeclaration]:
    """Read stored declarations back, re-bounding them.

    Re-sanitised on the way out as well as in, because a row written by an older
    build predates these bounds and a stored value is still not Raiker's own text.
    """
    if isinstance(stored, str):
        try:
            stored = json.loads(stored)
        except ValueError:
            return []
    if not isinstance(stored, list):
        return []
    out: list[McpToolDeclaration] = []
    for entry in stored:
        if not isinstance(entry, dict):
            continue
        declaration = sanitize_declaration(
            {
                "name": entry.get("name"),
                "title": entry.get("title"),
                "description": entry.get("description"),
                "inputSchema": entry.get("input_schema"),
            }
        )
        if declaration is None:
            continue
        # A stored row already carries why it has no schema; keep that rather
        # than re-deriving `not_declared` for one that was dropped as too large.
        reason = str(entry.get("schema_reason") or declaration.schema_reason)
        out.append(
            McpToolDeclaration(
                name=declaration.name,
                title=declaration.title,
                description=declaration.description,
                input_schema=declaration.input_schema,
                schema_reason="" if declaration.input_schema is not None else reason,
            )
        )
    return out


# ── What a server offers that Raiker does not use (BUG-234) ──────────────────
#
# Raiker speaks the current MCP revision and uses one part of it: tools. The
# rule the MCP surface is built on says the rest must be *named*, not silently
# dropped — so a server's own `initialize` capabilities, plus what the transport
# was observed doing, are recorded as feature keys and turned into sentences
# here. A key with no sentence is still shown, by its own name, rather than
# being hidden for not being on a list.

#: The one server capability Raiker uses today.
SUPPORTED_SERVER_FEATURES = frozenset({"tools"})

#: Observations the transport records about itself, rather than capabilities the
#: server declared. Prefixed so they cannot collide with a capability key.
TRANSPORT_EVENT_STREAM = "transport:event_stream"
TRANSPORT_SESSION_RESTARTED = "transport:session_restarted"

_FEATURE_NOTES: dict[str, str] = {
    "resources": (
        "Offers resources — including any ui:// app interface. Raiker reads this "
        "server's tools only."
    ),
    "prompts": "Offers prompt templates. Raiker does not load them.",
    "logging": "Offers a log stream. Raiker does not subscribe to it.",
    "completions": "Offers argument completions. Raiker does not request them.",
    "experimental": "Declares experimental capabilities. Raiker uses none of them.",
    TRANSPORT_EVENT_STREAM: (
        "Answers over an event stream. Raiker reads each response whole rather "
        "than streaming it, and holds no open connection between turns."
    ),
    TRANSPORT_SESSION_RESTARTED: (
        "Dropped the session mid-read; Raiker started a new one and continued."
    ),
}


def server_feature_keys(
    capabilities: Any, *, event_stream: bool = False, session_restarted: bool = False
) -> list[str]:
    """The feature keys to store for one connection: what it declared, plus what
    the transport saw. Names only — never a capability's contents."""
    keys: list[str] = []
    if isinstance(capabilities, dict):
        keys.extend(
            clean_text(key, limit=64)
            for key in sorted(capabilities)
            if isinstance(key, str) and clean_text(key, limit=64)
        )
    if event_stream:
        keys.append(TRANSPORT_EVENT_STREAM)
    if session_restarted:
        keys.append(TRANSPORT_SESSION_RESTARTED)
    return keys


def unsupported_feature_notes(features: Any) -> list[dict[str, str]]:
    """One owner-facing sentence per thing this server offers that Raiker does
    not use. Empty when a server offers only what Raiker uses."""
    if isinstance(features, str):
        try:
            features = json.loads(features)
        except ValueError:
            return []
    if not isinstance(features, list):
        return []
    notes: list[dict[str, str]] = []
    for raw in features:
        key = clean_text(raw, limit=64)
        if not key or key in SUPPORTED_SERVER_FEATURES:
            continue
        notes.append({"feature": key, "note": _FEATURE_NOTES.get(key, "Raiker does not use it.")})
    return notes


# ── What a tool result carries (BUG-234) ─────────────────────────────────────
#
# Raiker read one shape out of a `tools/call` result: the `text` of every block,
# concatenated. The current revision defines five block types and a typed
# `structuredContent` field beside them, so a server answering the way the
# specification tells it to was silently degraded — an image block contributed an
# empty string, a `resource_link` contributed an empty string, and a tool whose
# whole answer was `structuredContent` returned nothing at all to the model that
# called it. "Either supported or named as unsupported, never silently degraded"
# is the rule the MCP surface is built on, and this was the last place a result
# could fall through it without a word.
#
# What is rendered is what the *calling model* reads. It is still never stored:
# the artifacts, the audit event and the session log keep carrying counts and
# labels, exactly as before.
#
# **A link is not a read.** A `resource_link` names an address the server would
# like read; Raiker renders the name and never fetches it. Following it is a
# separate governed action — `web_fetch`, or a `resources/read` Raiker does not
# perform — and a tool result must not be able to cause a read the owner's
# policy never saw. That is the whole difference between carrying a link and
# obeying one.
#
# **Bytes are named, never carried.** An `image` or `audio` block is base64 in
# the wire format. Decoding it into a turn's context would spend the context on
# something the model cannot see anyway, so the block is named by its media type
# and its size.

#: The most one rendered block may contribute. A server's own text is already
#: bounded by the transport's byte ceiling; this bounds one block's share of it
#: so a single enormous block cannot crowd out the ones after it.
MAX_BLOCK_CHARS = 20_000

#: The most one tool result may contribute in total.
MAX_RESULT_CHARS = 60_000

#: Appended when either ceiling above cut something, so a truncated answer says
#: it was truncated rather than reading as a complete one.
TRUNCATION_MARKER = "\n[truncated by Raiker]"


def _named_block(kind: str, **fields: Any) -> str:
    """One line for a block whose contents are a reference rather than text."""
    stated = " ".join(
        f"{name}={value}" for name, value in fields.items() if value not in ("", None)
    )
    return f"[{kind}{' ' + stated if stated else ''}]"


def _blob_bytes(value: Any) -> int:
    """The decoded size of a base64 field, without decoding it.

    Base64 is four characters per three bytes, less the padding. Computing it
    rather than decoding means an inline megabyte is never materialised just to
    say how big it was.
    """
    if not isinstance(value, str) or not value:
        return 0
    padding = len(value) - len(value.rstrip("="))
    return max(0, (len(value) // 4) * 3 - padding)


def render_content_block(block: Any) -> str:
    """One content block, as the calling model should read it.

    An unrecognised type is named by its own type rather than dropped: a block
    Raiker has never heard of is still something the server chose to send, and
    the model reading "there was a block of this kind here" is strictly better
    informed than the model reading nothing.
    """
    if not isinstance(block, dict):
        return ""
    kind = clean_text(block.get("type"), limit=64) or "unknown"
    if kind == "text":
        text = block.get("text")
        return text if isinstance(text, str) else ""
    if kind == "resource_link":
        return _named_block(
            "resource link",
            # `clean_text` rather than a URL parse: this is a name being shown,
            # not an address being reached, and nothing downstream will open it.
            name=clean_text(block.get("name") or block.get("title"), limit=200),
            uri=clean_text(block.get("uri"), limit=500),
            type=clean_text(block.get("mimeType"), limit=100),
            description=clean_text(block.get("description")),
        )
    if kind == "resource":
        resource = block.get("resource")
        resource = resource if isinstance(resource, dict) else {}
        embedded = resource.get("text")
        header = _named_block(
            "embedded resource",
            uri=clean_text(resource.get("uri"), limit=500),
            type=clean_text(resource.get("mimeType"), limit=100),
            bytes=_blob_bytes(resource.get("blob")) or None,
        )
        # A server may embed the resource's text directly, which is the one case
        # where a non-text block genuinely carries something to read.
        if isinstance(embedded, str) and embedded:
            return f"{header}\n{embedded}"
        return header
    if kind in ("image", "audio"):
        return _named_block(
            kind,
            type=clean_text(block.get("mimeType"), limit=100),
            bytes=_blob_bytes(block.get("data")) or None,
        )
    return _named_block(kind)


def render_call_result(result: Any) -> tuple[str, int, int]:
    """A `tools/call` result as ``(text for the model, block count, length)``.

    The three travel together because they have to agree: the artifact says how
    many blocks and how many characters a result carried, and a count derived
    from a different reading of the same payload than the text the model saw is
    a record of something that did not happen.
    """
    if not isinstance(result, dict):
        return "", 0, 0
    raw = result.get("content")
    blocks = raw if isinstance(raw, list) else []
    rendered: list[str] = []
    for block in blocks:
        piece = render_content_block(block)
        if not piece:
            continue
        if len(piece) > MAX_BLOCK_CHARS:
            piece = piece[:MAX_BLOCK_CHARS] + TRUNCATION_MARKER
        rendered.append(piece)

    # `structuredContent` is the current revision's typed answer. The
    # specification tells a server that returns one to *also* serialise it into a
    # text block for compatibility, and most do — so carrying both would spend
    # the turn's context twice on one answer. It is appended only when the text
    # blocks did not already carry it, compared on the canonical encoding rather
    # than on the server's spacing.
    structured = result.get("structuredContent")
    if structured is not None:
        try:
            encoded = json.dumps(structured, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError):
            encoded = ""
        if encoded and not _already_carried(encoded, rendered):
            piece = f"[structured content]\n{encoded}"
            if len(piece) > MAX_BLOCK_CHARS:
                piece = piece[:MAX_BLOCK_CHARS] + TRUNCATION_MARKER
            rendered.append(piece)

    text = "\n".join(rendered)
    if len(text) > MAX_RESULT_CHARS:
        text = text[:MAX_RESULT_CHARS] + TRUNCATION_MARKER
    return text, len(blocks), len(text)


def _already_carried(encoded: str, rendered: list[str]) -> bool:
    """True when a text block already holds the structured answer.

    Compared on the canonical encoding of both sides: a server that pretty-prints
    its compatibility copy has still sent the same object, and re-appending it
    would be the same data twice in the model's context.
    """
    for piece in rendered:
        if encoded in piece:
            return True
        try:
            if json.dumps(json.loads(piece), sort_keys=True, separators=(",", ":")) == encoded:
                return True
        except ValueError:
            continue
    return False
