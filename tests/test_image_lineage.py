"""Editing an image, asking for variations of one, and knowing what came from what.

BUG-277. The governed image endpoint took a prompt, a size and a model and
returned one picture. There was no subject for "edit this" to be about, no
relationship between a variation and its original, and no versions for a version
picker to show — so the Design canvas's canvas had nothing to compose, and the composer
redesign's edit/variation controls had nothing to reach.

Three things are held here, and the first is the one that matters most:

* **A subject is an action argument, and an action argument is a thing a model
  can propose.** The subject is resolved owner-scoped, and an id belonging to
  somebody else answers exactly as an id that was never issued.
* An edit reaches the provider's *edit* path — multipart for OpenAI, an inline
  part for Gemini — through the same egress allowlist a generation answers to.
* Lineage is recorded on refusals as well as successes, because an edit that was
  denied is still a thing the owner asked of a particular image.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id, utc_now
from raiker.control.service import RuntimeControlService
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority import GovernedAction, GovernedActionResult, RuntimeAuthority
from raiker.runtime.authority.models import Principal, RiskLevelValue
from raiker.runtime.executors import build_default_executor_registry, tier2_image
from raiker.storage.sqlite import SQLiteStore

CAP = "image_generation"

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
OTHER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "lineage"
    ws.mkdir()
    return ws


def _enable(ws: Path) -> None:
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "test")
    store = SQLiteStore(ws)
    with store.connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref) "
            "VALUES (?, ?, ?, ?)",
            (CAP, "principal_owner", utc_now(), "docs/threat-models/models.md"),
        )
    assert svc.set_capability_state(
        CAP, "enabled_runtime", None, "test", confirmation_token="confirm"
    ).ok


def _generate(ws: Path, **args: object) -> GovernedActionResult:
    store = SQLiteStore(ws)
    authority = RuntimeAuthority(
        store, EventLogWriter(store), executor_registry=build_default_executor_registry(ws, store)
    )
    raw = store.get_principal("principal_owner")
    assert raw is not None
    principal = Principal(**raw)
    return authority.route_action(
        GovernedAction(
            action_id=new_id("act_"),
            principal_id=principal.principal_id,
            action_type=CAP,
            tool_or_service_name=CAP,
            arguments=dict(args),
            risk_level=RiskLevelValue.MEDIUM,
        ),
        principal,
    )


def _ready(ws: Path, monkeypatch: pytest.MonkeyPatch, host: str = "api.openai.com") -> None:
    _enable(ws)
    monkeypatch.setenv("RAIKER_MODEL_EGRESS_ALLOWLIST", host)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("GEMINI_API_KEY", "g-test")


def _seed_original(ws: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """One successful ordinary generation, to be the subject of what follows."""
    monkeypatch.setattr(
        tier2_image,
        "post_json",
        lambda *a, **k: {"data": [{"b64_json": base64.b64encode(PNG).decode()}]},
    )
    assert _generate(ws, profile_id="openai-hosted", prompt="a cat").decision == "allow"
    rows = SQLiteStore(ws).list_image_generations(owner_principal_id="principal_owner")
    return str(rows[0]["generation_id"])


# ── The subject is authority, not a parameter ────────────────────────────────


def test_a_generation_belonging_to_another_owner_cannot_be_edited(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole reason the subject is resolved in the executor.

    A generation id is short and guessable in shape. If it were taken on trust,
    naming somebody else's id would send their picture to a provider on this
    owner's credential.
    """
    ws = _ws(tmp_path)
    _ready(ws, monkeypatch)
    store = SQLiteStore(ws)
    store.save_attachment(
        attachment_id="att_theirs",
        kind="generated_image",
        filename="theirs.png",
        media_type="image/png",
        sha256="x",
        data=OTHER_PNG,
        owner_principal_id="principal_someone_else",
    )
    store.record_image_generation(
        generation_id="img_theirs",
        owner_principal_id="principal_someone_else",
        profile_id="openai-hosted",
        provider="openai",
        model="gpt-image-1",
        prompt="not yours",
        size="1024x1024",
        status="ok",
        attachment_id="att_theirs",
    )

    def refuse(*args: Any, **kwargs: Any) -> dict:
        raise AssertionError("the provider must not be reached for another owner's image")

    monkeypatch.setattr(tier2_image, "post_multipart", refuse)
    monkeypatch.setattr(tier2_image, "post_json", refuse)

    result = _generate(
        ws, profile_id="openai-hosted", prompt="change it", source_generation_id="img_theirs"
    )

    assert result.error == "image_source_not_found"
    mine = store.list_image_generations(owner_principal_id="principal_owner")
    assert [row["reason_code"] for row in mine] == ["image_source_not_found"]


def test_an_id_that_was_never_issued_answers_the_same_way(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Telling the two apart would be telling a caller that a generation exists."""
    ws = _ws(tmp_path)
    _ready(ws, monkeypatch)

    result = _generate(
        ws, profile_id="openai-hosted", prompt="change it", source_generation_id="img_nonexistent"
    )

    assert result.error == "image_source_not_found"
    rows = SQLiteStore(ws).list_image_generations(owner_principal_id="principal_owner")
    assert rows[0]["reason_code"] == "image_source_not_found"


def test_a_refused_generation_is_not_a_subject(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It has no picture, so there is nothing to edit."""
    ws = _ws(tmp_path)
    _ready(ws, monkeypatch)
    store = SQLiteStore(ws)
    store.record_image_generation(
        generation_id="img_refused",
        owner_principal_id="principal_owner",
        profile_id="openai-hosted",
        provider="openai",
        model="gpt-image-1",
        prompt="denied",
        size="1024x1024",
        status="refused",
        reason_code="image_refused_by_provider",
    )

    result = _generate(
        ws, profile_id="openai-hosted", prompt="fix it", source_generation_id="img_refused"
    )

    assert result.error == "image_source_has_no_image"
    # Addressed by its subject rather than by position: the seeded row and this
    # refusal share a timestamp, so "the first row" is not "the new one".
    rows = store.list_image_generations(owner_principal_id="principal_owner")
    refusal = next(row for row in rows if row["source_generation_id"] == "img_refused")
    assert refusal["reason_code"] == "image_source_has_no_image"


# ── An edit reaches the provider's edit path ─────────────────────────────────


def test_an_openai_edit_posts_the_subject_to_the_edits_endpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = _ws(tmp_path)
    _ready(ws, monkeypatch)
    original = _seed_original(ws, monkeypatch)
    seen: dict[str, Any] = {}

    def fake_multipart(
        url: str,
        fields: dict[str, str],
        files: dict[str, tuple[str, str, bytes]],
        *,
        egress_allowlist: frozenset[str] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 60.0,
    ) -> dict:
        seen.update(url=url, fields=fields, files=files, allowlist=egress_allowlist)
        return {"data": [{"b64_json": base64.b64encode(OTHER_PNG).decode()}]}

    monkeypatch.setattr(tier2_image, "post_multipart", fake_multipart)
    result = _generate(
        ws,
        profile_id="openai-hosted",
        prompt="make it blue",
        source_generation_id=original,
    )

    assert result.decision == "allow", result.error
    # The edit endpoint, not the generation one, and the subject's own bytes.
    assert seen["url"] == "https://api.openai.com/v1/images/edits"
    assert seen["files"]["image"][2] == PNG
    # The same allowlist a plain generation answers to — multipart widens no
    # boundary, it only changes how the body is encoded.
    assert seen["allowlist"] == frozenset({"api.openai.com"})


def test_a_gemini_edit_sends_the_subject_inline_on_the_json_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = _ws(tmp_path)
    _ready(ws, monkeypatch, host="generativelanguage.googleapis.com,api.openai.com")
    original = _seed_original(ws, monkeypatch)
    seen: dict[str, Any] = {}

    def fake_json(url: str, payload: dict[str, Any], **kwargs: Any) -> dict:
        seen.update(url=url, payload=payload)
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "inlineData": {
                                    "mimeType": "image/png",
                                    "data": base64.b64encode(OTHER_PNG).decode(),
                                }
                            }
                        ]
                    }
                }
            ]
        }

    monkeypatch.setattr(tier2_image, "post_json", fake_json)
    result = _generate(
        ws,
        profile_id="gemini-hosted-openai-compatible",
        prompt="make it blue",
        source_generation_id=original,
    )

    assert result.decision == "allow", result.error
    parts = seen["payload"]["contents"][0]["parts"]
    inline = [part for part in parts if "inline_data" in part]
    assert len(inline) == 1
    assert base64.b64decode(inline[0]["inline_data"]["data"]) == PNG


# ── Lineage ──────────────────────────────────────────────────────────────────


def test_an_edit_records_what_it_came_from(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = _ws(tmp_path)
    _ready(ws, monkeypatch)
    original = _seed_original(ws, monkeypatch)
    monkeypatch.setattr(
        tier2_image,
        "post_multipart",
        lambda *a, **k: {"data": [{"b64_json": base64.b64encode(OTHER_PNG).decode()}]},
    )

    assert (
        _generate(
            ws, profile_id="openai-hosted", prompt="bluer", source_generation_id=original
        ).decision
        == "allow"
    )

    rows = SQLiteStore(ws).list_image_generations(owner_principal_id="principal_owner")
    edit = next(row for row in rows if row["generation_id"] != original)
    assert edit["source_generation_id"] == original
    assert edit["kind"] == "edit"
    # The original is an origin, not a broken row.
    origin = next(row for row in rows if row["generation_id"] == original)
    assert origin["source_generation_id"] is None
    assert origin["kind"] == "create"


def test_a_refused_edit_still_says_which_image_it_was_about(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A refusal with no subject cannot be shown beside the asset it concerned."""
    ws = _ws(tmp_path)
    _ready(ws, monkeypatch)
    original = _seed_original(ws, monkeypatch)

    def unreachable(*args: Any, **kwargs: Any) -> dict:
        raise tier2_image.SandboxError("fetch_failed:TimeoutError")

    monkeypatch.setattr(tier2_image, "post_multipart", unreachable)
    _generate(ws, profile_id="openai-hosted", prompt="bluer", source_generation_id=original)

    rows = SQLiteStore(ws).list_image_generations(owner_principal_id="principal_owner")
    refused = next(row for row in rows if row["status"] == "refused")
    assert refused["source_generation_id"] == original
    assert refused["kind"] == "edit"


# ── Variations ───────────────────────────────────────────────────────────────


def test_a_variation_request_stores_one_asset_per_picture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Four pictures are four things an owner can pin, compare and edit."""
    ws = _ws(tmp_path)
    _ready(ws, monkeypatch)
    seen: dict[str, Any] = {}

    def fake_json(url: str, payload: dict[str, Any], **kwargs: Any) -> dict:
        seen.update(payload=payload)
        return {
            "data": [{"b64_json": base64.b64encode(PNG).decode()} for _ in range(3)]
        }

    monkeypatch.setattr(tier2_image, "post_json", fake_json)
    result = _generate(ws, profile_id="openai-hosted", prompt="a cat", variations=3)

    assert result.decision == "allow", result.error
    assert seen["payload"]["n"] == 3
    rows = SQLiteStore(ws).list_image_generations(owner_principal_id="principal_owner")
    assert len(rows) == 3
    assert {row["kind"] for row in rows} == {"variation"}
    assert len({row["attachment_id"] for row in rows}) == 3


def test_more_variations_than_the_cap_are_refused_rather_than_clamped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A count is an action argument, so it is bounded like the size and the prompt."""
    ws = _ws(tmp_path)
    _ready(ws, monkeypatch)

    def refuse(*args: Any, **kwargs: Any) -> dict:
        raise AssertionError("an out-of-range count must not reach a provider")

    monkeypatch.setattr(tier2_image, "post_json", refuse)
    result = _generate(
        ws, profile_id="openai-hosted", prompt="a cat", variations=tier2_image.MAX_VARIATIONS + 1
    )

    assert (result.error or "").startswith("unsupported_variation_count:")
    rows = SQLiteStore(ws).list_image_generations(owner_principal_id="principal_owner")
    assert str(rows[0]["reason_code"]).startswith("unsupported_variation_count:")


def test_a_provider_returning_fewer_pictures_than_asked_is_not_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The count is what was asked for; what came back is what there is."""
    ws = _ws(tmp_path)
    _ready(ws, monkeypatch)
    monkeypatch.setattr(
        tier2_image,
        "post_json",
        lambda *a, **k: {"data": [{"b64_json": base64.b64encode(PNG).decode()}]},
    )

    assert _generate(ws, profile_id="openai-hosted", prompt="a cat", variations=4).decision == "allow"
    rows = SQLiteStore(ws).list_image_generations(owner_principal_id="principal_owner")
    assert len(rows) == 1


def test_asking_for_no_images_is_refused_rather_than_treated_as_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Found live on 2026-09-12.

    The count was read as `int(arguments.get("variations", 1) or 1)`, and zero is
    falsy — so a request for no images became a request for one and spent the
    owner's credit on a picture they had not asked for. Absent and zero are
    different requests, and only one of them has a default.
    """
    ws = _ws(tmp_path)
    _ready(ws, monkeypatch)

    def refuse(*args: Any, **kwargs: Any) -> dict:
        raise AssertionError("a zero count must not reach a provider")

    monkeypatch.setattr(tier2_image, "post_json", refuse)
    result = _generate(ws, profile_id="openai-hosted", prompt="a cat", variations=0)

    assert result.error == "unsupported_variation_count:0"


def test_an_absent_count_still_means_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other half: naming no count is not naming zero."""
    ws = _ws(tmp_path)
    _ready(ws, monkeypatch)
    monkeypatch.setattr(
        tier2_image,
        "post_json",
        lambda *a, **k: {"data": [{"b64_json": base64.b64encode(PNG).decode()}]},
    )

    assert _generate(ws, profile_id="openai-hosted", prompt="a cat").decision == "allow"
    assert len(SQLiteStore(ws).list_image_generations(owner_principal_id="principal_owner")) == 1
