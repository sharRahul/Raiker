"""HTTP API coverage for the per-capability decision-mode routes.

The decision-mode *logic* is exercised at the service/router layer in
`tests/test_phase_5_decision_modes.py`. This module pins the REST surface that
exposes it — `GET /api/capability-modes/{cap}` and the four setters
`.../ask`, `.../allow`, `.../auto`, `.../deny` — so the human-in-control API
contract (default `ask`, human-only setter, permissive-requires-executor) can
never silently regress.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import utc_now
from raiker.storage.sqlite import SQLiteStore

# Real Tier-1 executor -> permissive modes (allow/auto) are selectable.
_REAL_CAP = "file_write_execution"
# No real executor -> permissive modes must be refused, deny/ask still allowed.
_SENSITIVE_CAP = "medical_runtime"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "api_decision_modes"
    ws.mkdir()
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    return ws


@pytest.fixture
def app(workspace: Path) -> FastAPI:
    return create_app(workspace)


@pytest.fixture
def owner_token(workspace: Path) -> str:
    raw, _ = ApiSessionStore(workspace).create_session("principal_rahul")
    return raw


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_ai_principal(workspace_root: Path) -> str:
    store = SQLiteStore(workspace_root)
    now = utc_now()
    with store.connect() as connection:
        connection.execute(
            """INSERT OR IGNORE INTO principals
               (principal_id, principal_type, display_name, role_ids, domain_scopes,
                max_runtime_mode, created_at, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "principal_ai_assistant",
                "ai_agent",
                "AI Assistant",
                '["assistant"]',
                "[]",
                "development_preview",
                now,
                1,
            ),
        )
    return "principal_ai_assistant"


class TestDefaultAndRead:
    def test_default_mode_is_ask(self, client: TestClient, owner_token: str) -> None:
        resp = client.get(f"/api/capability-modes/{_REAL_CAP}", headers=_auth(owner_token))
        assert resp.status_code == 200
        assert resp.json()["decision_mode"] == "ask"

    def test_read_requires_auth(self, client: TestClient) -> None:
        resp = client.get(f"/api/capability-modes/{_REAL_CAP}")
        assert resp.status_code == 401


class TestOwnerCanSetEveryMode:
    @pytest.mark.parametrize("mode", ["allow", "auto", "deny", "ask"])
    def test_owner_sets_mode(self, client: TestClient, owner_token: str, mode: str) -> None:
        resp = client.post(
            f"/api/capability-modes/{_REAL_CAP}/{mode}",
            json={"reason": f"set-{mode}"},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["ok"] is True
        assert body["capability"] == _REAL_CAP
        assert body["decision_mode"] == mode

        read = client.get(f"/api/capability-modes/{_REAL_CAP}", headers=_auth(owner_token))
        assert read.json()["decision_mode"] == mode

    def test_allow_round_trips_after_ask(self, client: TestClient, owner_token: str) -> None:
        # allow (permissive) then back to ask (the safe default) both succeed.
        assert client.post(
            f"/api/capability-modes/{_REAL_CAP}/allow", json={}, headers=_auth(owner_token)
        ).status_code == 200
        assert client.post(
            f"/api/capability-modes/{_REAL_CAP}/ask", json={}, headers=_auth(owner_token)
        ).status_code == 200
        read = client.get(f"/api/capability-modes/{_REAL_CAP}", headers=_auth(owner_token))
        assert read.json()["decision_mode"] == "ask"


class TestSafetyFloors:
    def test_permissive_mode_requires_executor(self, client: TestClient, owner_token: str) -> None:
        # A sensitive/no-executor domain can never be relaxed into acting.
        resp = client.post(
            f"/api/capability-modes/{_SENSITIVE_CAP}/allow",
            json={"reason": "try-relax"},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 403
        detail = resp.json()["detail"]
        assert detail["ok"] is False
        assert detail["reason_code"] == f"decision_mode_requires_executor:{_SENSITIVE_CAP}"

    def test_deny_always_selectable_on_sensitive(self, client: TestClient, owner_token: str) -> None:
        # deny only tightens, so it is allowed even without a real executor.
        resp = client.post(
            f"/api/capability-modes/{_SENSITIVE_CAP}/deny",
            json={"reason": "lock-it"},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["decision_mode"] == "deny"


class TestAiCannotSetMode:
    def test_ai_principal_refused_403(self, workspace: Path, app: FastAPI) -> None:
        ai_id = _create_ai_principal(workspace)
        raw, _ = ApiSessionStore(workspace).create_session(ai_id)
        client = TestClient(app)
        resp = client.post(
            f"/api/capability-modes/{_REAL_CAP}/allow",
            json={"reason": "ai-tries-to-self-authorize"},
            headers=_auth(raw),
        )
        # The AI principal is refused before the mode is ever changed. The block
        # lands at the gate-operation authorization boundary, so a reason
        # mentioning the gate-operation refusal is what surfaces.
        assert resp.status_code == 403
        detail = resp.json()["detail"]
        assert detail["ok"] is False
        assert "gate operations" in detail["reason_code"]

        # And the mode is unchanged — still the safe default.
        owner_raw, _ = ApiSessionStore(workspace).create_session("principal_rahul")
        read = client.get(f"/api/capability-modes/{_REAL_CAP}", headers=_auth(owner_raw))
        assert read.json()["decision_mode"] == "ask"

    def test_set_requires_auth(self, client: TestClient) -> None:
        resp = client.post(f"/api/capability-modes/{_REAL_CAP}/allow", json={})
        assert resp.status_code == 401
