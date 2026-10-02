"""The host and everything around a turn: host control and updates, the Browse
dialog, settings, the guide, the tray, instances, execution environments,
prompts, interrupts, stopping everything, attachments, resuming a parked turn,
the diagnostics bundle and a connector action."""

from __future__ import annotations

import base64
import hashlib
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from raiker.api.sessions import ApiSessionStore
from raiker.storage.sqlite import SQLiteStore
from tests.contract_cases.base import Call, Cases, Seed, patched, plain

OWNER = "principal_owner"
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


# ── host control ─────────────────────────────────────────────────────────────


def _host_control(ws: Path) -> dict[str, str]:
    """A host_control session — the scope the tray holds, and the only one host routes take."""
    token, _session = ApiSessionStore(ws).create_session(
        OWNER, scopes=("host_control",), scope="host_control"
    )
    return {"Authorization": f"Bearer {token}"}


def _host(path: str, body: Any = None) -> Seed:
    def seed(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
        return path, body, _host_control(ws)

    return seed


def _no_stop(monkeypatch: Any) -> None:
    """Record the stop a quit or restart schedules instead of stopping the test process."""
    import raiker.api.routes_host as routes

    monkeypatch.setattr(routes, "_schedule_stop", lambda request, exit_code: None)


def _registered(monkeypatch: Any) -> None:
    """A host registered with the platform's service manager, so a restart is possible."""
    import raiker.api.routes_host as routes

    _no_stop(monkeypatch)
    real = routes.registration
    monkeypatch.setattr(
        routes, "registration",
        lambda workspace, **kwargs: replace(real(workspace, **kwargs), registered=True),
    )


# ── settings, guide, tray, instances ─────────────────────────────────────────


def _guide_section(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    sections = client.get("/api/guide", headers=h).json()["sections"]
    assert sections, "this build carries no guide to read a section of"
    return "/api/guide/" + str(sections[0]["slug"])


def _tray(_ws: Path, client: TestClient, _h: dict[str, str]) -> Call:
    """The bootstrap secret the native tray was launched with, not yet used."""
    state = client.app.state  # type: ignore[attr-defined]
    state.tray_bootstrap_digest = hashlib.sha256(b"one-time-secret").hexdigest()
    state.tray_bootstrap_expires = time.monotonic() + 60
    state.tray_bootstrap_used = False
    return "/api/tray/session", {"secret": "one-time-secret"}


# ── execution environments ───────────────────────────────────────────────────


def _measured(monkeypatch: Any) -> None:
    """Every boundary measures as available and persistent; nothing is probed for real."""
    from raiker.execution.commands.models import CommandFeatures
    from raiker.execution.commands.service import CommandService
    from raiker.execution.profiles import ProfileProbe

    monkeypatch.setenv("RAIKER_TEST_SSH_KEY", "test key path only")
    monkeypatch.setattr(
        "raiker.control.dashboard_parts.execution.probe_execution_profile",
        lambda profile, **_kwargs: ProfileProbe(
            profile, True, None, "2026-10-02T00:00:00Z", boundary="remote_recipient_tcb",
            observations={"network": "enforced"},
            features=replace(CommandFeatures(), persistent_environment=True),
        ),
    )
    monkeypatch.setattr(CommandService, "reset_environment", lambda *args, **kwargs: True)


def _ssh_profile(client: TestClient, h: dict[str, str]) -> str:
    from raiker.execution.commands.known_hosts import host_key_fingerprint

    key = "ssh-ed25519 " + base64.b64encode(b"test execution host key").decode()
    saved = client.put(
        "/api/execution-environments/configure",
        json={
            "kind": "ssh", "name": "Build host", "enabled": True,
            "config": {
                "host": "build.example.com", "user": "raiker", "credential_env": "RAIKER_TEST_SSH_KEY",
                "host_public_key": key, "host_key_sha256": host_key_fingerprint(key),
            },
        },
        headers=h,
    )
    assert saved.status_code == 200, saved.text
    return str(saved.json()["profile_id"])


def _configure(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    from raiker.execution.commands.known_hosts import host_key_fingerprint

    key = "ssh-ed25519 " + base64.b64encode(b"test execution host key").decode()
    return "/api/execution-environments/configure", {
        "kind": "ssh", "name": "Build host", "enabled": True,
        "config": {
            "host": "build.example.com", "user": "raiker", "credential_env": "RAIKER_TEST_SSH_KEY",
            "host_public_key": key, "host_key_sha256": host_key_fingerprint(key),
        },
    }


def _environments(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    _ssh_profile(client, h)
    return "/api/execution-environments"


def _select(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    return "/api/execution-environments/selection", {"profile_id": _ssh_profile(client, h)}


def _probe(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    return f"/api/execution-environments/{_ssh_profile(client, h)}/probe"


def _reset(_ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    """The default container is the boundary that persists across a session's commands."""
    return "/api/execution-environments/container_default/reset", {
        "session_id": "sess_build", "recreate": False,
    }


# ── turns: prompts, interrupts, stop-all, attachments, resume ────────────────


def _owned_session(ws: Path, session_id: str = "sess_contract") -> str:
    store = SQLiteStore(ws)
    store.create_session(session_id, str(ws), user_id="owner")
    return session_id


def _interrupt(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    return "/api/interrupts", {
        "session_id": _owned_session(ws), "all": True, "action_type": "cancel", "reason": "contract",
    }


def _stop_all(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    from raiker.events.writer import EventLogWriter
    from raiker.tasks.manager import TaskManager

    store = SQLiteStore(ws)
    session_id = _owned_session(ws)
    TaskManager(store, EventLogWriter(store)).create_task(
        session_id=session_id, title="t", objective="o"
    )
    return "/api/stop-all"


_SCRIPT: list[Any] = []


def _scripted_model(monkeypatch: Any) -> None:
    """A model that proposes one file write, then reports it done."""
    from raiker.models.contracts import ModelResponse
    from raiker.models.router import ModelRouter
    from tests.test_turn_resume_after_approval import ScriptedRouter, _write_call

    script = ScriptedRouter([
        ModelResponse(text="Writing it now.", tool_calls=[_write_call()]),
        ModelResponse(text="Done — report.md now holds the report."),
    ])
    _SCRIPT[:] = [script]

    async def achat(self: Any, provider: str, model: str, messages: Any, tools: Any = None) -> Any:
        return script.chat(provider, model, messages, tools)

    monkeypatch.setattr(ModelRouter, "achat", achat, raising=False)


def _resume(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    """A turn parked on a file write, approved, and waiting to continue."""
    from tests.test_turn_resume_after_approval import _park_turn

    approval_id, _envelope = _park_turn(ws, _SCRIPT[0])
    resolved = client.post(
        f"/api/approvals/{approval_id}/resolve", json={"approve": True, "reason": "ship it"}, headers=h
    )
    assert resolved.status_code == 200, resolved.text
    return f"/api/approvals/{approval_id}/resume"


def _connector_write(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    """An enabled connector whose operation writes, so the action waits for approval."""
    from tests.contract_cases.extensions import MANIFEST

    assert client.post("/api/connector-store/github/install", headers=h).status_code == 200
    assert client.put(
        "/api/connector-store/github/credentials", json={"values": {"token": "gho_c"}}, headers=h
    ).status_code == 200
    assert client.post(
        "/api/connector-store/github/manifest", json={"manifest": MANIFEST}, headers=h
    ).status_code == 200
    assert client.put("/api/connector-store/github/enabled?enabled=true", headers=h).status_code == 200
    return "/api/connector-store/github/actions", {
        "operation_id": "create_repo", "arguments": {"name": "contract"},
    }


def _vault_key(monkeypatch: Any) -> None:
    from cryptography.fernet import Fernet

    monkeypatch.setenv("RAIKER_CONNECTOR_VAULT_KEY", Fernet.generate_key().decode())


CASES: Cases = {
    ("GET", "/api/host"): _host("/api/host"),
    ("POST", "/api/host/pause"): _host("/api/host/pause", {"reason": "contract"}),
    ("POST", "/api/host/resume"): _host("/api/host/resume"),
    ("POST", "/api/host/quit"): patched(_host("/api/host/quit", {"confirm": True}), _no_stop),
    ("POST", "/api/host/restart"): patched(_host("/api/host/restart", {"confirm": True}), _registered),
    ("GET", "/api/host/paths"): _host("/api/host/paths"),
    ("GET", "/api/host/update"): plain("/api/host/update"),
    ("POST", "/api/host/update/check"): plain("/api/host/update/check"),
    ("POST", "/api/host/update/apply"): patched(plain("/api/host/update/apply", {"confirm": True}), _no_stop),
    ("GET", "/api/settings"): plain("/api/settings"),
    ("PUT", "/api/settings"): plain("/api/settings", {"settings": {"general.theme": "dark"}}),
    ("GET", "/api/settings/composer-approval-mode"): plain("/api/settings/composer-approval-mode"),
    ("PUT", "/api/settings/composer-approval-mode"): plain(
        "/api/settings/composer-approval-mode", {"approval_mode": "manual"}
    ),
    ("GET", "/api/guide"): plain("/api/guide"),
    ("GET", "/api/guide/{slug}"): _guide_section,
    ("POST", "/api/tray/session"): _tray,
    ("POST", "/api/instances"): plain("/api/instances", {"name": "contract"}),
    ("GET", "/api/execution-environments"): patched(_environments, _measured),
    ("PUT", "/api/execution-environments/configure"): patched(_configure, _measured),
    ("PUT", "/api/execution-environments/selection"): patched(_select, _measured),
    ("POST", "/api/execution-environments/{profile_id}/probe"): patched(_probe, _measured),
    ("POST", "/api/execution-environments/{profile_id}/reset"): patched(_reset, _measured),
    ("POST", "/api/prompts"): plain("/api/prompts", {"text": "hello", "surface": "chat"}),
    ("POST", "/api/interrupts"): _interrupt,
    ("POST", "/api/stop-all"): _stop_all,
    ("POST", "/api/attachments"): plain(
        "/api/attachments",
        {"filename": "dot.png", "media_type": "image/png", "data_base64": base64.b64encode(PNG).decode()},
    ),
    ("POST", "/api/approvals/{approval_id}/resume"): patched(_resume, _scripted_model),
    ("GET", "/api/diagnostics/export"): plain("/api/diagnostics/export"),
    ("POST", "/api/connector-store/{connector_id}/actions"): patched(_connector_write, _vault_key),
}
