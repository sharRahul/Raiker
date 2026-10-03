# SPDX-License-Identifier: Apache-2.0
"""UX-DESIGN-03 — research the owner chose becomes a named, sourced reference.

DEC-07 step 5: reference inputs with a disclosure of what leaves the device,
research provenance preserved, and research output never silently fed into a
provider. The rules pinned here:

* a reference reaches the provider only as an audited ``references`` argument,
  after the owner's prompt and labelled as reference material;
* the row records each reference's name, passage and source pages — on a
  refusal as well as on a picture;
* anything malformed refuses the request rather than being dropped, and the
  composed prompt is held to the same bound as a prompt.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import pytest

from raiker.runtime.executors import tier2_image
from raiker.runtime.executors.tier2_image import compose_prompt, parse_references
from raiker.storage.sqlite import SQLiteStore
from tests.test_image_lineage import PNG, _generate, _ready, _ws

REFERENCE = {
    "name": "Lighthouse colour study",
    "text": "Keepers' houses were painted white with red lantern rooms.",
    "sources": ["https://example.org/lighthouses"],
}


def test_the_provider_gets_the_prompt_then_each_reference_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = _ws(tmp_path)
    _ready(ws, monkeypatch)
    sent: dict[str, Any] = {}

    def fake_json(url: str, payload: dict[str, Any], **kwargs: Any) -> dict:
        sent.update(payload)
        return {"data": [{"b64_json": base64.b64encode(PNG).decode()}]}

    monkeypatch.setattr(tier2_image, "post_json", fake_json)
    result = _generate(
        ws, profile_id="openai-hosted", prompt="A lighthouse at dusk", references=[REFERENCE]
    )
    assert result.decision == "allow"
    assert sent["prompt"].startswith("A lighthouse at dusk\n\nReference material")
    assert "- Lighthouse colour study: Keepers' houses" in sent["prompt"]

    row = SQLiteStore(ws).list_image_generations(owner_principal_id="principal_owner")[0]
    # The owner's own words stay the prompt; the provenance is its own field.
    assert row["prompt"] == "A lighthouse at dusk"
    assert json.loads(row["references_json"]) == [REFERENCE]


def test_no_references_sends_the_prompt_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = _ws(tmp_path)
    _ready(ws, monkeypatch)
    sent: dict[str, Any] = {}

    def fake_json(url: str, payload: dict[str, Any], **kwargs: Any) -> dict:
        sent.update(payload)
        return {"data": [{"b64_json": base64.b64encode(PNG).decode()}]}

    monkeypatch.setattr(tier2_image, "post_json", fake_json)
    _generate(ws, profile_id="openai-hosted", prompt="A lighthouse at dusk")
    assert sent["prompt"] == "A lighthouse at dusk"
    row = SQLiteStore(ws).list_image_generations(owner_principal_id="principal_owner")[0]
    assert row["references_json"] is None


@pytest.mark.parametrize(
    ("references", "reason"),
    [
        ([REFERENCE] * 4, "invalid_references:count"),
        ([{**REFERENCE, "name": ""}], "invalid_references:name"),
        ([{**REFERENCE, "text": "x" * 1001}], "invalid_references:text"),
        ([{**REFERENCE, "sources": ["file:///etc/passwd"]}], "invalid_references:sources"),
        ([{**REFERENCE, "sources": ["https://a.example/ b"]}], "invalid_references:sources"),
        (["just a string"], "invalid_references:shape"),
    ],
)
def test_a_malformed_reference_refuses_the_request_and_is_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, references: object, reason: str
) -> None:
    ws = _ws(tmp_path)
    _ready(ws, monkeypatch)

    def refuse(*args: Any, **kwargs: Any) -> dict:
        raise AssertionError("a malformed reference must not reach the provider")

    monkeypatch.setattr(tier2_image, "post_json", refuse)
    result = _generate(ws, profile_id="openai-hosted", prompt="a cat", references=references)
    assert result.error == reason
    row = SQLiteStore(ws).list_image_generations(owner_principal_id="principal_owner")[0]
    assert row["reason_code"] == reason


def test_a_refusal_after_validation_still_records_the_references(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = _ws(tmp_path)
    _ready(ws, monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY")
    result = _generate(ws, profile_id="openai-hosted", prompt="a cat", references=[REFERENCE])
    assert result.error == "image_provider_credential_missing"
    row = SQLiteStore(ws).list_image_generations(owner_principal_id="principal_owner")[0]
    assert json.loads(row["references_json"]) == [REFERENCE]


def test_the_composed_prompt_is_held_to_the_prompt_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = _ws(tmp_path)
    _ready(ws, monkeypatch)
    long_reference = {**REFERENCE, "text": "y" * 1000}
    result = _generate(
        ws,
        profile_id="openai-hosted",
        prompt="z" * 3500,
        references=[long_reference],
    )
    assert result.error == "prompt_too_long"


def test_the_pure_helpers() -> None:
    assert parse_references(None) == []
    assert parse_references([]) == []
    assert compose_prompt("p", []) == "p"
    parsed = parse_references([{"name": " n ", "text": " t ", "sources": []}])
    assert parsed == [{"name": "n", "text": "t", "sources": []}]
