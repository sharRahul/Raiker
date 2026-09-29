"""CR-04 — an embedding's sensitivity is read from its text, not from its caller.

``ModelProviderExecutor`` took ``sensitivity`` from the action and checked only
that it was a string. A credential labelled ``public`` went to a hosted
embedding provider, and its first 120 characters were stored as the vector's
plaintext preview. These tests hold the replacement: the content is classified,
a caller's label can only tighten it, secret-shaped text reaches no provider at
all, and personal text is embedded without a plaintext preview beside it.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.models.contracts import EmbeddingResponse
from raiker.runtime.authority import GovernedAction
from raiker.runtime.authority.models import Principal, RiskLevelValue
from raiker.runtime.executors.models_runtime import ModelProviderExecutor, effective_sensitivity
from raiker.storage.sqlite import SQLiteStore
from tests.factories import governed_action

# Built at runtime and deliberately not provider-shaped: a fixture must not look
# like a real key to a secret scanner, and only needs to be credential-*shaped*.
_CREDENTIAL = "api_key = " + "demo" * 6
_PERSONAL = "My phone number is +44 7700 900123 and I live at 10 Downing Street."


@pytest.fixture
def harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[ModelProviderExecutor, Principal, list[str], SQLiteStore]:
    monkeypatch.setenv("RAIKER_MODEL_EGRESS_ALLOWLIST", "api.openai.com")
    ws = tmp_path / "embed_ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    store = SQLiteStore(ws)
    sent: list[str] = []

    def embed(provider: str, model: str, text: str) -> EmbeddingResponse:
        sent.append(text)
        return EmbeddingResponse(vector=[0.1, 0.2, 0.3], model=model, usage={})

    executor = ModelProviderExecutor(ws, store, embedder=embed)
    raw = store.get_principal("principal_owner")
    assert raw is not None
    return executor, Principal(**raw), sent, store


def _embed(text: str, **extra: object) -> GovernedAction:
    return governed_action(
        "model_embed",
        principal_id="principal_owner",
        arguments={"operation": "embed", "text": text, "provider": "openai", "model": "m", **extra},
        risk_level=RiskLevelValue.MEDIUM,
    )


@pytest.mark.parametrize("operation", ["embed", "embed_query"])
def test_a_credential_labelled_public_reaches_no_provider(harness, operation: str) -> None:  # type: ignore[no-untyped-def]
    executor, principal, sent, store = harness
    result = executor.execute(_embed(_CREDENTIAL, sensitivity="public", operation=operation), principal)
    assert result.ok is False
    assert result.reason_code == "embedding_sensitivity_not_projectable"
    assert sent == []
    assert store.list_vector_records() == []


def test_personal_text_is_embedded_without_a_plaintext_preview(harness) -> None:  # type: ignore[no-untyped-def]
    executor, principal, sent, store = harness
    result = executor.execute(_embed(_PERSONAL, sensitivity="public"), principal)
    assert result.ok is True, result.reason_code
    [record] = store.list_vector_records()
    assert record["sensitivity"] == "personal"
    assert record["content_preview"] == ""


def test_a_callers_stricter_label_stands(harness) -> None:  # type: ignore[no-untyped-def]
    executor, principal, _sent, store = harness
    result = executor.execute(_embed("The build uses Vite.", sensitivity="personal"), principal)
    assert result.ok is True, result.reason_code
    [record] = store.list_vector_records()
    assert record["sensitivity"] == "personal"
    assert record["content_preview"] == ""


def test_ordinary_text_keeps_its_bounded_preview(harness) -> None:  # type: ignore[no-untyped-def]
    executor, principal, _sent, store = harness
    result = executor.execute(_embed("The build uses Vite.", sensitivity="public"), principal)
    assert result.ok is True, result.reason_code
    [record] = store.list_vector_records()
    assert record["content_preview"] == "The build uses Vite."


def test_the_label_can_tighten_and_never_loosen() -> None:
    assert effective_sensitivity(_CREDENTIAL, "public") == "credential_like"
    assert effective_sensitivity("hello", "secret_like") == "secret_like"
    # A label the runtime cannot read is not evidence of harmlessness.
    assert effective_sensitivity("hello", "totally-fine") == "totally-fine"
