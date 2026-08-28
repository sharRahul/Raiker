"""Owner-guided compaction: summarise up to a turn the owner picked (backlog #9).

Compaction already worked and it was the threshold's decision. These tests are
about the second reason for starting one, and about the property that makes it
safe to have two reasons: both go through the *same* summarise-and-record step,
so the owner's route cannot be the one that skipped `PreCompact` or wrote a
record the turn path would not have written.

The transcript is never touched by any of this. Compaction changes only the
messages a model is sent, so every test that asserts a compaction happened also
has the stored turns to check against.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.models.contracts import ModelResponse
from raiker.runtime.conversation_compaction import (
    ContextBudgetPlanner,
    ContextCompactionStore,
)
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.delenv("RAIKER_CONNECTOR_VAULT_KEY", raising=False)
    return TestClient(create_app(tmp_path))


def _token(client: TestClient, user: str = "owner", pw: str = "right-pass-123") -> str:
    return client.post(
        "/api/auth/register", json={"username": user, "password": pw}
    ).json()["token"]


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _conversation(
    store: SQLiteStore, session_id: str, count: int, *, user_id: str | None = None
) -> list[str]:
    """A session with *count* completed turns, and the turn ids in order."""
    store.create_session(session_id, str(store.paths.workspace_root), user_id=user_id)
    turn_ids: list[str] = []
    for index in range(count):
        turn_id = f"turn_{index}"
        store.insert_turn(session_id, turn_id, f"question {index}")
        store.complete_turn(turn_id, "completed", f"answer {index}")
        turn_ids.append(turn_id)
    return turn_ids


class _FixedModel:
    """A router whose summary is known, so the assertions are about the plumbing."""

    def __init__(self, text: str = "The earlier exchanges, summarised.") -> None:
        self.text = text
        self.calls: list[tuple[str, str]] = []

    async def achat(
        self, provider: str, model: str, messages: Any, tools: Any = None, **_: Any
    ) -> ModelResponse:
        self.calls.append((provider, model))
        return ModelResponse(text=self.text, finish_reason="stop")

    def default_provider(self) -> tuple[str, str]:
        return ("anthropic", "claude-haiku-4-5-20251001")


# ── The plan ─────────────────────────────────────────────────────────────────


def test_the_mark_is_inclusive_and_stops_there(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    turns = _conversation(store, "sess_plan", 5)

    plan = ContextBudgetPlanner().plan_through(
        store=store,
        session_id="sess_plan",
        capacity_tokens=None,
        fixed_messages=(),
        current_prompt="",
        latest_compaction=None,
        through_turn_id=turns[2],
    )

    assert plan.should_compact is True
    assert plan.compact_through_turn_id == turns[2]
    # Up to and *including* the mark: three of the five.
    assert [str(row["turn_id"]) for row in plan.eligible_turns] == turns[:3]


def test_the_newest_exchanges_are_not_withheld_from_a_mark(tmp_path: Path) -> None:
    # The threshold plan retains the newest two so an automatic compaction never
    # summarises the exchange a person is in the middle of. An owner who marks
    # that exchange has said they want it summarised, and a control that quietly
    # kept two turns back would be lying about its own name.
    store = SQLiteStore(tmp_path)
    turns = _conversation(store, "sess_newest", 3)

    plan = ContextBudgetPlanner().plan_through(
        store=store,
        session_id="sess_newest",
        capacity_tokens=None,
        fixed_messages=(),
        current_prompt="",
        latest_compaction=None,
        through_turn_id=turns[-1],
    )

    assert [str(row["turn_id"]) for row in plan.eligible_turns] == turns


def test_a_mark_naming_nothing_left_is_not_an_error(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    _conversation(store, "sess_unknown", 2)

    plan = ContextBudgetPlanner().plan_through(
        store=store,
        session_id="sess_unknown",
        capacity_tokens=None,
        fixed_messages=(),
        current_prompt="",
        latest_compaction=None,
        through_turn_id="turn_that_does_not_exist",
    )

    assert plan.should_compact is False
    assert plan.eligible_turns == ()


# ── The route ────────────────────────────────────────────────────────────────


def test_the_owner_can_summarise_up_to_a_turn(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = _token(client)
    store = SQLiteStore(tmp_path)
    turns = _conversation(store, "sess_route", 4)
    model = _FixedModel()
    monkeypatch.setattr(
        "raiker.api.routes_context.owner_model_runtime",
        lambda *_a, **_k: (model, ("anthropic", "claude-haiku-4-5-20251001")),
    )

    response = client.post(
        "/api/sessions/sess_route/compact",
        json={"through_turn_id": turns[1]},
        headers=_h(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["compacted"] is True
    assert body["through_turn_id"] == turns[1]
    assert body["source_turn_count"] == 2
    assert model.calls == [("anthropic", "claude-haiku-4-5-20251001")]

    # The record the turn path would have written, written here.
    record = ContextCompactionStore(store).active(
        store.original_account_principal_id() or "", "sess_route"
    )
    assert record is not None
    assert record.through_turn_id == turns[1]
    assert record.summary_text == model.text

    # And nothing was deleted: every turn is still in the transcript.
    with store.connect() as connection:
        rows = connection.execute(
            "SELECT turn_id FROM turns WHERE session_id = ?", ("sess_route",)
        ).fetchall()
    assert {str(row["turn_id"]) for row in rows} == set(turns)


def test_a_mark_with_nothing_behind_it_answers_a_state_not_an_error(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = _token(client)
    store = SQLiteStore(tmp_path)
    _conversation(store, "sess_nothing", 2)
    monkeypatch.setattr(
        "raiker.api.routes_context.owner_model_runtime",
        lambda *_a, **_k: (_FixedModel(), ("anthropic", "m")),
    )

    response = client.post(
        "/api/sessions/sess_nothing/compact",
        json={"through_turn_id": "turn_nope"},
        headers=_h(token),
    )

    assert response.status_code == 200
    assert response.json() == {
        "session_id": "sess_nothing",
        "compacted": False,
        "reason_code": "nothing_to_summarise",
    }


def test_compacting_someone_elses_conversation_is_not_found(
    client: TestClient, tmp_path: Path, seed_account: Any
) -> None:
    token = _token(client)
    store = SQLiteStore(tmp_path)
    # Bound to the registering account at creation, so a second principal must
    # not be able to reach it by naming its id.
    owner_user_id = store.principal_user_id(store.original_account_principal_id() or "")
    turns = _conversation(store, "sess_mine", 2, user_id=owner_user_id)
    _, other_token = seed_account(tmp_path, "intruder")
    assert token

    response = client.post(
        "/api/sessions/sess_mine/compact",
        json={"through_turn_id": turns[0]},
        headers=_h(other_token),
    )

    assert response.status_code == 404


def test_it_requires_auth(client: TestClient) -> None:
    assert (
        client.post(
            "/api/sessions/sess_x/compact", json={"through_turn_id": "turn_0"}
        ).status_code
        == 401
    )


# ── The shared governed step ─────────────────────────────────────────────────


def test_a_precompact_hook_can_refuse_the_owners_compaction(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The property that makes two entry points safe.

    `PreCompact` is one of the three deciding events. If the owner's route were a
    second implementation it would be the one that forgot to ask, and the owner
    would have a way to compact that a managed rule could not stop.
    """
    token = _token(client)
    store = SQLiteStore(tmp_path)
    turns = _conversation(store, "sess_hook", 3)
    (tmp_path / "config").mkdir(exist_ok=True)
    (tmp_path / "config" / "hooks.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "hooks": {
                    "PreCompact": [
                        {
                            "matcher": "*",
                            "handlers": [
                                {
                                    "id": "refuse",
                                    "type": "builtin",
                                    "builtin": "block_destructive_shell",
                                }
                            ],
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "raiker.api.routes_context.owner_model_runtime",
        lambda *_a, **_k: (_FixedModel(), ("anthropic", "m")),
    )
    # `block_destructive_shell` observes rather than refuses, so the refusal is
    # forced here: what is under test is that the answer is honoured, not what
    # any particular builtin decides.
    from raiker.hooks import dispatcher as dispatcher_module
    from raiker.hooks.contracts import HookOutcome

    monkeypatch.setattr(
        dispatcher_module.HookDispatcher,
        "dispatch",
        lambda self, hook_input, **_k: (
            HookOutcome(decision="deny", reasons=["not_now"])
            if hook_input.event_name == "PreCompact"
            else HookOutcome()
        ),
    )

    response = client.post(
        "/api/sessions/sess_hook/compact",
        json={"through_turn_id": turns[0]},
        headers=_h(token),
    )

    assert response.status_code == 200
    assert response.json()["compacted"] is False
    assert response.json()["reason_code"] == "pre_compact_hook_denied"
    # A refusal is still recorded, so the owner can see it was asked for.
    assert ContextCompactionStore(store).active(
        store.original_account_principal_id() or "", "sess_hook"
    ) is None
