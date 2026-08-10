"""The readiness gate must judge the chain the runtime will actually try.

Raiker already lets the owner order a fallback sequence, and
``RuntimeOrchestrator._provider_chain`` really does try each entry in turn when
the one before it fails. A gate that only looks at the primary therefore
contradicts the runtime twice over:

* it refuses work the owner configured a ready fallback for, and
* it admits work whose fallbacks were never probed at all.

Both are fixed by resolving the same chain the orchestrator will build.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.models.readiness import (
    ModelNotReady,
    ModelReadinessService,
    ModelReadinessState,
    ProviderCatalogueProbe,
)
from raiker.storage.sqlite import SQLiteStore


class MarkModelReady(Protocol):
    """Keyword-callable view of the shared ``mark_model_ready`` fixture."""

    def __call__(
        self,
        workspace: Path,
        principal_id: str = "principal_owner",
        profile_id: str = "ollama-local-openai-compatible",
        model: str = "gemma4:31b-cloud",
    ) -> None: ...


PRIMARY = "ollama-local-openai-compatible"
PRIMARY_MODEL = "gemma4:31b-cloud"
FALLBACK = "anthropic-hosted"
FALLBACK_MODEL = "claude-haiku-4-5-20251001"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "readiness-fallback"
    root.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=root)
    return root


def _service(workspace: Path) -> ModelReadinessService:
    store = SQLiteStore(workspace)
    return ModelReadinessService(store, probe=ProviderCatalogueProbe(store))


def test_ready_fallback_admits_work_the_primary_cannot_serve(
    workspace: Path, mark_model_ready: MarkModelReady
) -> None:
    store = SQLiteStore(workspace)
    store.save_principal_model_fallback_sequence("principal_owner", [FALLBACK])
    # What "Use model" on the Anthropic card persists: a hosted profile ships a
    # `<model>` placeholder, so the pin is the only thing that makes it runnable.
    store.save_configured_model("principal_owner", FALLBACK, FALLBACK_MODEL)
    mark_model_ready(workspace, profile_id=FALLBACK, model=FALLBACK_MODEL)

    readiness = _service(workspace).require_ready(
        "principal_owner", PRIMARY, PRIMARY_MODEL
    )

    assert readiness.state is ModelReadinessState.READY
    assert readiness.key.profile_id == FALLBACK


def test_refusal_reports_the_primary_when_no_chain_entry_is_ready(
    workspace: Path,
) -> None:
    store = SQLiteStore(workspace)
    store.save_principal_model_fallback_sequence("principal_owner", [FALLBACK])
    # What "Use model" on the Anthropic card persists: a hosted profile ships a
    # `<model>` placeholder, so the pin is the only thing that makes it runnable.
    store.save_configured_model("principal_owner", FALLBACK, FALLBACK_MODEL)

    with pytest.raises(ModelNotReady) as caught:
        _service(workspace).require_ready("principal_owner", PRIMARY, PRIMARY_MODEL)

    assert caught.value.readiness.key.profile_id == PRIMARY


def test_a_ready_primary_still_wins_over_a_ready_fallback(
    workspace: Path, mark_model_ready: MarkModelReady
) -> None:
    store = SQLiteStore(workspace)
    store.save_principal_model_fallback_sequence("principal_owner", [FALLBACK])
    # What "Use model" on the Anthropic card persists: a hosted profile ships a
    # `<model>` placeholder, so the pin is the only thing that makes it runnable.
    store.save_configured_model("principal_owner", FALLBACK, FALLBACK_MODEL)
    mark_model_ready(workspace, profile_id=PRIMARY, model=PRIMARY_MODEL)
    mark_model_ready(workspace, profile_id=FALLBACK, model=FALLBACK_MODEL)

    readiness = _service(workspace).require_ready(
        "principal_owner", PRIMARY, PRIMARY_MODEL
    )

    assert readiness.key.profile_id == PRIMARY


def test_chain_readiness_lists_every_candidate_for_the_owner(
    workspace: Path, mark_model_ready: MarkModelReady
) -> None:
    store = SQLiteStore(workspace)
    store.save_principal_model_fallback_sequence("principal_owner", [FALLBACK])
    # What "Use model" on the Anthropic card persists: a hosted profile ships a
    # `<model>` placeholder, so the pin is the only thing that makes it runnable.
    store.save_configured_model("principal_owner", FALLBACK, FALLBACK_MODEL)
    mark_model_ready(workspace, profile_id=FALLBACK, model=FALLBACK_MODEL)

    chain = _service(workspace).resolve_chain("principal_owner", PRIMARY, PRIMARY_MODEL)

    assert [entry.key.profile_id for entry in chain] == [PRIMARY, FALLBACK]
    assert chain[0].ready is False
    assert chain[1].ready is True
