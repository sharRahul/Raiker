"""A structured question to the owner, mid-turn (ADD-22).

Raiker's only mid-turn interruption was an approval, which asks *may I do this*.
A turn facing two readings of an instruction had no way to ask *which of these
did you mean*, so it picked one and the owner found out afterwards.

The thing that makes this safe to build is not the question — it is that a
question and an approval can never be mistaken for each other. That claim has
three halves, and each is tested here:

* the **band** is honest: a question grants nothing, so it is `low`, and it says
  so on the queue the owner reads. Before the risk model had definitions this was
  impossible: everything that parked was labelled `high`, and a queue where
  "high risk" sometimes means "which database did you mean" is a queue people
  learn to click through.
* the **routes** refuse each other's kind: a question cannot be approved and an
  approval cannot be answered.
* the **answer** is bounded by what was asked. Only a question the model asked
  and an option it offered can come back, because the answer is handed straight
  to the model in a field it already trusts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.contracts.ids import new_id
from raiker.contracts.models import OWNER_QUESTION_TOOL, ToolAction
from raiker.models.contracts import ToolCallProposal
from raiker.models.tool_call_validation import ToolCallRejected, validate_tool_call
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.runtime.turn_suspension import approval_outcome, owner_answer_outcome
from raiker.storage.sqlite import SQLiteStore

QUESTIONS: list[dict[str, Any]] = [
    {
        "question": "Which database should the new service use?",
        "header": "Database",
        "options": [
            {"label": "Postgres", "description": "Relational, what the other services use"},
            {"label": "SQLite", "description": "Embedded, no server to run"},
        ],
    }
]


def _proposal(questions: list[dict[str, Any]] | None = None) -> ToolCallProposal:
    return ToolCallProposal(
        call_id="call_ask",
        tool_name=OWNER_QUESTION_TOOL,
        arguments={"questions": questions if questions is not None else QUESTIONS},
    )


# ── The band is honest ───────────────────────────────────────────────────────


def test_a_question_is_low_risk_because_it_grants_nothing() -> None:
    action = validate_tool_call(_proposal())
    assert action.risk_level == "low"
    assert action.requires_approval is True


def test_it_parks_the_turn_without_claiming_to_be_dangerous(tmp_path: Path) -> None:
    """The prerequisite, proved.

    `PolicyEngine` used to assert `high` for everything in
    `approval_required_actions`. A question parks through that same branch, so
    had it still asserted, this surface would have reached the owner labelled a
    high-risk approval — worse than not shipping it.
    """
    engine = PolicyEngine(StaticPolicyConfig(tmp_path))
    decision = engine.review(validate_tool_call(_proposal()))

    assert decision.decision == "needs_approval"
    assert decision.risk_level == "low"


# ── The shape is checked before an owner ever sees it ────────────────────────


@pytest.mark.parametrize(
    ("questions", "reason"),
    [
        ([], "questions_missing"),
        ([{**QUESTIONS[0], "header": "far too long a header"}], "question_header_too_long"),
        ([{**QUESTIONS[0], "options": QUESTIONS[0]["options"][:1]}], "question_option_count"),
        (
            [{**QUESTIONS[0], "options": [{"label": "A", "description": "x"}] * 2}],
            "duplicate_option",
        ),
        ([QUESTIONS[0], QUESTIONS[0]], "duplicate_question"),
        ([{**QUESTIONS[0], "multiSelect": "yes"}], "question_multiselect_not_bool"),
    ],
)
def test_a_malformed_question_never_reaches_the_owner(
    questions: list[dict[str, Any]], reason: str
) -> None:
    """All of it is model-authored text a person is about to act on."""
    with pytest.raises(ToolCallRejected) as excinfo:
        validate_tool_call(_proposal(questions))
    assert excinfo.value.reason == reason


def test_five_questions_are_refused_like_the_reference_bounds() -> None:
    with pytest.raises(ToolCallRejected) as excinfo:
        validate_tool_call(
            _proposal([{**QUESTIONS[0], "question": f"Q{index}?"} for index in range(5)])
        )
    assert excinfo.value.reason == "too_many_questions"


# ── An answer is not a permission ────────────────────────────────────────────


def test_the_outcome_handed_back_is_shaped_nothing_like_an_approval() -> None:
    answered = owner_answer_outcome(answers={"Which database?": "Postgres"})
    approved = approval_outcome(approved=True, executed=True, capability="file_write_execution")

    assert answered["status"] == "answered"
    assert answered["executed"] is False
    # The distinction the model has to be able to make. An answer that read as a
    # permission would turn "Postgres" into consent for whatever was proposed.
    assert "permission" in answered["note"]
    assert approved["status"] == "success"
    assert answered["status"] != approved["status"]


def test_free_text_is_carried_verbatim_and_says_so() -> None:
    answered = owner_answer_outcome(answers={}, response="Neither — use the existing one.")
    assert answered["response"] == "Neither — use the existing one."
    assert "own words" in answered["note"]


# ── The routes refuse each other's kind ──────────────────────────────────────


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.delenv("RAIKER_CONNECTOR_VAULT_KEY", raising=False)
    return TestClient(create_app(tmp_path))


def _token(client: TestClient) -> str:
    return client.post(
        "/api/auth/register", json={"username": "owner", "password": "right-pass-123"}
    ).json()["token"]


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _parked(store: SQLiteStore, tool_name: str, arguments: dict[str, Any]) -> str:
    """A pending approval row for *tool_name*, as the broker would have written one."""
    session_id = f"sess_{tool_name}"
    store.create_session(
        session_id,
        str(store.paths.workspace_root),
        user_id=store.principal_user_id(store.original_account_principal_id() or ""),
    )
    store.insert_turn(session_id, f"turn_{tool_name}", "do the thing")
    action = ToolAction(
        action_id=new_id("act_"),
        tool_name=tool_name,
        arguments=arguments,
        risk_level="low" if tool_name == OWNER_QUESTION_TOOL else "medium",
        requires_approval=True,
    )
    store.insert_tool_action(action, session_id, f"turn_{tool_name}", "approval_required")
    approval_id = new_id("appr_")
    store.insert_approval(approval_id, action)
    return approval_id


def test_a_question_cannot_be_approved(client: TestClient, tmp_path: Path) -> None:
    token = _token(client)
    store = SQLiteStore(tmp_path)
    approval_id = _parked(store, OWNER_QUESTION_TOOL, {"questions": QUESTIONS})

    response = client.post(
        f"/api/approvals/{approval_id}/resolve", json={"approve": True, "reason": "looks fine"}, headers=_h(token)
    )

    assert response.status_code == 409
    assert response.json()["detail"]["reason_code"] == "approval_is_a_question"


def test_an_approval_cannot_be_answered(client: TestClient, tmp_path: Path) -> None:
    token = _token(client)
    store = SQLiteStore(tmp_path)
    approval_id = _parked(store, "write_file", {"path": "report.md", "text": "hi"})

    response = client.post(
        f"/api/approvals/{approval_id}/answer",
        json={"answers": {"anything": "at all"}},
        headers=_h(token),
    )

    assert response.status_code == 409
    assert response.json()["detail"]["reason_code"] == "approval_is_not_a_question"


# ── The answer is bounded by what was asked ──────────────────────────────────


def test_the_owner_answers_and_the_answer_is_recorded(
    client: TestClient, tmp_path: Path
) -> None:
    token = _token(client)
    store = SQLiteStore(tmp_path)
    approval_id = _parked(store, OWNER_QUESTION_TOOL, {"questions": QUESTIONS})

    response = client.post(
        f"/api/approvals/{approval_id}/answer",
        json={"answers": {QUESTIONS[0]["question"]: "Postgres"}},
        headers=_h(token),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "answered"
    row = store.load_approval(approval_id)
    assert row is not None
    # `answered`, not `approved`: nothing was permitted, and a status saying it
    # was would make the audit trail describe a grant nobody gave.
    assert row["status"] == "answered"
    assert json.loads(str(row["answer_json"]))["answers"] == {QUESTIONS[0]["question"]: "Postgres"}


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        ({"answers": {"A question nobody asked": "Postgres"}}, "unknown_question"),
        ({"answers": {QUESTIONS[0]["question"]: "MongoDB"}}, "unknown_option"),
        ({"answers": {}}, "no_answer_given"),
        (
            {"answers": {QUESTIONS[0]["question"]: ["Postgres", "SQLite"]}},
            "single_select_question",
        ),
    ],
)
def test_only_what_was_asked_and_offered_comes_back(
    client: TestClient, tmp_path: Path, payload: dict[str, Any], reason: str
) -> None:
    """The answer is handed to the model in a field it already trusts.

    A label nobody offered would be a way to put chosen text into the model's
    next turn through the answer channel. An owner who wants to say something
    else uses `response`, which is carried as their own words and labelled that
    way.
    """
    token = _token(client)
    store = SQLiteStore(tmp_path)
    approval_id = _parked(store, OWNER_QUESTION_TOOL, {"questions": QUESTIONS})

    response = client.post(
        f"/api/approvals/{approval_id}/answer", json=payload, headers=_h(token)
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reason_code"] == reason


def test_the_owner_can_answer_in_their_own_words(client: TestClient, tmp_path: Path) -> None:
    token = _token(client)
    store = SQLiteStore(tmp_path)
    approval_id = _parked(store, OWNER_QUESTION_TOOL, {"questions": QUESTIONS})

    response = client.post(
        f"/api/approvals/{approval_id}/answer",
        json={"response": "Neither. Reuse the one the billing service has."},
        headers=_h(token),
    )

    assert response.status_code == 200
    stored = json.loads(str(store.load_approval(approval_id)["answer_json"]))  # type: ignore[index]
    assert stored["response"].startswith("Neither.")


def test_a_question_is_answered_once(client: TestClient, tmp_path: Path) -> None:
    """The first answer is the one the turn resumed on."""
    token = _token(client)
    store = SQLiteStore(tmp_path)
    approval_id = _parked(store, OWNER_QUESTION_TOOL, {"questions": QUESTIONS})
    body = {"answers": {QUESTIONS[0]["question"]: "SQLite"}}

    assert client.post(
        f"/api/approvals/{approval_id}/answer", json=body, headers=_h(token)
    ).status_code == 200
    second = client.post(f"/api/approvals/{approval_id}/answer", json=body, headers=_h(token))

    assert second.status_code == 409
    assert second.json()["detail"]["reason_code"] == "question_already_answered"


def test_answering_requires_auth(client: TestClient) -> None:
    assert client.post("/api/approvals/appr_x/answer", json={"answers": {}}).status_code == 401


def test_the_audit_row_records_that_it_was_answered_and_not_the_answer(
    client: TestClient, tmp_path: Path
) -> None:
    """The answer goes to the model. The log keeps that one was given."""
    from raiker.events.writer import EventLogWriter

    token = _token(client)
    store = SQLiteStore(tmp_path)
    approval_id = _parked(store, OWNER_QUESTION_TOOL, {"questions": QUESTIONS})
    client.post(
        f"/api/approvals/{approval_id}/answer",
        json={"answers": {QUESTIONS[0]["question"]: "Postgres"}},
        headers=_h(token),
    )

    path = EventLogWriter(store).path_for_session(f"sess_{OWNER_QUESTION_TOOL}")
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    answered = [r for r in records if r["event_type"] == "owner_question_answered"]

    assert len(answered) == 1
    assert answered[0]["payload"]["answered_count"] == 1
    assert "Postgres" not in json.dumps(answered[0])
