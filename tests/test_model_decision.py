"""MODEL-01 — one authoritative answer about which model, and which one runs.

The failure this closes is not a missing feature. Every part of the decision was
already persisted correctly: the global selection, the per-surface default, the
readiness verdict, the ordered fallback sequence and the managed local runtime.
They were five stores read through five paths, and each surface assembled its
own answer from whichever subset it happened to need — so the Models page, the
composer picker, Chat, Build and Design agreed only by coincidence, and when
they disagreed nobody could say which was wrong. Each was telling the truth
about a different question.

The invariant under test throughout:

    A selected model never disappears because it is not currently ready.

It is reported as selected-and-unavailable, with the reason and the fix beside
it, and the model that *would* actually serve is named separately. Replacing the
displayed selection with the first ready model is the behaviour that makes
persistence look broken to an owner who did nothing wrong.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.models.decision import SURFACES, ModelDecisionService
from raiker.models.readiness import (
    ModelReadiness,
    ModelReadinessKey,
    ModelReadinessService,
    ModelReadinessState,
)
from raiker.storage.sqlite import SQLiteStore

OWNER = "principal_owner"
LOCAL = "ollama-local-openai-compatible"
HOSTED = "anthropic-hosted"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "model-decision"
    root.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=root)
    return root


@pytest.fixture
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


@pytest.fixture
def owner_token(workspace: Path) -> str:
    token, _session = ApiSessionStore(workspace).create_session(OWNER)
    return token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class _StubReadiness(ModelReadinessService):
    """A readiness service whose verdicts the test states outright.

    Real readiness reaches a provider, and the question here is what the
    decision service *does* with a verdict rather than how the verdict is
    reached. `ready` names the pairs that can serve; everything else is
    reported unreachable, which is the ordinary way a model fails.
    """

    def __init__(self, store: object, ready: set[tuple[str, str]], chain: list[tuple[str, str]]):
        self._ready = ready
        self._chain = chain

    def resolve_request_target(  # type: ignore[override]
        self, owner_principal_id: str, profile_id: str | None, model: str | None
    ) -> tuple[str, str]:
        if profile_id:
            return profile_id, (model or "").strip() or f"{profile_id}-default"
        return self._chain[0]

    def _verdict(self, pair: tuple[str, str]) -> ModelReadiness:
        ready = pair in self._ready
        return ModelReadiness(
            key=ModelReadinessKey(OWNER, pair[0], pair[1], ""),
            state=ModelReadinessState.READY if ready else ModelReadinessState.UNREACHABLE,
            checked_at=None,
            expires_at=None,
            summary="Ready." if ready else "The provider could not be reached.",
            reason_code="ready" if ready else "unreachable",
            remediation="" if ready else "Check the provider's status and your connection.",
            evidence={},
        )

    def resolve_chain(  # type: ignore[override]
        self, owner_principal_id: str, profile_id: str | None, model: str | None
    ) -> list[ModelReadiness]:
        head = self.resolve_request_target(owner_principal_id, profile_id, model)
        rest = [pair for pair in self._chain if pair != head]
        return [self._verdict(pair) for pair in [head, *rest]]


def _service(
    store: SQLiteStore,
    *,
    ready: set[tuple[str, str]],
    chain: list[tuple[str, str]],
) -> ModelDecisionService:
    return ModelDecisionService(store, readiness=_StubReadiness(store, ready, chain))


class TestTheSurfacesThatMayHoldADefault:
    def test_the_three_work_modes_are_all_present(self) -> None:
        # MODEL-02. Design was absent while the product model was Chat | Build |
        # Design, so a Design model choice silently followed whatever Chat had.
        assert "design" in SURFACES
        for mode in ("chat", "build", "design"):
            assert mode in SURFACES


class TestSelectionResolvesMostSpecificFirst:
    def test_a_surface_default_wins_over_the_global_choice(self, workspace: Path) -> None:
        store = SQLiteStore(workspace)
        store.save_surface_model_default(OWNER, "build", HOSTED, "claude-big")

        decision = _service(
            store, ready={(HOSTED, "claude-big")}, chain=[(LOCAL, "small")]
        ).decide(OWNER, "build")

        assert decision.selected.profile_id == HOSTED
        assert decision.selected.model == "claude-big"
        assert decision.selected.source == "surface_default"

    def test_a_surface_with_no_opinion_reports_where_its_model_came_from(
        self, workspace: Path
    ) -> None:
        # The distinction matters to the interface: "you have not chosen a model
        # yet" and "your global choice applies here" need different copy, and
        # only one of them should send the owner to the Models page.
        store = SQLiteStore(workspace)

        decision = _service(
            store, ready={(LOCAL, "small")}, chain=[(LOCAL, "small")]
        ).decide(OWNER, "design")

        assert decision.selected.source == "native_default"

    def test_each_work_mode_resolves_its_own_default(self, workspace: Path) -> None:
        # The whole point of a surface default: Chat on the small local model,
        # Build on the big hosted one, Design on the one that draws.
        store = SQLiteStore(workspace)
        store.save_surface_model_default(OWNER, "chat", LOCAL, "small")
        store.save_surface_model_default(OWNER, "build", HOSTED, "claude-big")
        store.save_surface_model_default(OWNER, "design", HOSTED, "image-model")

        service = _service(
            store,
            ready={(LOCAL, "small"), (HOSTED, "claude-big"), (HOSTED, "image-model")},
            chain=[(LOCAL, "small")],
        )

        assert service.decide(OWNER, "chat").selected.model == "small"
        assert service.decide(OWNER, "build").selected.model == "claude-big"
        assert service.decide(OWNER, "design").selected.model == "image-model"


class TestAnUnavailableSelectionStaysSelected:
    def test_the_selection_survives_being_unready(self, workspace: Path) -> None:
        store = SQLiteStore(workspace)
        store.save_surface_model_default(OWNER, "chat", HOSTED, "claude-big")

        decision = _service(
            store,
            ready={(LOCAL, "small")},
            chain=[(HOSTED, "claude-big"), (LOCAL, "small")],
        ).decide(OWNER, "chat")

        # This is the invariant. Before MODEL-01 a picker that could not reach
        # Anthropic re-rendered showing the local model, which is
        # indistinguishable from having lost the owner's choice.
        assert decision.selected.profile_id == HOSTED
        assert decision.selected.model == "claude-big"

    def test_the_fallback_is_named_rather_than_substituted(self, workspace: Path) -> None:
        store = SQLiteStore(workspace)
        store.save_surface_model_default(OWNER, "chat", HOSTED, "claude-big")

        decision = _service(
            store,
            ready={(LOCAL, "small")},
            chain=[(HOSTED, "claude-big"), (LOCAL, "small")],
        ).decide(OWNER, "chat")

        assert decision.effective.profile_id == LOCAL
        assert decision.effective.source == "fallback"
        assert decision.ready is True

    def test_the_obstacle_travels_with_the_selection(self, workspace: Path) -> None:
        store = SQLiteStore(workspace)
        store.save_surface_model_default(OWNER, "chat", HOSTED, "claude-big")

        decision = _service(
            store,
            ready={(LOCAL, "small")},
            chain=[(HOSTED, "claude-big"), (LOCAL, "small")],
        ).decide(OWNER, "chat")

        assert decision.problem is not None
        assert decision.problem["reason_code"] == "unreachable"
        # The remediation is readiness's own words. An interface that invented
        # its own would be guessing about a provider it never contacted.
        assert decision.problem["remediation"]

    def test_nothing_ready_keeps_the_selection_and_says_so(self, workspace: Path) -> None:
        store = SQLiteStore(workspace)
        store.save_surface_model_default(OWNER, "chat", HOSTED, "claude-big")

        decision = _service(
            store, ready=set(), chain=[(HOSTED, "claude-big"), (LOCAL, "small")]
        ).decide(OWNER, "chat")

        assert decision.ready is False
        assert decision.selected.model == "claude-big"
        assert decision.effective.model == "claude-big"
        assert decision.effective.source == "no_ready_candidate"
        assert decision.problem is not None


class TestAReadySelectionIsNotDescribedAsAFallback:
    def test_the_effective_model_is_the_selection_itself(self, workspace: Path) -> None:
        store = SQLiteStore(workspace)
        store.save_surface_model_default(OWNER, "build", HOSTED, "claude-big")

        decision = _service(
            store,
            ready={(HOSTED, "claude-big"), (LOCAL, "small")},
            chain=[(HOSTED, "claude-big"), (LOCAL, "small")],
        ).decide(OWNER, "build")

        assert decision.effective.source == "selected"
        assert decision.problem is None
        assert decision.ready is True


class TestRunningIsOnlyClaimedWhereItMeansSomething:
    def test_a_hosted_model_reports_no_running_state(self, workspace: Path) -> None:
        # "Not running" is not a true statement about somebody else's endpoint,
        # and rendering it as false puts a stopped-looking state beside a model
        # that is working perfectly.
        store = SQLiteStore(workspace)
        store.save_surface_model_default(OWNER, "chat", HOSTED, "claude-big")

        decision = _service(
            store, ready={(HOSTED, "claude-big")}, chain=[(HOSTED, "claude-big")]
        ).decide(OWNER, "chat")

        assert decision.running is None


class TestTheRevisionChangesWhenTheDecisionDoes:
    def test_the_same_decision_gives_the_same_token(self, workspace: Path) -> None:
        store = SQLiteStore(workspace)
        store.save_surface_model_default(OWNER, "chat", HOSTED, "claude-big")
        service = _service(
            store, ready={(HOSTED, "claude-big")}, chain=[(HOSTED, "claude-big")]
        )

        assert service.decide(OWNER, "chat").revision == service.decide(OWNER, "chat").revision

    def test_changing_a_surface_default_changes_the_token(self, workspace: Path) -> None:
        store = SQLiteStore(workspace)
        store.save_surface_model_default(OWNER, "chat", HOSTED, "claude-big")
        service = _service(
            store,
            ready={(HOSTED, "claude-big"), (LOCAL, "small")},
            chain=[(HOSTED, "claude-big")],
        )
        before = service.decide(OWNER, "chat").revision

        store.save_surface_model_default(OWNER, "chat", LOCAL, "small")

        assert service.decide(OWNER, "chat").revision != before


class TestTheEndpoint:
    def test_requires_authentication(self, client: TestClient) -> None:
        assert client.get("/api/model-decision?surface=chat").status_code == 401

    def test_rejects_a_surface_raiker_does_not_have(
        self, client: TestClient, owner_token: str
    ) -> None:
        response = client.get(
            "/api/model-decision?surface=not-a-surface", headers=_auth(owner_token)
        )
        assert response.status_code == 422
        assert response.json()["detail"]["reason_code"] == "unknown_surface"

    def test_answers_the_full_contract_for_every_work_mode(
        self, client: TestClient, owner_token: str
    ) -> None:
        for surface in ("chat", "build", "design"):
            body = client.get(
                f"/api/model-decision?surface={surface}", headers=_auth(owner_token)
            ).json()
            assert body["scope"] == {"surface": surface, "project_id": None}
            for part in ("selected", "effective"):
                assert set(body[part]) >= {"profile_id", "model"}
            assert "reason" in body["effective"]
            assert set(body) >= {"scope", "selected", "effective", "ready", "running", "problem", "revision"}

    def test_a_saved_surface_default_is_visible_through_the_contract(
        self, client: TestClient, owner_token: str
    ) -> None:
        # The acceptance path from the review, end to end over HTTP: choose a
        # model for one surface, then read the decision back and find it there
        # rather than the global default.
        client.put(
            "/api/surface-models",
            headers=_auth(owner_token),
            json={"surface": "design", "profile_id": LOCAL, "model": "gemma4:31b-cloud"},
        )

        body = client.get(
            "/api/model-decision?surface=design", headers=_auth(owner_token)
        ).json()

        assert body["selected"]["profile_id"] == LOCAL
        assert body["selected"]["model"] == "gemma4:31b-cloud"
        assert body["selected"]["source"] == "surface_default"
        # And it did not leak into a surface that never asked for it.
        chat = client.get("/api/model-decision?surface=chat", headers=_auth(owner_token)).json()
        assert chat["selected"]["source"] != "surface_default"
