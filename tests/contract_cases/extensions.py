"""Extensions and code: skills, the connector store, MCP connections, command
runs and credential deltas, the git credential, the web-access blocklist, and
Build's repositories and code map."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from raiker.contracts.ids import utc_now
from tests.contract_cases.base import Call, Cases, Seed, patched, plain

OWNER = "principal_owner"
SKILL_MD = "---\nname: tidy-imports\ndescription: Sort and group imports.\n---\n\nSort them.\n"
SKILL_URL = "https://raw.githubusercontent.com/o/r/main/skills/tidy/SKILL.md"
MANIFEST = {
    "openapi": "3.0.0",
    "servers": [{"url": "https://api.github.com"}],
    "paths": {
        "/user": {"get": {"operationId": "get_user", "summary": "Who am I"}},
        "/user/repos": {"post": {"operationId": "create_repo", "summary": "Create a repository"}},
    },
}


# ── skills ───────────────────────────────────────────────────────────────────


def _upload_body() -> dict[str, str]:
    return {"filename": "SKILL.md", "data_base64": base64.b64encode(SKILL_MD.encode()).decode()}


def _skill(client: TestClient, h: dict[str, str]) -> str:
    uploaded = client.post("/api/skills", json=_upload_body(), headers=h)
    assert uploaded.status_code == 200, uploaded.text
    return str(uploaded.json()["skill_id"])


def _skills(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    _skill(client, h)
    return "/api/skills"


def _on_skill(suffix: str, body: Any) -> Seed:
    def seed(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
        return f"/api/skills/{_skill(client, h)}{suffix}", body

    return seed


def _skill_deleted(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    return f"/api/skills/{_skill(client, h)}"


def _fake_skill_host(monkeypatch: Any) -> None:
    """The linked document, so no case reaches GitHub."""
    import raiker.runtime.executors.sandbox as sandbox

    monkeypatch.setattr(
        sandbox, "get_url",
        lambda url, **kwargs: {"status": 200, "body_text": SKILL_MD, "truncated": False},
    )


# ── connectors, the git credential ───────────────────────────────────────────


def _vault_key(monkeypatch: Any) -> None:
    """A configured connector vault, so credentials can be stored."""
    monkeypatch.setenv("RAIKER_CONNECTOR_VAULT_KEY", Fernet.generate_key().decode())


def _installed(client: TestClient, h: dict[str, str]) -> None:
    assert client.post("/api/connector-store/github/install", headers=h).status_code == 200


def _credited(client: TestClient, h: dict[str, str]) -> None:
    _installed(client, h)
    credited = client.put(
        "/api/connector-store/github/credentials", json={"values": {"token": "gho_contract"}}, headers=h
    )
    assert credited.status_code == 200, credited.text


def _store_view(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    _credited(client, h)
    assert client.post(
        "/api/connector-store/github/manifest", json={"manifest": MANIFEST}, headers=h
    ).status_code == 200
    return "/api/connector-store"


def _uninstall(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    _installed(client, h)
    return "/api/connector-store/github"


def _credentials(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    _installed(client, h)
    return "/api/connector-store/github/credentials", {"values": {"token": "gho_contract"}}


def _enable(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    _credited(client, h)
    return "/api/connector-store/github/enabled?enabled=true"


def _git_token(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    assert client.put("/api/git-credential", json={"token": "ghp_contract"}, headers=h).status_code == 200
    return "/api/git-credential"


_GRANT = {"scope": "once", "reason": "contract"}


def _git_grant(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    assert client.put("/api/git-credential", json={"token": "ghp_contract"}, headers=h).status_code == 200
    return "/api/git-credential/grant", _GRANT


def _git_revoke(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    _git_grant(ws, client, h)
    assert client.post("/api/git-credential/grant", json=_GRANT, headers=h).status_code == 200
    return "/api/git-credential/grant"


# ── the web-access blocklist ─────────────────────────────────────────────────


def _rule(client: TestClient, h: dict[str, str]) -> str:
    added = client.post(
        "/api/web-access/blocklist", json={"rule": "*.tracker.example", "note": "c"}, headers=h
    )
    assert added.status_code == 201, added.text
    return str(added.json()["rule_id"])


def _blocklist(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    _rule(client, h)
    return "/api/web-access/blocklist"


def _rule_deleted(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    return f"/api/web-access/blocklist/{_rule(client, h)}"


# ── MCP ──────────────────────────────────────────────────────────────────────


def _mcp_server(client: TestClient, h: dict[str, str]) -> str:
    created = client.post(
        "/api/mcp/servers", json={"name": "echo", "template": "python-stdio-echo"}, headers=h
    )
    assert created.status_code == 200, created.text
    return str(created.json()["server_id"])


def _on_mcp(suffix: str, body: Any = None) -> Seed:
    def seed(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
        path = f"/api/mcp/servers/{_mcp_server(client, h)}{suffix}"
        return path if body is None else (path, body)

    return seed


def _mcp_offer(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    """An installed plugin that offers one MCP server."""
    from raiker.plugins.contributions import PLUGIN_HOOKS_DIR, PLUGIN_MCP_FILE

    folder = ws / PLUGIN_HOOKS_DIR / "plugin_contract"
    folder.mkdir(parents=True)
    (folder / PLUGIN_MCP_FILE).write_text(
        json.dumps({"servers": [{
            "name": "notes", "transport": "http",
            "endpoint_url": "https://mcp.example.com/rpc", "description": "Notes",
        }]}),
        encoding="utf-8",
    )
    return "/api/mcp/offers"


# ── command runs and credential deltas ───────────────────────────────────────


def _finished_run(ws: Path) -> str:
    """A run that ran, wrote a line, and was receipted — straight into the store."""
    from raiker.execution.commands.models import (
        CommandChunk,
        CommandReceipt,
        CommandRequest,
        CommandState,
    )
    from raiker.execution.commands.service import CommandService

    store = CommandService.for_workspace(ws).store
    request = CommandRequest(
        run_id="cmd_contract", owner_principal_id=OWNER, acting_principal_id=OWNER,
        session_id="sess_build", turn_id="turn_build", action_id="act_build", repository_id=None,
        workspace_root=ws, cwd=".", executable_template="", argv_template=("git", "status"),
        safe_display="git status", credential_bindings=(), shell=False, interactive=False,
        background=False, timeout_seconds=30.0, max_output_bytes=4096,
        environment_profile_id="local_strict", network_policy_id=None,
        authority_kind="approval", authority_id="appr_build",
    )
    store.create_finalizing(request)
    store.append_chunk(OWNER, CommandChunk(
        run_id="cmd_contract", sequence=1, stream="stdout", text="clean\n", byte_count=6,
        emitted_at=utc_now(), start_byte_offset=0, end_byte_offset=6,
    ))
    receipt = CommandReceipt.create(
        run_id="cmd_contract", state=CommandState.SUCCEEDED, exit_code=0,
        termination_reason="exited", completed_at=utc_now(), evidence={"backend": "local_strict"},
    )
    store.finalize_with_receipt(OWNER, "cmd_contract", CommandState.SUCCEEDED, receipt)
    return "cmd_contract"


def _run(suffix: str) -> Seed:
    def seed(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
        return f"/api/command-runs/{_finished_run(ws)}{suffix}"

    return seed


def _runs(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    _finished_run(ws)
    return "/api/command-runs"


def _delta(ws: Path) -> None:
    from raiker.execution.commands.service import CommandService

    CommandService.for_workspace(ws).store.create_credential_delta(
        owner_principal_id=OWNER, run_id="cmd_delta", environment_profile_id="container_a",
        state="quarantined", snapshot_handle=b"staging", cleanup_scan_bundle=b"bytes",
        safe_manifest_json='{"files":[{"kind":"file","path":"result.txt","size":4}]}',
        delta_digest="a" * 64, scan_digest="b" * 64,
    )


def _deltas(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    _delta(ws)
    return "/api/credential-deltas?environment_profile_id=container_a"


def _delta_discarded(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    _delta(ws)
    return "/api/credential-deltas/cmd_delta/discard", {"decision_id": "decision_owner"}


# ── Build's repositories and the code map ────────────────────────────────────


def _local_repo(ws: Path, client: TestClient, h: dict[str, str]) -> str:
    (ws / "projects" / "app").mkdir(parents=True, exist_ok=True)
    (ws / "projects" / "app" / "main.py").write_text("def main() -> None:\n    pass\n", encoding="utf-8")
    connected = client.post(
        "/api/code/repos", json={"kind": "local", "path": "projects/app"}, headers=h
    )
    assert connected.status_code == 201, connected.text
    return str(connected.json()["repo_id"])


def _selected_repo(ws: Path, client: TestClient, h: dict[str, str]) -> str:
    repo_id = _local_repo(ws, client, h)
    selected = client.put("/api/code/repos/selection", json={"repo_id": repo_id}, headers=h)
    assert selected.status_code == 200, selected.text
    return repo_id


def _after_selection(path: str) -> Seed:
    def seed(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
        _selected_repo(ws, client, h)
        return path

    return seed


def _connect_repo(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    (ws / "projects" / "app").mkdir(parents=True, exist_ok=True)
    (ws / "projects" / "app" / "main.py").write_text("x = 1\n", encoding="utf-8")
    return "/api/code/repos", {"kind": "local", "path": "projects/app"}


def _select_repo(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    return "/api/code/repos/selection", {"repo_id": _local_repo(ws, client, h)}


def _disconnect_repo(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    return f"/api/code/repos/{_local_repo(ws, client, h)}"


# ── files in a repository, hooks, plugins ────────────────────────────────────


def _on_repo(suffix: str) -> Seed:
    """A connected git repository with one committed file and one uncommitted change."""

    def seed(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
        import subprocess

        repo_id = _local_repo(ws, client, h)
        root = ws / "projects" / "app"
        git = ["git", "-c", "user.name=c", "-c", "user.email=c@example.com", "-C", str(root)]
        subprocess.run([*git, "init", "-q"], check=True)
        subprocess.run([*git, "add", "."], check=True)
        subprocess.run([*git, "commit", "-qm", "init"], check=True)
        (root / "main.py").write_text("def main() -> None:\n    return None\n", encoding="utf-8")
        return f"/api/code/repos/{repo_id}{suffix}"

    return seed


# ── channels ─────────────────────────────────────────────────────────────────


def _channel_pairing(ws: Path, connector_id: str = "channel.webhook", sender: str = "alice") -> str:
    from raiker.contracts.ids import new_id
    from raiker.contracts.models import ChannelPairing
    from raiker.storage.sqlite import SQLiteStore

    pairing_id = new_id("chn_")
    SQLiteStore(ws).insert_channel_pairing(ChannelPairing(
        pairing_id=pairing_id, connector_id=connector_id,
        channel_type="telegram" if connector_id == "channel.telegram" else "webhooks",
        display_name="Contract", paired_at=utc_now(), paired_by=OWNER, enabled=True,
        sender_allowlist_json=json.dumps([sender]),
    ))
    return pairing_id


def _channels(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    _channel_pairing(ws)
    return "/api/channels"


def _on_pairing(suffix: str, body: Any = None) -> Seed:
    def seed(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
        path = f"/api/channels/pairings/{_channel_pairing(ws)}{suffix}"
        return path if body is None else (path, body)

    return seed


def _channel_gate_open(ws: Path) -> None:
    from raiker.control.service import RuntimeControlService
    from raiker.storage.sqlite import SQLiteStore

    control = RuntimeControlService(ws)
    control.activate_runtime_mode("local_single_user_runtime", None, "test")
    with SQLiteStore(ws).connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref) "
            "VALUES (?, ?, ?, ?)",
            ("external_channel_runtime", OWNER, utc_now(), "docs/threat-models/channels.md"),
        )
    opened = control.set_capability_state(
        "external_channel_runtime", "enabled_runtime", None, "test", confirmation_token="confirm"
    )
    assert opened.ok, opened.reason_code


def _deliver_test(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    from raiker.storage.sqlite import SQLiteStore

    _channel_gate_open(ws)
    # UX-MSG-04 — the destination is bound on the pairing, never sent.
    SQLiteStore(ws).set_channel_pairing_destination(
        _channel_pairing(ws), "http://127.0.0.1:9/hook"
    )
    return "/api/channels/deliver-test", {"connector_id": "channel.webhook", "text": "hello"}


def _fake_channel_host(monkeypatch: Any) -> None:
    """A receiver that accepts every delivery, so no case reaches the network."""
    import raiker.runtime.executors.channels as channels

    monkeypatch.setenv("RAIKER_CHANNEL_EGRESS_ALLOWLIST", "127.0.0.1:9")
    monkeypatch.setattr(
        channels, "post_url",
        lambda *args, **kwargs: {"status": 200, "sent_bytes": 5, "response_bytes": 0},
    )


def _inbound_secret(monkeypatch: Any) -> None:
    monkeypatch.setenv("RAIKER_CHANNEL_INBOUND_SECRET", "s3cret")


def _inbound(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    _channel_pairing(ws)
    return (
        "/api/channels/channel.webhook/inbound",
        {"sender_id": "alice", "text": "hello"},
        {"X-Raiker-Channel-Secret": "s3cret"},
    )


def _telegram(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    _channel_gate_open(ws)
    _channel_pairing(ws, "channel.telegram", "4242")
    return (
        "/api/channels/channel.telegram/telegram",
        {"message": {"from": {"id": 4242}, "chat": {"id": 4242}, "text": "hello"}},
        {"X-Telegram-Bot-Api-Secret-Token": "s3cret"},
    )


def _approval_response(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    """A relayed approval the paired owner answers from the channel."""
    from raiker.contracts.models import ApprovalRelayRecord
    from raiker.control.service import RuntimeControlService
    from raiker.storage.sqlite import SQLiteStore
    from tests.factories import tool_action

    pairing_id = _channel_pairing(ws)
    routed = RuntimeControlService(ws).set_channel_routing(
        None, pairing_id, routing_mode="record_only", target_session_id=None,
        owner_sender_id="alice", approval_relay_enabled=True,
    )
    assert routed.ok, routed.reason_code
    store = SQLiteStore(ws)
    store.create_session("sess_relay", str(ws))
    action = tool_action(
        "write_file", {"path": "never.txt", "text": "no"}, action_id="act_relay",
        risk_level="high", requires_approval=True,
    )
    store.insert_tool_action(action, session_id="sess_relay", turn_id="turn_relay", status="approval_required")
    store.insert_approval("appr_relay", action)
    store.insert_approval_relay(ApprovalRelayRecord(
        relay_id="chr_relay", pairing_id=pairing_id, action_id="act_relay", status="pending",
        requested_at=utc_now(), resolved_at=None, resolved_by=None,
    ))
    return (
        "/api/channels/channel.webhook/approval-response",
        {"sender_id": "alice", "relay_id": "chr_relay", "action_id": "act_relay", "approve": False},
        {"X-Raiker-Channel-Secret": "s3cret"},
    )


CASES: Cases = {
    ("GET", "/api/skills"): _skills,
    ("POST", "/api/skills"): plain("/api/skills", _upload_body()),
    ("POST", "/api/skills/build"): plain(
        "/api/skills/build",
        {"name": "note-taker", "description": "Take notes.", "body": "Write it down.",
         "command_trigger": "notes"},
    ),
    ("POST", "/api/skills/verify"): patched(plain("/api/skills/verify", {"url": SKILL_URL}), _fake_skill_host),
    ("POST", "/api/skills/import"): patched(plain("/api/skills/import", {"url": SKILL_URL}), _fake_skill_host),
    ("PUT", "/api/skills/{skill_id}"): _on_skill("", {"name": "tidy-all-imports"}),
    ("PUT", "/api/skills/{skill_id}/active"): _on_skill("/active", {"active": True}),
    ("PUT", "/api/skills/{skill_id}/command"): _on_skill("/command", {"command_trigger": "tidy"}),
    ("DELETE", "/api/skills/{skill_id}"): _skill_deleted,
    ("GET", "/api/connector-store"): patched(_store_view, _vault_key),
    ("POST", "/api/connector-store/{connector_id}/install"): plain("/api/connector-store/github/install"),
    ("DELETE", "/api/connector-store/{connector_id}"): _uninstall,
    ("PUT", "/api/connector-store/{connector_id}/credentials"): patched(_credentials, _vault_key),
    ("PUT", "/api/connector-store/{connector_id}/enabled"): patched(_enable, _vault_key),
    ("POST", "/api/connector-store/{connector_id}/manifest"): plain(
        "/api/connector-store/github/manifest", {"manifest": MANIFEST}
    ),
    ("GET", "/api/git-credential"): patched(_git_token, _vault_key),
    ("PUT", "/api/git-credential"): patched(plain("/api/git-credential", {"token": "ghp_contract"}), _vault_key),
    ("DELETE", "/api/git-credential"): patched(_git_token, _vault_key),
    ("POST", "/api/git-credential/grant"): patched(_git_grant, _vault_key),
    ("DELETE", "/api/git-credential/grant"): patched(_git_revoke, _vault_key),
    ("GET", "/api/web-access/blocklist"): _blocklist,
    ("POST", "/api/web-access/blocklist"): plain(
        "/api/web-access/blocklist", {"rule": "*.tracker.example", "note": "contract"}
    ),
    ("POST", "/api/web-access/blocklist/test"): plain(
        "/api/web-access/blocklist/test", {"host": "127.0.0.1"}
    ),
    ("DELETE", "/api/web-access/blocklist/{rule_id}"): _rule_deleted,
    ("POST", "/api/mcp/servers"): plain(
        "/api/mcp/servers", {"name": "echo", "template": "python-stdio-echo"}
    ),
    ("POST", "/api/mcp/servers/remote"): plain(
        "/api/mcp/servers/remote", {"name": "remote", "endpoint_url": "https://mcp.example.com/rpc"}
    ),
    ("PUT", "/api/mcp/servers/{server_id}"): _on_mcp("", {"name": "echo-two"}),
    ("DELETE", "/api/mcp/servers/{server_id}"): _on_mcp(""),
    ("POST", "/api/mcp/servers/{server_id}/connect"): _on_mcp("/connect"),
    ("POST", "/api/mcp/servers/{server_id}/pause"): _on_mcp("/pause", {"reason": "contract"}),
    ("POST", "/api/mcp/servers/{server_id}/kill"): _on_mcp("/kill", {"reason": "contract"}),
    ("POST", "/api/mcp/servers/{server_id}/resume"): _on_mcp("/resume"),
    ("POST", "/api/mcp/servers/{server_id}/tools/approve"): _on_mcp(
        "/tools/approve", {"tools": ["echo"]}
    ),
    ("GET", "/api/mcp/offers"): _mcp_offer,
    ("GET", "/api/mcp/agent-access"): plain("/api/mcp/agent-access"),
    ("GET", "/api/command-runs"): _runs,
    ("GET", "/api/command-runs/{run_id}"): _run(""),
    ("GET", "/api/command-runs/{run_id}/output"): _run("/output"),
    ("GET", "/api/command-runs/{run_id}/receipt"): _run("/receipt"),
    ("POST", "/api/command-runs/{run_id}/stop"): _run("/stop"),
    ("GET", "/api/credential-deltas"): _deltas,
    ("POST", "/api/credential-deltas/{run_id}/discard"): _delta_discarded,
    ("GET", "/api/code/map"): _after_selection("/api/code/map"),
    ("GET", "/api/code/map/paths"): _after_selection("/api/code/map/paths?q=main"),
    ("POST", "/api/code/map/rebuild"): _after_selection("/api/code/map/rebuild"),
    ("POST", "/api/code/repos"): _connect_repo,
    ("PUT", "/api/code/repos/selection"): _select_repo,
    ("DELETE", "/api/code/repos/{repo_id}"): _disconnect_repo,
    ("GET", "/api/code/repos/{repo_id}/browse"): _on_repo("/browse"),
    ("GET", "/api/code/repos/{repo_id}/file"): _on_repo("/file?path=main.py"),
    ("GET", "/api/code/repos/{repo_id}/changes"): _on_repo("/changes"),
    ("GET", "/api/code/repos/{repo_id}/diagnostics"): _on_repo("/diagnostics?path=main.py"),
    ("GET", "/api/hooks"): plain("/api/hooks"),
    ("GET", "/api/plugins"): plain("/api/plugins"),
    ("GET", "/api/channels"): _channels,
    ("POST", "/api/channels/pairings"): plain(
        "/api/channels/pairings",
        {"connector_id": "channel.webhooks", "display_name": "Contract", "senders": ["alice"]},
    ),
    ("PUT", "/api/channels/pairings/{pairing_id}/enabled"): _on_pairing("/enabled", {"enabled": False}),
    ("PUT", "/api/channels/pairings/{pairing_id}/senders"): _on_pairing("/senders", {"senders": ["alice", "bob"]}),
    ("PUT", "/api/channels/pairings/{pairing_id}/routing"): _on_pairing(
        "/routing", {"routing_mode": "record_only", "owner_sender_id": "alice"}
    ),
    ("PUT", "/api/channels/pairings/{pairing_id}/destination"): _on_pairing(
        "/destination", {"delivery_url": "https://hooks.example.com/raiker"}
    ),
    ("DELETE", "/api/channels/pairings/{pairing_id}"): _on_pairing(""),
    ("POST", "/api/channels/deliver-test"): patched(_deliver_test, _fake_channel_host),
    ("POST", "/api/channels/{connector_id}/inbound"): patched(_inbound, _inbound_secret),
    ("POST", "/api/channels/{connector_id}/telegram"): patched(_telegram, _inbound_secret),
    ("POST", "/api/channels/{connector_id}/approval-response"): patched(_approval_response, _inbound_secret),
}
