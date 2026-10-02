"""Governance: approvals and their resumption, runtime mode, capability gates
and decision modes, standing grants, audit and telemetry export, security
containment and health, the vault, and the environment a turn sees."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from raiker.api.sessions import ApiSessionStore
from raiker.contracts.ids import utc_now
from raiker.contracts.models import OWNER_QUESTION_TOOL
from raiker.storage.sqlite import SQLiteStore
from tests.contract_cases.base import Call, Cases, Seed, first, patched, plain
from tests.factories import tool_action

OWNER = "principal_owner"
#: A gate the owner may switch on in a local runtime, with a threat model to acknowledge.
GATED = "image_generation"
#: A capability with a real executor, so every decision mode is settable.
MODED = "file_write_execution"

PROPOSED = "--- a/poem.txt\n+++ b/poem.txt\n@@ -1,2 +1,2 @@\n-roses\n+roses are read\n violets\n"
QUESTIONS = [
    {
        "question": "Which database should the new service use?",
        "header": "Database",
        "options": [{"label": "Postgres", "description": ""}, {"label": "SQLite", "description": ""}],
    }
]


def _pending(
    ws: Path, tool_name: str, arguments: dict[str, Any], *, critical: bool = False
) -> str:
    """An approval-required action and its pending approval, as the broker writes them."""
    store = SQLiteStore(ws)
    store.create_session(f"sess_{tool_name}", str(ws), user_id="owner")
    store.insert_turn(f"sess_{tool_name}", f"turn_{tool_name}", "do the thing")
    action = tool_action(
        tool_name, arguments, action_id=f"act_{tool_name}",
        risk_level="low" if tool_name == OWNER_QUESTION_TOOL else "medium",
        requires_approval=True, proposed_by=OWNER,
    )
    store.insert_tool_action(action, f"sess_{tool_name}", f"turn_{tool_name}", "approval_required")
    store.insert_approval(f"appr_{tool_name}", action)
    if critical:
        with store.connect() as connection:
            connection.execute(
                "UPDATE approvals SET critical = 1 WHERE approval_id = ?", (f"appr_{tool_name}",)
            )
    return f"appr_{tool_name}"


def _resumable(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    """A turn parked on an approval that has since been decided, not yet claimed."""
    store = SQLiteStore(ws)
    store.insert_suspended_turn({
        "approval_id": "appr_parked", "session_id": "sess_parked", "turn_id": "turn_parked",
        "request_id": "req_parked", "principal_id": OWNER, "action_id": "act_parked",
        "tool_name": "write_file", "call_id": "call_parked", "prompt_text": "write notes.md",
        "messages_json": json.dumps([{"role": "user", "content": "write notes.md"}]),
        "options_json": "{}", "client_json": "{}",
    })
    store.record_suspended_turn_outcome("appr_parked", json.dumps({"status": "approved"}))
    return "/api/approvals/resumable"


def _answer(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    approval_id = _pending(ws, OWNER_QUESTION_TOOL, {"questions": QUESTIONS})
    return f"/api/approvals/{approval_id}/answer", {
        "answers": {"Which database should the new service use?": "SQLite"}
    }


def _replace(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    (ws / "poem.txt").write_text("roses\nviolets\n", encoding="utf-8")
    approval_id = _pending(ws, "apply_patch", {"path": "poem.txt", "patch": PROPOSED})
    return f"/api/approvals/{approval_id}/replace", {
        "patch": PROPOSED.replace("roses are read", "roses are red"), "reason": "typo",
    }


def _resolve(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    """Approving a file write carries it out, so the answer has its execution."""
    approval_id = _pending(ws, "write_file", {"path": "notes.txt", "text": "hello\n"})
    return f"/api/approvals/{approval_id}/resolve", {"approve": True, "reason": "fine"}


def _elevated(ws: Path) -> dict[str, str]:
    token, _session = ApiSessionStore(ws).create_session(
        OWNER, scope="elevated", expires_in_seconds=60
    )
    return {"Authorization": f"Bearer {token}"}


def _resolve_critical(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    approval_id = _pending(ws, "write_file", {"path": "notes.txt", "text": "hi"}, critical=True)
    return (
        f"/api/approvals/{approval_id}/resolve-critical",
        {"approve": False, "reason": "not now"},
        _elevated(ws),
    )


def _local_mode(ws: Path) -> None:
    from raiker.control.service import RuntimeControlService

    RuntimeControlService(ws).activate_runtime_mode("local_single_user_runtime", None, "test")


def _acknowledged(ws: Path) -> None:
    _local_mode(ws)
    with SQLiteStore(ws).connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref) "
            "VALUES (?, ?, ?, ?)",
            (GATED, OWNER, utc_now(), "docs/threat-models/models.md"),
        )


_ENABLE = {"target_state": "enabled_runtime", "reason": "contract", "confirmation_token": "confirm"}


def _set_gate(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    _acknowledged(ws)
    return f"/api/capability-gates/{GATED}/set", _ENABLE


def _threat_ack(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    _local_mode(ws)
    return f"/api/capability-gates/{GATED}/threat-ack", {"reason": "read the threat model"}


def _disable_gate(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    _acknowledged(ws)
    enabled = client.post(f"/api/capability-gates/{GATED}/set", json=_ENABLE, headers=h)
    assert enabled.status_code == 200, enabled.text
    return f"/api/capability-gates/{GATED}/disable", {"reason": "contract"}


def _mode(mode: str) -> Seed:
    return plain(f"/api/capability-modes/{MODED}/{mode}", {"reason": f"set {mode}"})


def _runtime_mode_off(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    _local_mode(ws)
    return "/api/runtime-mode/disable", {"reason": "contract"}


_GRANT = {"action_type": "write_file", "risk_ceiling": "medium", "reason": "contract"}


def _grant(client: TestClient, h: dict[str, str]) -> str:
    created = client.post("/api/standing-grants", json=_GRANT, headers=h)
    assert created.status_code == 200, created.text
    return str(created.json()["grant"]["grant_id"])


def _grants(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    _grant(client, h)
    return "/api/standing-grants"


def _revoke_grant(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    return f"/api/standing-grants/{_grant(client, h)}/revoke"


def _audit_export(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    _local_mode(ws)
    return "/api/audit/export"


def _audit_exports(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    _local_mode(ws)
    assert client.post("/api/audit/export", headers=h).status_code == 200
    return "/api/audit/exports"


_DESTINATION = {"name": "collector", "endpoint_url": "http://127.0.0.1:4318"}


def _destination(client: TestClient, h: dict[str, str]) -> str:
    created = client.post("/api/telemetry/destinations", json=_DESTINATION, headers=h)
    assert created.status_code == 200, created.text
    return str(created.json()["destination_id"])


def _destinations(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    _destination(client, h)
    return "/api/telemetry/destinations"


def _on_destination(suffix: str, body: Any = None) -> Seed:
    def seed(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
        path = f"/api/telemetry/destinations/{_destination(client, h)}{suffix}"
        return path if body is None else (path, body)

    return seed


def _fake_collector(monkeypatch: Any) -> None:
    """A collector that accepts everything, so no case reaches the network."""
    from raiker.runtime.executors import tier2_telemetry

    monkeypatch.setattr(
        tier2_telemetry, "post_json_url",
        lambda *args, **kwargs: {"status": 200, "body_text": "", "body_bytes": 0, "truncated": False},
    )


def _notification_read(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    store = SQLiteStore(ws)
    store.insert_notification(
        principal_id=OWNER, kind="security_alert", title="Probe", body="A probe", finding_id=None,
        subject_id="probe",
    )
    return f"/api/notifications/{first(client, h, '/api/notifications', 'notification_id')}/read"


def _no_vault_key(monkeypatch: Any) -> None:
    monkeypatch.delenv("RAIKER_CONNECTOR_VAULT_KEY", raising=False)


def _health_rows(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    assert client.post("/api/security/health-check", headers=h).status_code == 200
    return "/api/security/health"


def _vault_key(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    return "/api/vault/key", {"key": Fernet.generate_key().decode()}, _elevated(ws)


def _vault_cleared(ws: Path, client: TestClient, _h: dict[str, str]) -> Call:
    elevated = _elevated(ws)
    put = client.put("/api/vault/key", json={"key": Fernet.generate_key().decode()}, headers=elevated)
    assert put.status_code == 200, put.text
    return "/api/vault/key", None, elevated


CASES: Cases = {
    ("GET", "/api/approvals/resumable"): _resumable,
    ("POST", "/api/approvals/{approval_id}/answer"): _answer,
    ("POST", "/api/approvals/{approval_id}/replace"): _replace,
    ("POST", "/api/approvals/{approval_id}/resolve"): _resolve,
    ("POST", "/api/approvals/{approval_id}/resolve-critical"): _resolve_critical,
    ("POST", "/api/runtime-mode/activate"): plain(
        "/api/runtime-mode/activate", {"mode_name": "local_single_user_runtime", "reason": "contract"}
    ),
    ("POST", "/api/runtime-mode/disable"): _runtime_mode_off,
    ("POST", "/api/capability-gates/{capability}/set"): _set_gate,
    ("POST", "/api/capability-gates/{capability}/threat-ack"): _threat_ack,
    ("POST", "/api/capability-gates/{capability}/disable"): _disable_gate,
    ("GET", "/api/capability-modes/{capability}"): plain(f"/api/capability-modes/{MODED}"),
    ("POST", "/api/capability-modes/{capability}/ask"): _mode("ask"),
    ("POST", "/api/capability-modes/{capability}/allow"): _mode("allow"),
    ("POST", "/api/capability-modes/{capability}/auto"): _mode("auto"),
    ("POST", "/api/capability-modes/{capability}/deny"): _mode("deny"),
    ("GET", "/api/standing-grants"): _grants,
    ("POST", "/api/standing-grants"): plain("/api/standing-grants", _GRANT),
    ("POST", "/api/standing-grants/{grant_id}/revoke"): _revoke_grant,
    ("POST", "/api/audit/export"): _audit_export,
    ("GET", "/api/audit/exports"): _audit_exports,
    ("GET", "/api/telemetry/destinations"): _destinations,
    ("POST", "/api/telemetry/destinations"): plain("/api/telemetry/destinations", _DESTINATION),
    ("PUT", "/api/telemetry/destinations/{destination_id}/cadence"): _on_destination(
        "/cadence", {"cadence": "daily"}
    ),
    ("DELETE", "/api/telemetry/destinations/{destination_id}"): _on_destination(""),
    ("POST", "/api/telemetry/destinations/{destination_id}/export"): patched(
        _on_destination("/export"), _fake_collector
    ),
    ("POST", "/api/notifications/{notification_id}/read"): _notification_read,
    ("GET", "/api/security/containment"): plain("/api/security/containment"),
    ("POST", "/api/security/containment/{capability}/{subject_id}/{action}"): plain(
        "/api/security/containment/connector/github/pause"
    ),
    ("POST", "/api/security/health-check"): patched(
        plain("/api/security/health-check"), _no_vault_key
    ),
    ("GET", "/api/security/health"): patched(_health_rows, _no_vault_key),
    ("GET", "/api/vault/status"): plain("/api/vault/status"),
    ("PUT", "/api/vault/key"): _vault_key,
    ("DELETE", "/api/vault/key"): _vault_cleared,
    ("GET", "/api/read-capabilities"): plain("/api/read-capabilities"),
    ("GET", "/api/environment"): plain("/api/environment"),
    ("GET", "/api/health"): plain("/api/health"),
}
