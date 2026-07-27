"""BUG-06 — approving a file mutation actually writes the file.

Before this change, every approval resolution was metadata-only: the Approvals
inbox recorded a decision and `raiker/tools/broker.py` reported *"Approval
resolution is metadata-only and does not execute the action"*, so nothing in the
app could produce a file. These tests cover the wiring that closes that loop —
`raiker/approvals/execution.py` handing an approved, non-critical, pending
approval to `ApprovalExecutionRelay` through `RuntimeAuthority.route_action` —
and, just as importantly, its boundaries: which capabilities are relayed, which
gates return resolution to metadata-only, and what a write may never touch.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.routes_prompts import _record_generated_file_attachments_for_turn
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.models import ToolAction
from raiker.runtime.attachment_preview import AttachmentPreviewService
from raiker.storage.sqlite import SQLiteStore


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
    raw, _ = ApiSessionStore(workspace).create_session("principal_owner")
    return {"Authorization": f"Bearer {raw}"}


def _pending(
    workspace: Path,
    *,
    tool_name: str = "write_file",
    arguments: dict[str, object] | None = None,
    approval_id: str = "appr_1",
    action_id: str = "act_1",
) -> str:
    """Insert a pending approval exactly as the broker parks one."""
    store = SQLiteStore(workspace)
    store.create_session("sess_a", str(workspace))
    action = ToolAction(
        action_id=action_id,
        tool_name=tool_name,
        arguments=arguments if arguments is not None else {"path": "notes.md", "text": "hello\n"},
        risk_level="high",
        requires_approval=True,
    )
    store.insert_tool_action(
        action, session_id="sess_a", turn_id="turn_a", status="approval_required"
    )
    store.insert_approval(approval_id, action)
    return approval_id


def _disable_gate(client: TestClient, headers: dict[str, str], capability: str) -> None:
    """Turn a capability gate off the way the owner does — through the governed API."""
    resp = client.post(
        f"/api/capability-gates/{capability}/disable",
        json={"reason": "owner turned this off"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text


def _resolve(
    client: TestClient, headers: dict[str, str], approval_id: str, *, approve: bool = True
) -> Any:
    return client.post(
        f"/api/approvals/{approval_id}/resolve",
        json={"approve": approve, "reason": "test decision"},
        headers=headers,
    )


class TestApprovedWriteExecutes:
    def test_write_file_is_written_to_the_workspace(
        self, workspace: Path, client: TestClient, headers: dict[str, str]
    ) -> None:
        _pending(workspace, arguments={"path": "docs/report.md", "text": "# Q3\n"})
        resp = _resolve(client, headers, "appr_1")

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["executes_action"] is True
        assert body["status"] == "executed"
        assert body["execution"] == {
            "capability": "file_write_execution",
            "path": "docs/report.md",
        }
        assert (workspace / "docs" / "report.md").read_text(encoding="utf-8") == "# Q3\n"
        assert SQLiteStore(workspace).load_approval("appr_1")["status"] == "executed"  # type: ignore[index]

    def test_new_file_is_copied_into_the_session_after_approval(
        self, workspace: Path, client: TestClient, headers: dict[str, str]
    ) -> None:
        _pending(workspace, arguments={"path": "docs/report.md", "text": "# Q3\n"})

        assert _resolve(client, headers, "appr_1").status_code == 200

        files = AttachmentPreviewService(SQLiteStore(workspace)).list_session_files(
            "sess_a", "principal_owner"
        )
        assert len(files) == 1
        assert files[0]["turn_id"] == "turn_a"
        assert files[0]["filename"] == "report.md"
        assert files[0]["media_type"] == "text/markdown"

        # The final stream event may reach the recorder after an approved
        # write. Re-running it must retain the same session file, not add a
        # duplicate chip for the same generated artifact.
        _record_generated_file_attachments_for_turn(
            workspace,
            session_id="sess_a",
            turn_id="turn_a",
            principal_id="principal_owner",
        )
        assert len(
            AttachmentPreviewService(SQLiteStore(workspace)).list_session_files(
                "sess_a", "principal_owner"
            )
        ) == 1

    def test_apply_patch_is_relayed_through_its_own_capability(
        self, workspace: Path, client: TestClient, headers: dict[str, str]
    ) -> None:
        (workspace / "src.txt").write_text("old\n", encoding="utf-8")
        _pending(
            workspace,
            tool_name="apply_patch",
            arguments={
                "path": "src.txt",
                "patch": "--- a/src.txt\n+++ b/src.txt\n@@ -1 +1 @@\n-old\n+new\n",
            },
        )
        resp = _resolve(client, headers, "appr_1")

        assert resp.status_code == 200, resp.text
        assert resp.json()["execution"]["capability"] == "patch_apply_execution"
        assert (workspace / "src.txt").read_text(encoding="utf-8") == "new\n"

    def test_edit_file_replaces_only_the_approved_unique_text(
        self, workspace: Path, client: TestClient, headers: dict[str, str]
    ) -> None:
        (workspace / "src.txt").write_text("before\nold\nafter\n", encoding="utf-8")
        _pending(
            workspace,
            tool_name="edit_file",
            arguments={"path": "src.txt", "old_text": "old\n", "new_text": "new\n"},
        )

        resp = _resolve(client, headers, "appr_1")

        assert resp.status_code == 200, resp.text
        assert resp.json()["execution"]["capability"] == "file_write_execution"
        assert (workspace / "src.txt").read_text(encoding="utf-8") == "before\nnew\nafter\n"

    def test_the_previous_contents_are_checkpointed_before_the_overwrite(
        self, workspace: Path, client: TestClient, headers: dict[str, str]
    ) -> None:
        # A real execution has to stay reversible: the router captures a
        # pre-image before the executor runs. Without it, "Approve" would be a
        # one-way door.
        (workspace / "notes.md").write_text("original\n", encoding="utf-8")
        _pending(workspace, arguments={"path": "notes.md", "text": "replaced\n"})

        assert _resolve(client, headers, "appr_1").status_code == 200
        assert (workspace / "notes.md").read_text(encoding="utf-8") == "replaced\n"

        store = SQLiteStore(workspace)
        types = {e["event_type"] for e in store.list_event_index(limit=500)}
        assert "checkpoint_captured" in types

    def test_the_audit_trail_records_both_the_decision_and_the_execution(
        self, workspace: Path, client: TestClient, headers: dict[str, str]
    ) -> None:
        _pending(workspace)
        assert _resolve(client, headers, "appr_1").status_code == 200

        store = SQLiteStore(workspace)
        types = {e["event_type"] for e in store.list_event_index(limit=500)}
        # The human decision, the relay's execution record, and the executor's
        # own outcome are each durable and separately attributable.
        assert {"approval_received", "approval_executed", "action_executed"} <= types

    def test_denying_writes_nothing(
        self, workspace: Path, client: TestClient, headers: dict[str, str]
    ) -> None:
        _pending(workspace)
        resp = _resolve(client, headers, "appr_1", approve=False)

        assert resp.status_code == 200
        assert resp.json()["status"] == "denied"
        assert resp.json()["executes_action"] is False
        assert not (workspace / "notes.md").exists()


class TestOwnerGatesStillWin:
    def test_disabling_the_relay_returns_resolution_to_metadata_only(
        self, workspace: Path, client: TestClient, headers: dict[str, str]
    ) -> None:
        _disable_gate(client, headers, "approval_execution_relay")
        _pending(workspace)

        detail = client.get("/api/approvals/appr_1", headers=headers).json()
        assert detail["executes_on_approval"] is False
        assert "NOT execute" in detail["metadata_only_notice"]

        resp = _resolve(client, headers, "appr_1")
        assert resp.status_code == 200
        assert resp.json()["executes_action"] is False
        assert resp.json()["status"] == "approved"
        assert not (workspace / "notes.md").exists()

    def test_disabling_the_target_capability_returns_resolution_to_metadata_only(
        self, workspace: Path, client: TestClient, headers: dict[str, str]
    ) -> None:
        _disable_gate(client, headers, "file_write_execution")
        _pending(workspace)

        detail = client.get("/api/approvals/appr_1", headers=headers).json()
        assert detail["executes_on_approval"] is False

        resp = _resolve(client, headers, "appr_1")
        assert resp.status_code == 200
        assert resp.json()["executes_action"] is False
        assert not (workspace / "notes.md").exists()

    def test_a_critical_approval_is_never_relayed_by_the_ordinary_inbox(
        self, workspace: Path, client: TestClient, headers: dict[str, str]
    ) -> None:
        _pending(workspace)
        store = SQLiteStore(workspace)
        with store.connect() as connection:
            connection.execute("UPDATE approvals SET critical = 1 WHERE approval_id = ?", ("appr_1",))

        detail = client.get("/api/approvals/appr_1", headers=headers).json()
        assert detail["executes_on_approval"] is False

        resp = _resolve(client, headers, "appr_1")
        assert resp.status_code == 400
        assert resp.json()["detail"]["reason_code"] == "critical_approval_requires_lifecycle"
        assert not (workspace / "notes.md").exists()


class TestImmutableIntentStillHolds:
    def test_a_payload_that_drifted_since_approval_is_refused(
        self, workspace: Path, client: TestClient, headers: dict[str, str]
    ) -> None:
        _pending(workspace)
        store = SQLiteStore(workspace)
        with store.connect() as connection:
            connection.execute(
                "UPDATE tool_actions SET arguments_json = ? WHERE action_id = ?",
                ('{"path": "evil.txt", "text": "pwned"}', "act_1"),
            )

        resp = _resolve(client, headers, "appr_1")
        assert resp.status_code == 409
        assert resp.json()["detail"]["reason_code"] == "approval_payload_tampered"
        assert not (workspace / "evil.txt").exists()
        assert not (workspace / "notes.md").exists()

    def test_an_expired_approval_never_executes(
        self, workspace: Path, client: TestClient, headers: dict[str, str]
    ) -> None:
        _pending(workspace)
        store = SQLiteStore(workspace)
        with store.connect() as connection:
            connection.execute(
                "UPDATE approvals SET expires_at = ? WHERE approval_id = ?",
                ("2000-01-01T00:00:00Z", "appr_1"),
            )

        resp = _resolve(client, headers, "appr_1")
        assert resp.status_code == 409
        assert resp.json()["detail"]["reason_code"] == "approval_expired"
        assert not (workspace / "notes.md").exists()
        assert store.load_approval("appr_1")["status"] == "expired"  # type: ignore[index]


class TestWriteBoundaries:
    @pytest.mark.parametrize(
        "path",
        [".raiker/hooks.json", ".raiker/vault.key", ".git/hooks/pre-commit", ".raiker"],
    )
    def test_protected_workspace_directories_are_refused(
        self, workspace: Path, client: TestClient, headers: dict[str, str], path: str
    ) -> None:
        _pending(workspace, arguments={"path": path, "text": "owned"})
        resp = _resolve(client, headers, "appr_1")

        assert resp.status_code == 409
        assert "protected_workspace_path" in resp.json()["detail"]["reason_code"]
        assert not (workspace / path).is_file()

    def test_a_path_outside_the_workspace_is_refused(
        self, workspace: Path, client: TestClient, headers: dict[str, str], tmp_path: Path
    ) -> None:
        escape = tmp_path / "escaped.txt"
        _pending(workspace, arguments={"path": "../escaped.txt", "text": "owned"})
        resp = _resolve(client, headers, "appr_1")

        assert resp.status_code == 409
        assert "outside_workspace" in resp.json()["detail"]["reason_code"]
        assert not escape.exists()

    def test_a_refused_write_leaves_the_approval_terminal_not_replayable(
        self, workspace: Path, client: TestClient, headers: dict[str, str]
    ) -> None:
        # The executor ran and failed, so the approval must not fall back to
        # pending — a failed execution can never be silently re-run.
        _pending(workspace, arguments={"path": ".raiker/hooks.json", "text": "owned"})
        assert _resolve(client, headers, "appr_1").status_code == 409
        assert (
            SQLiteStore(workspace).load_approval("appr_1")["status"]  # type: ignore[index]
            == "execution_failed"
        )
