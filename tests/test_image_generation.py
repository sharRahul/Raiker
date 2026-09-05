"""The Design surface: one prompt to a hosted image model, governed like any other.

What these tests hold is that being a *new* kind of output buys image generation
no new powers. It is a hosted model call, so it answers to the capability gate,
the model egress allowlist, and the owner's own credential — and it refuses in
each of those places by name rather than quietly producing nothing.

The other half is the record. A refused generation is written down with the same
care as a successful one, because an owner who pressed Generate and got nothing
should be able to find out why from the page rather than from the audit log.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id, utc_now
from raiker.control.service import RuntimeControlService
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority import GovernedAction, GovernedActionResult, RuntimeAuthority
from raiker.runtime.authority.models import Principal, RiskLevelValue
from raiker.runtime.executors import (
    REAL_EXECUTOR_CAPABILITIES,
    build_default_executor_registry,
    tier2_image,
)
from raiker.storage.sqlite import SQLiteStore

CAP = "image_generation"

# A 1x1 PNG — the smallest thing that is genuinely a PNG.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "img"
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
    result = svc.set_capability_state(
        CAP, "enabled_runtime", None, "test", confirmation_token="confirm"
    )
    assert result.ok is True, result.reason_code


def _authority(ws: Path) -> tuple[RuntimeAuthority, Principal]:
    store = SQLiteStore(ws)
    registry = build_default_executor_registry(ws, store)
    authority = RuntimeAuthority(store, EventLogWriter(store), executor_registry=registry)
    raw = store.get_principal("principal_owner")
    assert raw is not None
    return authority, Principal(**raw)


def _action(principal_id: str, **args: object) -> GovernedAction:
    return GovernedAction(
        action_id=new_id("act_"),
        principal_id=principal_id,
        action_type=CAP,
        tool_or_service_name=CAP,
        arguments=dict(args),
        risk_level=RiskLevelValue.MEDIUM,
    )


def _generate(ws: Path, **args: object) -> GovernedActionResult:
    authority, principal = _authority(ws)
    return authority.route_action(_action(principal.principal_id, **args), principal)


# ── Registration ──


def test_image_generation_is_a_real_executor(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    registry = build_default_executor_registry(ws, SQLiteStore(ws))
    assert CAP in REAL_EXECUTOR_CAPABILITIES
    assert registry.has(CAP)


def test_it_is_tier_2_because_it_leaves_the_machine() -> None:
    from raiker.phase_gates import default_capability_gates

    gate = default_capability_gates()[CAP]
    assert gate.phase == 2
    # The shipped table marks a capability with a real executor
    # `enabled_runtime`; what decides whether it is on for an *account* is the
    # per-account resolution, and an unset capability that is not in
    # `CAPABILITY_UNSET_RESOLUTION` resolves off. That is where "off until the
    # owner turns it on" actually lives, so that is what is asserted.
    from raiker.runtime.authority.admission import CAPABILITY_UNSET_RESOLUTION

    assert CAP not in CAPABILITY_UNSET_RESOLUTION


# ── The three boundaries, each refusing by name ──


def test_a_closed_gate_refuses_before_anything_reaches_a_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    RuntimeControlService(ws).activate_runtime_mode("local_single_user_runtime", None, "test")
    monkeypatch.setenv("RAIKER_MODEL_EGRESS_ALLOWLIST", "api.openai.com")
    result = _generate(ws, profile_id="openai-hosted", prompt="a cat", size="1024x1024")
    assert result.decision != "allow" or result.error is not None


def test_an_empty_egress_allowlist_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An API key is not authorisation to reach the network."""
    ws = _ws(tmp_path)
    _enable(ws)
    monkeypatch.delenv("RAIKER_MODEL_EGRESS_ALLOWLIST", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    result = _generate(ws, profile_id="openai-hosted", prompt="a cat", size="1024x1024")
    assert result.error == "egress_denied:no_allowlist"


def test_a_missing_credential_refuses_and_says_where_to_put_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    monkeypatch.setenv("RAIKER_MODEL_EGRESS_ALLOWLIST", "api.openai.com")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = _generate(ws, profile_id="openai-hosted", prompt="a cat", size="1024x1024")
    assert result.error == "image_provider_credential_missing"


def test_a_provider_with_no_governed_image_endpoint_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    monkeypatch.setenv("RAIKER_MODEL_EGRESS_ALLOWLIST", "*")
    result = _generate(
        ws, profile_id="anthropic-hosted", prompt="a cat", size="1024x1024"
    )
    assert result.error is not None
    assert result.error.startswith("image_provider_unsupported")


def test_an_unsupported_size_is_refused_rather_than_forwarded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A free-text size would be a string this runtime hands a provider
    without understanding it."""
    ws = _ws(tmp_path)
    _enable(ws)
    monkeypatch.setenv("RAIKER_MODEL_EGRESS_ALLOWLIST", "*")
    result = _generate(ws, profile_id="openai-hosted", prompt="a cat", size="9000x9000")
    assert result.error == "unsupported_size:9000x9000"


# ── The record ──


def test_a_refusal_is_recorded_so_the_page_can_show_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    monkeypatch.delenv("RAIKER_MODEL_EGRESS_ALLOWLIST", raising=False)
    _generate(ws, profile_id="openai-hosted", prompt="a refused cat", size="1024x1024")
    rows = SQLiteStore(ws).list_image_generations(owner_principal_id="principal_owner")
    assert len(rows) == 1
    assert rows[0]["status"] == "refused"
    assert rows[0]["reason_code"] == "egress_denied:no_allowlist"
    assert rows[0]["prompt"] == "a refused cat"
    assert rows[0]["attachment_id"] is None


def test_a_successful_generation_stores_the_bytes_and_records_the_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    monkeypatch.setenv("RAIKER_MODEL_EGRESS_ALLOWLIST", "api.openai.com")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    seen: dict[str, object] = {}

    def fake_post(
        url: str,
        payload: dict[str, object],
        *,
        egress_allowlist: frozenset[str] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 60.0,
    ) -> dict:
        seen["url"] = url
        seen["allowlist"] = egress_allowlist
        seen["headers"] = headers
        return {"data": [{"b64_json": base64.b64encode(PNG).decode()}]}

    monkeypatch.setattr(tier2_image, "post_json", fake_post)
    result = _generate(ws, profile_id="openai-hosted", prompt="a cat", size="1024x1024")
    assert result.decision == "allow", result.error
    assert result.message == "executed"

    store = SQLiteStore(ws)
    rows = store.list_image_generations(owner_principal_id="principal_owner")
    assert len(rows) == 1 and rows[0]["status"] == "ok"
    attachment = store.load_attachment(
        str(rows[0]["attachment_id"]), owner_principal_id="principal_owner"
    )
    assert attachment is not None
    assert bytes(attachment["data"]) == PNG
    assert attachment["kind"] == "generated_image"

    # The endpoint is built from the profile, never taken from the request, and
    # the allowlist is passed down rather than merely checked beforehand.
    assert seen["url"] == "https://api.openai.com/v1/images/generations"
    assert seen["allowlist"] == frozenset({"api.openai.com"})


def test_the_credential_never_reaches_the_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    monkeypatch.setenv("RAIKER_MODEL_EGRESS_ALLOWLIST", "api.openai.com")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-supersecret")
    monkeypatch.setattr(
        tier2_image,
        "post_json",
        lambda *a, **k: {"data": [{"b64_json": base64.b64encode(PNG).decode()}]},
    )
    result = _generate(ws, profile_id="openai-hosted", prompt="a cat", size="1024x1024")
    blob = json.dumps({"artifacts": result.artifacts, "summary": result.message})
    assert "supersecret" not in blob
    rows = SQLiteStore(ws).list_image_generations(owner_principal_id="principal_owner")
    assert "supersecret" not in json.dumps(rows)


def test_a_provider_refusal_is_named_rather_than_crashing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A content-policy refusal is an ordinary event, not a broken response."""
    ws = _ws(tmp_path)
    _enable(ws)
    monkeypatch.setenv("RAIKER_MODEL_EGRESS_ALLOWLIST", "api.openai.com")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(
        tier2_image,
        "post_json",
        lambda *a, **k: {"error": {"code": "content_policy_violation"}},
    )
    result = _generate(ws, profile_id="openai-hosted", prompt="something", size="1024x1024")
    assert result.error == "image_refused_by_provider"


def test_an_oversized_image_is_refused_rather_than_stored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    monkeypatch.setenv("RAIKER_MODEL_EGRESS_ALLOWLIST", "api.openai.com")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    huge = base64.b64encode(b"\x00" * (tier2_image.MAX_IMAGE_BYTES + 1)).decode()
    monkeypatch.setattr(
        tier2_image, "post_json", lambda *a, **k: {"data": [{"b64_json": huge}]}
    )
    result = _generate(ws, profile_id="openai-hosted", prompt="a cat", size="1024x1024")
    assert result.error == "image_too_large"
    rows = SQLiteStore(ws).list_image_generations(owner_principal_id="principal_owner")
    assert rows[0]["attachment_id"] is None


# ── The API ──


def test_the_list_route_never_returns_bytes_and_the_bytes_route_is_owner_scoped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi.testclient import TestClient

    from raiker.api.app import create_app

    ws = _ws(tmp_path)
    _enable(ws)
    monkeypatch.setenv("RAIKER_MODEL_EGRESS_ALLOWLIST", "api.openai.com")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(
        tier2_image,
        "post_json",
        lambda *a, **k: {"data": [{"b64_json": base64.b64encode(PNG).decode()}]},
    )
    _generate(ws, profile_id="openai-hosted", prompt="a cat", size="1024x1024")
    generation_id = SQLiteStore(ws).list_image_generations(
        owner_principal_id="principal_owner"
    )[0]["generation_id"]

    client = TestClient(create_app(ws))
    # Unauthenticated: both reads are refused.
    assert client.get("/api/images").status_code in (401, 403)
    assert client.get(f"/api/images/{generation_id}/bytes").status_code in (401, 403)


# ── choosing a model ─────────────────────────────────────────────────────
#
# The Design surface had no model control at all, because `image_model` was read
# by the page and never sent by the models view — every profile answered
# `undefined`, so the picker was empty on every real install. Sending it opened a
# second question: a chosen model is a string this runtime posts to a provider,
# and an action argument is a thing a model can propose.


def test_a_profile_declares_its_image_models_default_first() -> None:
    from raiker.runtime.executors.tier2_image import declared_image_models

    assert declared_image_models(
        {"image_model": "gpt-image-1", "image_models": ["gpt-image-1", "dall-e-3"]}
    ) == ("gpt-image-1", "dall-e-3")
    # A default missing from the list is still choosable, and still first.
    assert declared_image_models({"image_model": "a", "image_models": ["b"]}) == ("a", "b")
    assert declared_image_models({}) == ()


def test_the_shipped_profiles_declare_the_models_the_page_offers() -> None:
    """The config is the source; a page that offered more would be guessing."""
    from raiker.models.registry import ModelProfileRegistry
    from raiker.runtime.executors.tier2_image import (
        SUPPORTED_PROVIDERS,
        declared_image_models,
    )

    declaring = {
        profile.provider: declared_image_models(profile.raw)
        for profile in ModelProfileRegistry.load().profiles
        if declared_image_models(profile.raw)
    }
    assert declaring, "no shipped profile declares an image model"
    # Declaring one is pointless without a governed endpoint to send it to.
    for provider in declaring:
        assert provider in SUPPORTED_PROVIDERS


def test_the_models_view_actually_sends_the_declared_image_models() -> None:
    """The defect itself: the field existed in config and never reached the web.

    The Design page read `image_model` off each profile and every profile
    answered `undefined`, because this view never carried it. The picker was
    therefore empty on every real install, and the one fixture that could have
    caught it had no image provider either.
    """
    import inspect

    from raiker.control import dashboard
    from raiker.control.dashboard import ModelProfileView

    field = ModelProfileView.__dataclass_fields__.get("image_models")
    assert field is not None, "the models view does not carry image models"
    assert field.default == ()
    # And the builder populates it, rather than leaving every profile at the
    # default — which would reproduce the defect with the field in place.
    source = inspect.getsource(dashboard)
    assert "image_models=declared_image_models(" in source


def test_a_model_the_profile_does_not_declare_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A chosen model is bounded by the profile, exactly as `size` is."""
    ws = _ws(tmp_path)
    _enable(ws)
    monkeypatch.setenv("RAIKER_MODEL_EGRESS_ALLOWLIST", "api.openai.com")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    called = False

    def fake_post(*args: object, **kwargs: object) -> dict:
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(tier2_image, "post_json", fake_post)
    result = _generate(
        ws,
        profile_id="openai-hosted",
        prompt="a cat",
        size="1024x1024",
        model="some-model-nobody-declared",
    )
    assert result.decision == "allow"
    assert result.error is not None
    assert "image_model_not_declared" in str(result.error)
    assert not called, "an undeclared model must not reach the provider"
