"""GAP-BUILD B14 — accepting part of a proposed change.

An approval governed the whole change set: Accept applied every hunk, Reject
applied none. A reviewer who wanted two of five hunks had to reject everything
and ask again — the one interaction a coding agent's review surface exists to
support, and the reason B14's remainder stayed open.

The property these tests defend is not "a subset can be applied". It is that a
**selection narrows and never edits**:

* ids are positions in the approved diff, never content, so there is nothing in
  one for a caller to smuggle a change through;
* an id naming no hunk in the approved patch refuses the whole decision rather
  than being ignored, because ignoring it would apply a change the owner did not
  press Accept on;
* the immutable-intent hash the relay checks still covers the entire approved
  change set, so the narrowing cannot be used to get around it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id
from raiker.contracts.models import ToolAction
from raiker.runtime.authority.models import Principal, RiskLevelValue
from raiker.runtime.authority.router import GovernedAction
from raiker.runtime.executors.tier1_approval import ApprovalExecutionRelay
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.patch_selection import hunk_ids, select_hunks, unknown_hunk_ids

TWO_FILES = (
    "--- a/poem.txt\n"
    "+++ b/poem.txt\n"
    "@@ -1,2 +1,2 @@\n"
    "-roses\n"
    "+roses are red\n"
    " violets\n"
    "@@ -5,2 +5,2 @@\n"
    "-sugar\n"
    "+sugar is sweet\n"
    " and\n"
    "--- a/note.txt\n"
    "+++ b/note.txt\n"
    "@@ -1 +1 @@\n"
    "-draft\n"
    "+final\n"
)


class TestSelectingHunks:
    def test_every_hunk_has_a_position_and_positions_are_all_there_is(self) -> None:
        """An id carries no content, which is why it cannot carry an edit."""
        assert hunk_ids(TWO_FILES) == ["0:0", "0:1", "1:0"]

    def test_keeping_one_hunk_drops_the_others_and_nothing_else(self) -> None:
        kept = select_hunks(TWO_FILES, ["0:1"])
        assert "sugar is sweet" in kept
        assert "roses are red" not in kept
        # A file whose hunks were all declined is not opened, not rewritten, and
        # not recorded as changed.
        assert "note.txt" not in kept
        assert kept.startswith("--- a/poem.txt\n+++ b/poem.txt\n")

    def test_a_selection_can_only_remove(self) -> None:
        """Every line of the result came out of the patch it was given."""
        approved = set(TWO_FILES.splitlines())
        for line in select_hunks(TWO_FILES, ["0:0", "1:0"]).splitlines():
            assert line in approved

    def test_selecting_everything_is_the_same_patch(self) -> None:
        assert select_hunks(TWO_FILES, hunk_ids(TWO_FILES)) == TWO_FILES

    def test_selecting_nothing_yields_nothing(self) -> None:
        assert select_hunks(TWO_FILES, []) == ""

    def test_an_id_that_names_no_hunk_is_reported(self) -> None:
        assert unknown_hunk_ids(TWO_FILES, ["0:0", "3:9"]) == ["3:9"]


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


def _human(store: SQLiteStore) -> Principal:
    raw = store.get_principal("principal_owner")
    assert raw is not None
    return Principal(**raw)


def _pending_patch(store: SQLiteStore, patch: str) -> None:
    store.create_session("sess_a", "ws")
    store.insert_tool_action(
        ToolAction(
            action_id="act_1",
            tool_name="apply_patch",
            arguments={"path": "poem.txt", "patch": patch},
            risk_level="low",
            requires_approval=True,
            proposed_by="principal_owner",
        ),
        session_id="sess_a",
        turn_id=None,
        status="approval_required",
    )
    store.insert_approval("appr_1", "act_1", ttl_hours=24.0)


def _relay_action() -> GovernedAction:
    return GovernedAction(
        action_id=new_id("act_"),
        principal_id="principal_owner",
        action_type="approval_execution_relay",
        tool_or_service_name="approval_execution_relay",
        arguments={"approval_id": "appr_1"},
        risk_level=RiskLevelValue.LOW,
    )


ONE_FILE = (
    "--- a/poem.txt\n"
    "+++ b/poem.txt\n"
    "@@ -1,2 +1,2 @@\n"
    "-roses\n"
    "+roses are red\n"
    " violets\n"
    "@@ -3,2 +3,2 @@\n"
    "-sugar\n"
    "+sugar is sweet\n"
    " and\n"
)


class TestTheRelayHonoursTheDecision:
    def test_only_the_accepted_hunk_reaches_the_file(self, tmp_path: Path) -> None:
        ws = _ws(tmp_path)
        store = SQLiteStore(ws)
        (ws / "poem.txt").write_text("roses\nviolets\nsugar\nand\n", encoding="utf-8")
        _pending_patch(store, ONE_FILE)
        store.save_approval_decision_scope("appr_1", ["0:1"])

        result = ApprovalExecutionRelay(ws, store).execute(_relay_action(), _human(store))

        assert result.ok is True, result.reason_code
        text = (ws / "poem.txt").read_text(encoding="utf-8")
        assert "sugar is sweet" in text
        assert "roses are red" not in text

    def test_no_recorded_selection_still_applies_the_whole_change(
        self, tmp_path: Path
    ) -> None:
        """What every approval meant before B14, and what most still mean."""
        ws = _ws(tmp_path)
        store = SQLiteStore(ws)
        (ws / "poem.txt").write_text("roses\nviolets\nsugar\nand\n", encoding="utf-8")
        _pending_patch(store, ONE_FILE)

        result = ApprovalExecutionRelay(ws, store).execute(_relay_action(), _human(store))

        assert result.ok is True, result.reason_code
        text = (ws / "poem.txt").read_text(encoding="utf-8")
        assert "roses are red" in text
        assert "sugar is sweet" in text

    def test_a_selection_naming_an_unknown_hunk_refuses_the_execution(
        self, tmp_path: Path
    ) -> None:
        """Ignoring it would apply a different change from the one accepted."""
        ws = _ws(tmp_path)
        store = SQLiteStore(ws)
        (ws / "poem.txt").write_text("roses\nviolets\nsugar\nand\n", encoding="utf-8")
        _pending_patch(store, ONE_FILE)
        store.save_approval_decision_scope("appr_1", ["0:0", "7:7"])

        result = ApprovalExecutionRelay(ws, store).execute(_relay_action(), _human(store))

        assert result.ok is False
        assert result.reason_code == "unknown_hunk_selection"
        assert (ws / "poem.txt").read_text(encoding="utf-8") == "roses\nviolets\nsugar\nand\n"

    def test_accepting_no_part_of_a_change_is_not_an_apply(self, tmp_path: Path) -> None:
        ws = _ws(tmp_path)
        store = SQLiteStore(ws)
        (ws / "poem.txt").write_text("roses\nviolets\nsugar\nand\n", encoding="utf-8")
        _pending_patch(store, ONE_FILE)
        store.save_approval_decision_scope("appr_1", [])

        result = ApprovalExecutionRelay(ws, store).execute(_relay_action(), _human(store))

        assert result.ok is False
        assert result.reason_code == "no_hunk_accepted"
        assert (ws / "poem.txt").read_text(encoding="utf-8") == "roses\nviolets\nsugar\nand\n"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return _ws(tmp_path)


@pytest.fixture
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


@pytest.fixture
def headers(workspace: Path) -> dict[str, str]:
    token, _session = ApiSessionStore(workspace).create_session("principal_owner")
    return {"Authorization": f"Bearer {token}"}


class TestTheRoute:
    def test_a_selection_is_recorded_and_applied(
        self, client: TestClient, headers: dict[str, str], workspace: Path
    ) -> None:
        store = SQLiteStore(workspace)
        (workspace / "poem.txt").write_text("roses\nviolets\nsugar\nand\n", encoding="utf-8")
        _pending_patch(store, ONE_FILE)

        response = client.post(
            "/api/approvals/appr_1/resolve",
            headers=headers,
            json={"approve": True, "reason": "keep the second", "accepted_hunks": ["0:1"]},
        )

        assert response.status_code == 200, response.text
        text = (workspace / "poem.txt").read_text(encoding="utf-8")
        assert "sugar is sweet" in text
        assert "roses are red" not in text

    def test_an_unknown_hunk_is_refused_before_anything_runs(
        self, client: TestClient, headers: dict[str, str], workspace: Path
    ) -> None:
        store = SQLiteStore(workspace)
        (workspace / "poem.txt").write_text("roses\nviolets\nsugar\nand\n", encoding="utf-8")
        _pending_patch(store, ONE_FILE)

        response = client.post(
            "/api/approvals/appr_1/resolve",
            headers=headers,
            json={"approve": True, "reason": "", "accepted_hunks": ["9:9"]},
        )

        assert response.status_code == 400
        assert response.json()["detail"]["reason_code"] == "unknown_hunk_selection"
        assert (workspace / "poem.txt").read_text(encoding="utf-8") == (
            "roses\nviolets\nsugar\nand\n"
        )
        assert store.load_approval("appr_1")["status"] == "pending"  # type: ignore[index]

    def test_a_selection_cannot_accompany_a_rejection(
        self, client: TestClient, headers: dict[str, str], workspace: Path
    ) -> None:
        """Rejecting is not accepting a smaller part of it; the two are separate."""
        _pending_patch(SQLiteStore(workspace), ONE_FILE)

        response = client.post(
            "/api/approvals/appr_1/resolve",
            headers=headers,
            json={"approve": False, "reason": "", "accepted_hunks": ["0:0"]},
        )

        assert response.status_code == 400
        assert response.json()["detail"]["reason_code"] == "hunk_selection_requires_approval"

    def test_a_selection_on_an_action_with_no_hunks_is_refused(
        self, client: TestClient, headers: dict[str, str], workspace: Path
    ) -> None:
        """Offering a per-hunk control where there are no hunks would be a lie."""
        store = SQLiteStore(workspace)
        store.create_session("sess_a", "ws")
        store.insert_tool_action(
            ToolAction(
                action_id="act_1",
                tool_name="memory_write",
                arguments={"text": "note", "scope": "project"},
                risk_level="low",
                requires_approval=True,
                proposed_by="principal_owner",
            ),
            session_id="sess_a",
            turn_id=None,
            status="approval_required",
        )
        store.insert_approval("appr_1", "act_1", ttl_hours=24.0)

        response = client.post(
            "/api/approvals/appr_1/resolve",
            headers=headers,
            json={"approve": True, "reason": "", "accepted_hunks": ["0:0"]},
        )

        assert response.status_code == 409
        assert response.json()["detail"]["reason_code"] == "action_has_no_hunks"

    def test_the_whole_change_is_still_the_default(
        self, client: TestClient, headers: dict[str, str], workspace: Path
    ) -> None:
        (workspace / "poem.txt").write_text("roses\nviolets\nsugar\nand\n", encoding="utf-8")
        _pending_patch(SQLiteStore(workspace), ONE_FILE)

        response = client.post(
            "/api/approvals/appr_1/resolve",
            headers=headers,
            json={"approve": True, "reason": "all of it"},
        )

        assert response.status_code == 200, response.text
        text = (workspace / "poem.txt").read_text(encoding="utf-8")
        assert "roses are red" in text
        assert "sugar is sweet" in text
