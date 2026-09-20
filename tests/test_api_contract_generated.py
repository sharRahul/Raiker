"""The contract gate that is derived rather than transcribed (GCR-42).

``web/src/lib/apiTypes.ts`` is a hand-maintained mirror of the backend DTOs and
says so in its own header. The guard standing behind it —
``test_api_contract_schemas.py`` — was a second hand-maintained copy: field
names transcribed out of the TypeScript into Python literals. Three hands had
to agree about every shape, and a backend change that dropped a field the UI
reads would only fail the build if someone had remembered to transcribe that
field in the first place.

This derives the same comparison from the two artefacts themselves. It does not
replace the older guard, which asserts against *live responses* and so covers
the routes as well as the types; it covers what that one cannot, which is every
shape nobody thought to transcribe.
"""

from __future__ import annotations

from scripts.check_api_contract import (
    API_TYPES,
    backend_dataclasses,
    drifts,
    pairs,
    parse_interfaces,
    serialised_keys,
)


def test_no_required_frontend_field_is_missing_from_its_backend_dto() -> None:
    found = drifts()
    assert not found, "\n".join(str(drift) for drift in found)


def test_the_gate_actually_pairs_a_meaningful_share_of_the_mirror() -> None:
    """A checker that pairs nothing passes everything.

    The floor is deliberately well under the count the check pairs today: the
    number moves whenever an interface or a DTO is added, and a test that has to
    be edited for every such change gets edited without being read.
    """
    interfaces = parse_interfaces(API_TYPES.read_text(encoding="utf-8"))
    matched = pairs(interfaces, backend_dataclasses())
    assert len(matched) >= 30, f"only {len(matched)} of {len(interfaces)} paired"


def test_a_key_a_view_computes_counts_as_a_field_it_sends() -> None:
    """`to_dict` may add a key the dataclass does not store, and often does.

    Comparing against `dataclasses.fields` alone reported `BrainView`'s constant
    motion notice as a field the browser read and the backend did not send.
    """
    from raiker.control.dashboard import BrainView

    keys = serialised_keys(BrainView)
    assert "illustrative_motion_notice" in keys
    assert {"generated_at", "nodes", "edges"} <= keys


def test_an_optional_frontend_field_is_not_required_of_the_backend() -> None:
    """`field?: T` means the UI copes without it; only required fields are read."""
    interfaces = parse_interfaces(
        "export interface Example {\n"
        "  required: string;\n"
        "  optional?: string;\n"
        "}\n"
    )
    assert interfaces["Example"] == {"required": False, "optional": True}
