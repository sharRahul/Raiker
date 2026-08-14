from __future__ import annotations

import json
from pathlib import Path

import pytest

from raiker.api.sessions import ApiSessionStore
from raiker.cli.commands import handle_slash_command
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.models import ToolAction
from raiker.control.dashboard import DashboardService
from raiker.execution.commands.store import CommandStore
from raiker.storage.sqlite import SQLiteStore


def _pending_shell(workspace: Path, approval_id: str = "appr_terminal") -> None:
    store = SQLiteStore(workspace)
    store.create_session("sess_terminal", str(workspace))
    action = ToolAction(
        action_id="act_terminal",
        tool_name="shell",
        # RAIKER-2023: `python -c` is an interpreter escape and is refused, so
        # the terminal relay is exercised with a command that is not one.
        arguments={"command": ["echo", "terminal relay"]},
        risk_level="high",
        requires_approval=True,
    )
    store.insert_tool_action(
        action,
        session_id="sess_terminal",
        turn_id="turn_terminal",
        status="approval_required",
    )
    store.insert_approval(approval_id, action)


def _workspace(tmp_path: Path) -> tuple[Path, str]:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    token, _session = ApiSessionStore(workspace).create_session(
        "principal_owner", device_label="Raiker terminal"
    )
    _pending_shell(workspace)
    return workspace, token


def test_terminal_approval_requires_an_authenticated_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, _token = _workspace(tmp_path)
    monkeypatch.delenv("RAIKER_API_TOKEN", raising=False)

    result = handle_slash_command("/approve appr_terminal", workspace_root=workspace)

    assert "Authentication required" in result
    assert SQLiteStore(workspace).load_approval("appr_terminal")["status"] == "pending"  # type: ignore[index]


def test_terminal_approval_previews_without_executing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, token = _workspace(tmp_path)
    monkeypatch.setenv("RAIKER_API_TOKEN", token)

    result = handle_slash_command("/approve appr_terminal", workspace_root=workspace)

    assert "Effect preview" in result
    assert "echo 'terminal relay'" in result
    assert "workspace cwd" in result
    assert "/approve appr_terminal --confirm appr_terminal" in result
    assert SQLiteStore(workspace).load_approval("appr_terminal")["status"] == "pending"  # type: ignore[index]


def test_terminal_confirmation_executes_once_and_prints_bounded_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, token = _workspace(tmp_path)
    monkeypatch.setenv("RAIKER_API_TOKEN", token)

    result = handle_slash_command(
        "/approve appr_terminal --confirm appr_terminal", workspace_root=workspace
    )
    repeated = handle_slash_command(
        "/approve appr_terminal --confirm appr_terminal", workspace_root=workspace
    )

    assert "Executing" in result
    assert "terminal relay" in result
    assert "Continuing turn" in result
    assert "already resolved" in repeated.lower()
    approval = SQLiteStore(workspace).load_approval("appr_terminal")
    assert approval is not None
    assert approval["status"] == "executed"
    assert approval["approved_by"] == "principal_owner"
    detail = DashboardService(workspace).get_approval("appr_terminal")
    assert detail is not None
    assert detail.approval.resolved_by == "principal_owner"
    assert str(detail.execution_evidence["stdout"]).strip() == "terminal relay"
    assert detail.execution_evidence["returncode"] == 0


def test_revoked_terminal_session_cannot_execute(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, token = _workspace(tmp_path)
    sessions = ApiSessionStore(workspace)
    session = sessions.get_by_token(token)
    assert session is not None
    sessions.revoke_session(session.session_id)
    monkeypatch.setenv("RAIKER_API_TOKEN", token)

    result = handle_slash_command(
        "/approve appr_terminal --confirm appr_terminal", workspace_root=workspace
    )

    assert "revoked" in result.lower()
    assert SQLiteStore(workspace).load_approval("appr_terminal")["status"] == "pending"  # type: ignore[index]


def test_terminal_execution_redacts_secret_like_output_before_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, token = _workspace(tmp_path)
    store = SQLiteStore(workspace)
    arguments_json = json.dumps(
        {"command": ["echo", "sk-ant-api03-AAAABBBBCCCCDDDDEEEE"]},
        sort_keys=True,
    )
    with store.connect() as connection:
        connection.execute(
            "UPDATE tool_actions SET arguments_json = ? WHERE action_id = ?",
            (arguments_json, "act_terminal"),
        )
        payload_hash = store.tool_action_payload_sha256(
            "shell", arguments_json, "high"
        )
        connection.execute(
            "UPDATE approvals SET action_payload_sha256 = ? WHERE approval_id = ?",
            (payload_hash, "appr_terminal"),
        )
    monkeypatch.setenv("RAIKER_API_TOKEN", token)

    result = handle_slash_command(
        "/approve appr_terminal --confirm appr_terminal", workspace_root=workspace
    )
    detail = DashboardService(workspace).get_approval("appr_terminal")

    assert "sk-ant-api03" not in result
    assert "command_secret_pattern_rejected" in result
    assert detail is not None
    assert store.load_approval("appr_terminal")["status"] == "execution_failed"  # type: ignore[index]
    assert CommandStore(store).list_runs("principal_owner") == []
