"""BUG-234 — a tool result had one shape, and the revision defines six.

Raiker negotiates the current MCP revision and read exactly one thing out of a
``tools/call`` answer: the ``text`` field of every content block, concatenated.
The revision defines five block types — ``text``, ``image``, ``audio``,
``resource_link`` and an embedded ``resource`` — and a typed ``structuredContent``
field beside them. A server answering the way the specification tells it to was
therefore *silently degraded*: an image block contributed an empty string, a
resource link contributed an empty string, and a tool whose whole answer was
``structuredContent`` returned nothing at all to the model that called it.

That is the one failure mode the MCP surface is built to refuse. "Either
supported or named as unsupported, never silently degraded" is the rule, and a
result falling through it without a word was the last place it did not hold.

What has to hold now:

* **Every shape reaches the model as something.** Text as text; a reference as a
  named reference; a block Raiker has never heard of as its own type rather than
  as nothing.
* **A link is not a read.** A ``resource_link`` names an address the server would
  like read. Raiker renders the name and never fetches it — following it is a
  separate governed action, and a tool result must not be able to cause a read
  the owner's policy never saw.
* **Bytes are named, never carried.** An inline image is base64 on the wire.
  Naming its media type and size costs a line; decoding it into the turn's
  context costs the context and tells the model nothing it can use.
* **The record agrees with what happened.** The artifact's block count and length
  come from the same rendering the model read, not from a second reading of the
  same payload.
* **It is still bounded.** One block cannot spend the whole result, and one
  result cannot spend the whole turn.
* **Nothing is stored.** Artifacts, the audit event and the session log keep
  carrying counts and labels, exactly as before.
"""

from __future__ import annotations

import json
from typing import Any

from raiker.tools.mcp_schema import (
    MAX_BLOCK_CHARS,
    MAX_RESULT_CHARS,
    TRUNCATION_MARKER,
    render_call_result,
    render_content_block,
)


def _rendered(result: dict[str, Any]) -> str:
    text, _blocks, _length = render_call_result(result)
    return text


class TestEveryShapeReachesTheModelAsSomething:
    def test_text_is_carried_verbatim(self) -> None:
        assert _rendered({"content": [{"type": "text", "text": "the answer"}]}) == "the answer"

    def test_a_resource_link_is_named_and_never_fetched(self) -> None:
        rendered = _rendered(
            {
                "content": [
                    {
                        "type": "resource_link",
                        "uri": "https://example.invalid/secret",
                        "name": "report",
                        "mimeType": "text/markdown",
                        "description": "Last quarter",
                    }
                ]
            }
        )
        # Named — the model can see there was a link, and to what.
        assert "resource link" in rendered
        assert "report" in rendered
        assert "https://example.invalid/secret" in rendered
        assert "text/markdown" in rendered
        # And that is all that happened. The renderer takes no arguments that
        # could reach a network and returns a string; there is no fetch to make.

    def test_an_embedded_resource_carries_its_text_and_names_its_blob(self) -> None:
        with_text = _rendered(
            {
                "content": [
                    {
                        "type": "resource",
                        "resource": {
                            "uri": "file:///notes.md",
                            "mimeType": "text/markdown",
                            "text": "# Notes",
                        },
                    }
                ]
            }
        )
        assert "file:///notes.md" in with_text
        assert "# Notes" in with_text

        as_blob = _rendered(
            {
                "content": [
                    {
                        "type": "resource",
                        "resource": {
                            "uri": "file:///photo.png",
                            "mimeType": "image/png",
                            "blob": "QUJDRA==",
                        },
                    }
                ]
            }
        )
        assert "file:///photo.png" in as_blob
        assert "QUJDRA" not in as_blob

    def test_an_image_is_named_by_type_and_size_not_carried(self) -> None:
        # 400 base64 characters — 300 bytes decoded, and none of them in the turn.
        rendered = _rendered(
            {"content": [{"type": "image", "mimeType": "image/png", "data": "AAAA" * 100}]}
        )
        assert "image" in rendered
        assert "image/png" in rendered
        assert "bytes=300" in rendered
        assert "AAAA" not in rendered

    def test_an_unknown_block_type_is_named_rather_than_dropped(self) -> None:
        rendered = _rendered({"content": [{"type": "hologram", "frames": 12}]})
        # A block Raiker has never heard of is still something the server chose
        # to send; the model reading that it happened beats reading nothing.
        assert "hologram" in rendered

    def test_a_result_that_is_only_structured_content_is_not_empty(self) -> None:
        rendered = _rendered({"content": [], "structuredContent": {"temperature": 21}})
        assert "structured content" in rendered
        assert '"temperature":21' in rendered

    def test_structured_content_is_not_carried_twice(self) -> None:
        """A server that returns ``structuredContent`` is told by the
        specification to also serialise it into a text block. Carrying both
        would spend the turn's context twice on one answer."""
        payload = {"temperature": 21}
        rendered = _rendered(
            {
                "content": [{"type": "text", "text": json.dumps(payload, indent=2)}],
                "structuredContent": payload,
            }
        )
        assert rendered.count("temperature") == 1
        assert "structured content" not in rendered

    def test_structured_content_beside_unrelated_text_is_carried(self) -> None:
        rendered = _rendered(
            {
                "content": [{"type": "text", "text": "It is mild today."}],
                "structuredContent": {"temperature": 21},
            }
        )
        assert "It is mild today." in rendered
        assert '"temperature":21' in rendered


class TestTheRecordAgreesWithWhatHappened:
    def test_the_count_and_length_describe_what_the_model_read(self) -> None:
        result = {
            "content": [
                {"type": "text", "text": "hello"},
                {"type": "resource_link", "uri": "file:///x", "name": "x"},
            ]
        }
        text, blocks, length = render_call_result(result)
        assert blocks == 2
        assert length == len(text)
        # The defect this replaces: summing `text` fields recorded two blocks
        # and five characters for a result the model was handed more than that.
        assert length > len("hello")

    def test_a_non_result_renders_to_nothing_rather_than_raising(self) -> None:
        assert render_call_result(None) == ("", 0, 0)
        assert render_call_result({"content": "not a list"}) == ("", 0, 0)
        assert render_content_block("not a block") == ""


class TestItIsStillBounded:
    def test_one_block_cannot_spend_the_whole_result(self) -> None:
        rendered = _rendered(
            {
                "content": [
                    {"type": "text", "text": "x" * (MAX_BLOCK_CHARS * 2)},
                    {"type": "text", "text": "the block after it"},
                ]
            }
        )
        assert TRUNCATION_MARKER in rendered
        # Truncating the first block rather than the result is what leaves room
        # for the ones behind it.
        assert "the block after it" in rendered

    def test_one_result_cannot_spend_the_whole_turn(self) -> None:
        rendered = _rendered(
            {
                "content": [
                    {"type": "text", "text": "y" * (MAX_BLOCK_CHARS - 1)}
                    for _ in range(10)
                ]
            }
        )
        assert len(rendered) <= MAX_RESULT_CHARS + len(TRUNCATION_MARKER)
        assert rendered.endswith(TRUNCATION_MARKER)
