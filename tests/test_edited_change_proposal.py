"""BUG-271 — a reviewer could narrow a change and could not correct one.

Per-hunk accept and reject shipped as FIXED-369. *Edit then accept* — the
reviewer changing a line in the proposed diff and approving the result — did
not, and the reason is the distinction the whole approval boundary rests on:

* a **narrowing** is a subset of what was approved. `select_hunks` copies bytes
  out of the approved patch and copies nothing else in, so the immutable-intent
  hash still covers the whole approved change and what runs is provably inside
  it;
* an **edit** is a *different action*. Its bytes were never approved, so it
  cannot ride that hash. `ResolveApprovalRequest` sets ``extra="forbid"``
  precisely to stop an edited payload arriving on a decision.

So an edit is not a field on the decision. It is a **new proposal**: the
original resolves as denied with the replacement named, and the reviewer's own
patch gets its own preview, its own hash and its own approval. What these tests
pin is that the second half of that sentence is really true — that nothing the
owner typed can execute without an approval they gave after seeing it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.models import ToolAction
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.patch_selection import patch_target_paths

PROPOSED = (
    "--- a/poem.txt\n"
    "+++ b/poem.txt\n"
    "@@ -1,2 +1,2 @@\n"
    "-roses\n"
    "+roses are read\n"
    " violets\n"
)
CORRECTED = PROPOSED.replace("roses are read", "roses are red")


def _events(workspace: Path, session_id: str) -> list[dict[str, object]]:
    """The durable event log for one session, as written."""
    path = workspace / ".raiker" / "events" / f"{session_id}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


@pytest.fixture
def headers(workspace: Path) -> dict[str, str]:
    token, _session = ApiSessionStore(workspace).create_session("principal_owner")
    return {"Authorization": f"Bearer {token}"}


def _pending_patch(
    store: SQLiteStore,
    patch: str = PROPOSED,
    *,
    tool_name: str = "apply_patch",
    critical: bool = False,
) -> None:
    store.create_session("sess_a", "ws")
    store.insert_tool_action(
        ToolAction(
            action_id="act_1",
            tool_name=tool_name,
            arguments={"path": "poem.txt", "patch": patch},
            risk_level="medium",
            requires_approval=True,
            proposed_by="principal_owner",
        ),
        session_id="sess_a",
        turn_id=None,
        status="approval_required",
    )
    store.insert_approval("appr_1", "act_1", ttl_hours=24.0, critical=critical)


class TestTheTargetsOfAPatch:
    def test_the_plus_header_names_the_file(self) -> None:
        assert patch_target_paths(PROPOSED) == ["poem.txt"]

    def test_a_timestamped_git_style_header_still_reads(self) -> None:
        patch = "--- a/x.py\n+++ b/x.py\t2026-01-01 00:00:00\n@@ -1 +1 @@\n-a\n+b\n"
        assert patch_target_paths(patch) == ["x.py"]

    def test_text_that_is_not_a_diff_names_nothing(self) -> None:
        assert patch_target_paths("please change the poem") == []


class TestAnEditBecomesItsOwnProposal:
    def test_the_original_is_denied_and_the_edit_awaits_its_own_approval(
        self, client: TestClient, headers: dict[str, str], workspace: Path
    ) -> None:
        store = SQLiteStore(workspace)
        (workspace / "poem.txt").write_text("roses\nviolets\n", encoding="utf-8")
        _pending_patch(store)

        response = client.post(
            "/api/approvals/appr_1/replace",
            headers=headers,
            json={"patch": CORRECTED, "reason": "typo"},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "denied"
        assert body["executes_action"] is False
        replacement = body["replacement_approval_id"]
        assert replacement != "appr_1"

        # Nothing has run. The reviewer's own text is a proposal like any other.
        assert (workspace / "poem.txt").read_text(encoding="utf-8") == "roses\nviolets\n"
        assert store.load_approval("appr_1")["status"] == "denied"  # type: ignore[index]
        assert store.load_approval(replacement)["status"] == "pending"  # type: ignore[index]

    def test_the_replacement_carries_the_edited_bytes_and_its_own_hash(
        self, client: TestClient, headers: dict[str, str], workspace: Path
    ) -> None:
        store = SQLiteStore(workspace)
        _pending_patch(store)

        replacement = client.post(
            "/api/approvals/appr_1/replace",
            headers=headers,
            json={"patch": CORRECTED, "reason": ""},
        ).json()["replacement_approval_id"]

        original_row = store.load_approval("appr_1")
        new_row = store.load_approval(replacement)
        assert new_row is not None and original_row is not None
        assert "roses are red" in str(new_row["arguments_json"])
        assert new_row["action_id"] != original_row["action_id"]
        # Its own immutable intent, covering the bytes it will actually run.
        assert new_row["action_payload_sha256"] != original_row["action_payload_sha256"]
        assert new_row["action_payload_sha256"] == store.tool_action_payload_sha256(
            str(new_row["tool_name"]),
            str(new_row["arguments_json"]),
            str(new_row["risk_level"]),
        )

    def test_approving_the_replacement_applies_the_reviewers_own_text(
        self, client: TestClient, headers: dict[str, str], workspace: Path
    ) -> None:
        """The whole point: the bytes that ran are bytes a human read first."""
        store = SQLiteStore(workspace)
        (workspace / "poem.txt").write_text("roses\nviolets\n", encoding="utf-8")
        _pending_patch(store)

        replacement = client.post(
            "/api/approvals/appr_1/replace",
            headers=headers,
            json={"patch": CORRECTED, "reason": ""},
        ).json()["replacement_approval_id"]
        approved = client.post(
            f"/api/approvals/{replacement}/resolve",
            headers=headers,
            json={"approve": True, "reason": "my own version"},
        )

        assert approved.status_code == 200, approved.text
        text = (workspace / "poem.txt").read_text(encoding="utf-8")
        assert "roses are red" in text
        assert "roses are read" not in text

    def test_the_trail_says_replaced_rather_than_amended(
        self, client: TestClient, headers: dict[str, str], workspace: Path
    ) -> None:
        store = SQLiteStore(workspace)
        _pending_patch(store)

        replacement = client.post(
            "/api/approvals/appr_1/replace",
            headers=headers,
            json={"patch": CORRECTED, "reason": "typo"},
        ).json()["replacement_approval_id"]

        events = _events(workspace, "sess_a")
        types = [str(row.get("event_type")) for row in events]
        assert "approval_denied" in types
        assert "approval_replaced_by_edit" in types
        # The denial names what took its place, so a reader of the trail is not
        # left with a refusal and an unexplained second proposal.
        denial = next(row for row in events if row.get("event_type") == "approval_denied")
        assert replacement in json.dumps(denial)

    def test_the_event_carries_no_diff(
        self, client: TestClient, headers: dict[str, str], workspace: Path
    ) -> None:
        """The patch lives on its action row, redacted by the ordinary path."""
        store = SQLiteStore(workspace)
        _pending_patch(store)

        client.post(
            "/api/approvals/appr_1/replace",
            headers=headers,
            json={"patch": CORRECTED, "reason": ""},
        )

        event = next(
            row
            for row in _events(workspace, "sess_a")
            if row.get("event_type") == "approval_replaced_by_edit"
        )
        assert "roses" not in json.dumps(event)


class TestWhatItRefuses:
    def _replace(
        self, client: TestClient, headers: dict[str, str], patch: str
    ) -> tuple[int, str]:
        response = client.post(
            "/api/approvals/appr_1/replace",
            headers=headers,
            json={"patch": patch, "reason": ""},
        )
        return response.status_code, str(response.json().get("detail", {}).get("reason_code", ""))

    def test_an_empty_diff_is_not_a_change(
        self, client: TestClient, headers: dict[str, str], workspace: Path
    ) -> None:
        _pending_patch(SQLiteStore(workspace))
        assert self._replace(client, headers, "   ") == (400, "replacement_patch_empty")

    def test_text_that_is_not_a_diff_is_refused(
        self, client: TestClient, headers: dict[str, str], workspace: Path
    ) -> None:
        _pending_patch(SQLiteStore(workspace))
        assert self._replace(client, headers, "just fix the typo please") == (
            400,
            "replacement_patch_unreadable",
        )

    def test_the_same_patch_is_not_a_replacement(
        self, client: TestClient, headers: dict[str, str], workspace: Path
    ) -> None:
        """Denying and re-raising an identical proposal only churns the trail."""
        _pending_patch(SQLiteStore(workspace))
        assert self._replace(client, headers, PROPOSED) == (409, "replacement_unchanged")

    def test_it_cannot_reach_a_file_the_review_never_mentioned(
        self, client: TestClient, headers: dict[str, str], workspace: Path
    ) -> None:
        """A different change wearing a review's clothes is still a different change."""
        _pending_patch(SQLiteStore(workspace))
        widened = CORRECTED + (
            "--- a/.ssh/authorized_keys\n"
            "+++ b/.ssh/authorized_keys\n"
            "@@ -0,0 +1 @@\n"
            "+ssh-rsa AAAA\n"
        )
        status_code, reason = self._replace(client, headers, widened)
        assert (status_code, reason) == (400, "replacement_widens_targets")
        assert SQLiteStore(workspace).load_approval("appr_1")["status"] == "pending"  # type: ignore[index]

    def test_only_a_patch_can_be_edited_as_text(
        self, client: TestClient, headers: dict[str, str], workspace: Path
    ) -> None:
        store = SQLiteStore(workspace)
        store.create_session("sess_a", "ws")
        store.insert_tool_action(
            ToolAction(
                action_id="act_1",
                tool_name="write_file",
                arguments={"path": "poem.txt", "content": "roses"},
                risk_level="medium",
                requires_approval=True,
                proposed_by="principal_owner",
            ),
            session_id="sess_a",
            turn_id=None,
            status="approval_required",
        )
        store.insert_approval("appr_1", "act_1", ttl_hours=24.0)
        assert self._replace(client, headers, CORRECTED) == (409, "action_is_not_a_patch")

    def test_a_critical_action_keeps_its_step_up_lifecycle(
        self, client: TestClient, headers: dict[str, str], workspace: Path
    ) -> None:
        """Replacing one here would route it around the human-only floor."""
        _pending_patch(SQLiteStore(workspace), critical=True)
        assert self._replace(client, headers, CORRECTED) == (
            400,
            "critical_approval_requires_lifecycle",
        )

    def test_an_already_decided_change_cannot_be_replaced(
        self, client: TestClient, headers: dict[str, str], workspace: Path
    ) -> None:
        store = SQLiteStore(workspace)
        _pending_patch(store)
        client.post(
            "/api/approvals/appr_1/resolve",
            headers=headers,
            json={"approve": False, "reason": "no"},
        )
        assert self._replace(client, headers, CORRECTED) == (409, "approval_already_resolved")

    def test_an_unknown_approval_is_a_404(
        self, client: TestClient, headers: dict[str, str]
    ) -> None:
        response = client.post(
            "/api/approvals/appr_missing/replace",
            headers=headers,
            json={"patch": CORRECTED, "reason": ""},
        )
        assert response.status_code == 404

    def test_it_needs_authentication(self, client: TestClient) -> None:
        response = client.post(
            "/api/approvals/appr_1/replace", json={"patch": CORRECTED, "reason": ""}
        )
        assert response.status_code == 401


class TestTheDecisionStillForbidsAnEditedPayload:
    def test_resolve_refuses_an_unknown_field(
        self, client: TestClient, headers: dict[str, str], workspace: Path
    ) -> None:
        """`extra="forbid"` is why the edit needed its own route in the first place."""
        _pending_patch(SQLiteStore(workspace))
        response = client.post(
            "/api/approvals/appr_1/resolve",
            headers=headers,
            json={"approve": True, "reason": "", "patch": CORRECTED},
        )
        assert response.status_code == 422
