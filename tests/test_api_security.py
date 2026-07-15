from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.storage.sqlite import SQLiteStore

SK_OPENAI = "sk-proj-FakeTestKey00000000000000000000000000000000"
BEARER_FAKE = "bearer fp_0000000000000000000000000000000000000000"


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "sec_ws"
    ws.mkdir()
    return ws


@pytest.fixture
def bootstrapped_ws(temp_workspace: Path) -> Path:
    bootstrap_owner("owner", "Owner", workspace_root=temp_workspace)
    return temp_workspace


@pytest.fixture
def app(bootstrapped_ws: Path) -> FastAPI:
    return create_app(bootstrapped_ws)


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture
def owner_token(bootstrapped_ws: Path) -> str:
    store = ApiSessionStore(bootstrapped_ws)
    raw, _ = store.create_session("principal_owner")
    return raw


# ── 1. Unauthenticated → 401 ────────────────────────────────────────────────


class TestUnauthenticated:
    def test_no_header_returns_401(self, client: TestClient) -> None:
        for path in ("/api/runtime-mode", "/api/capability-gates", "/api/runtime-readiness"):
            resp = client.get(path)
            assert resp.status_code == 401, f"{path} should return 401"

    def test_bad_token_returns_401(self, client: TestClient) -> None:
        resp = client.get(
            "/api/capability-gates",
            headers={"Authorization": "Bearer invalidtoken123"},
        )
        assert resp.status_code == 401

    def test_malformed_header_returns_401(self, client: TestClient) -> None:
        resp = client.get(
            "/api/capability-gates",
            headers={"Authorization": "NotBearer xyz"},
        )
        assert resp.status_code == 401


# ── 2. AI-principal flip → 403 ──────────────────────────────────────────────


class TestAiPrincipalDenied:
    @pytest.fixture
    def ai_token(self, bootstrapped_ws: Path) -> str:
        _create_ai_principal(bootstrapped_ws)
        store = ApiSessionStore(bootstrapped_ws)
        raw, _ = store.create_session("principal_ai_assistant")
        return raw

    def test_ai_cannot_activate_runtime_mode(self, client: TestClient, ai_token: str) -> None:
        resp = client.post(
            "/api/runtime-mode/activate",
            json={"mode_name": "local_single_user_runtime", "reason": "ai-try"},
            headers={"Authorization": f"Bearer {ai_token}"},
        )
        assert resp.status_code == 403

    def test_ai_cannot_flip_capability_gate(self, client: TestClient, ai_token: str) -> None:
        resp = client.post(
            "/api/capability-gates/admin_mutation/set",
            json={"target_state": "enabled_policy_gated", "reason": "ai-try"},
            headers={"Authorization": f"Bearer {ai_token}"},
        )
        assert resp.status_code == 403
        detail = _detail(resp.json())
        assert not detail.get("ok", True)

    def test_ai_cannot_disable_runtime(self, client: TestClient, ai_token: str) -> None:
        resp = client.post(
            "/api/runtime-mode/disable",
            json={"reason": "ai-try"},
            headers={"Authorization": f"Bearer {ai_token}"},
        )
        assert resp.status_code == 403

    def test_ai_can_read_gates(self, client: TestClient, ai_token: str) -> None:
        resp = client.get(
            "/api/capability-gates",
            headers={"Authorization": f"Bearer {ai_token}"},
        )
        assert resp.status_code == 200


# ── 3. Redaction guard ──────────────────────────────────────────────────────


class TestRedactionGuard:
    def test_response_bodies_have_no_secrets(self, client: TestClient, owner_token: str) -> None:
        paths = (
            ("GET", "/api/runtime-mode", None),
            ("GET", "/api/capability-gates", None),
            ("GET", "/api/runtime-readiness", None),
        )
        for method, path, _body in paths:
            resp = client.request(
                method, path,
                headers={"Authorization": f"Bearer {owner_token}"},
            )
            assert resp.status_code in (200, 403), f"{method} {path} failed"
            _assert_no_secrets_in_body(resp.json())

    def test_redaction_masks_secret_like_strings(self) -> None:
        from raiker.api.redaction import redact_response_body
        body = {
            "api_key": SK_OPENAI,
            "nested": {"token": BEARER_FAKE},
            "safe": "hello world",
            "items": [
                {"password": "supersecret123"},
                {"email": "test@example.com"},
            ],
        }
        redacted = redact_response_body(body)
        assert redacted["api_key"] != SK_OPENAI
        assert redacted["nested"]["token"] != BEARER_FAKE
        assert redacted["safe"] == "hello world"
        assert redacted["items"][0]["password"] != "supersecret123"
        assert redacted["items"][1]["email"] != "test@example.com"

    def test_no_secret_keys_in_response(self, client: TestClient, owner_token: str) -> None:
        resp = client.get(
            "/api/capability-gates",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert resp.status_code == 200
        _assert_no_secrets_in_body(resp.json())


# ── 4. Token revocation ─────────────────────────────────────────────────────


class TestTokenRevocation:
    def test_revoked_token_returns_401(self, bootstrapped_ws: Path, app: FastAPI) -> None:
        store = ApiSessionStore(bootstrapped_ws)
        raw, session = store.create_session("principal_owner")
        store.revoke_session(session.session_id)
        client = TestClient(app)
        resp = client.get(
            "/api/capability-gates",
            headers={"Authorization": f"Bearer {raw}"},
        )
        assert resp.status_code == 401


# ── 5. Cross-session leakage ─────────────────────────────────────────────────


class TestCrossSessionLeakage:
    def test_session_bound_to_principal(self, bootstrapped_ws: Path) -> None:
        store = ApiSessionStore(bootstrapped_ws)
        raw_a, session_a = store.create_session("principal_owner")
        _create_second_principal(bootstrapped_ws, "principal_alice")
        raw_b, session_b = store.create_session("principal_alice")

        assert session_a.principal_id == "principal_owner"
        assert session_b.principal_id == "principal_alice"

        s_a = store.get_by_token(raw_a)
        s_b = store.get_by_token(raw_b)
        assert s_a is not None
        assert s_b is not None
        assert s_a.principal_id == "principal_owner"
        assert s_b.principal_id == "principal_alice"
        assert s_a.principal_id != s_b.principal_id

    def test_cannot_impersonate_via_as_principal(self, client: TestClient, bootstrapped_ws: Path) -> None:
        _create_second_principal(bootstrapped_ws, "principal_alice")
        store = ApiSessionStore(bootstrapped_ws)
        raw_alice, _ = store.create_session("principal_alice")

        resp = client.post(
            "/api/capability-gates/admin_mutation/set",
            json={"target_state": "enabled_policy_gated", "reason": "x", "as_principal": "principal_owner"},
            headers={"Authorization": f"Bearer {raw_alice}"},
        )
        assert resp.status_code == 403


# ── 6. Approval bypass attempt ──────────────────────────────────────────────


class TestApprovalBypass:
    def test_dangerous_cap_denied_by_authority(self, client: TestClient, owner_token: str, bootstrapped_ws: Path) -> None:
        _activate_runtime(client, owner_token)
        resp = client.post(
            "/api/capability-gates/shell_execution/set",
            json={"target_state": "enabled_policy_gated", "reason": "try-bypass"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert resp.status_code == 403
        detail = _detail(resp.json())
        assert not detail.get("ok", True)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _detail(body: dict[str, Any]) -> dict[str, Any]:
    d = body.get("detail", body)
    if isinstance(d, dict):
        return d
    return body


def _assert_no_secrets_in_body(body: Any) -> None:
    from raiker.api.redaction import assert_no_secrets_in_body as _check
    _check(body)


def _create_ai_principal(workspace_root: Path) -> None:
    from raiker.contracts.ids import utc_now
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


def _create_second_principal(workspace_root: Path, principal_id: str) -> None:
    from raiker.contracts.ids import utc_now
    store = SQLiteStore(workspace_root)
    now = utc_now()
    with store.connect() as connection:
        connection.execute(
            """INSERT OR IGNORE INTO principals
               (principal_id, principal_type, display_name, role_ids, domain_scopes,
                max_runtime_mode, created_at, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                principal_id,
                "human",
                "Alice",
                '[]',
                "[]",
                "development_preview",
                now,
                1,
            ),
        )


def _activate_runtime(client: TestClient, token: str) -> None:
    resp = client.post(
        "/api/runtime-mode/activate",
        json={"mode_name": "local_single_user_runtime", "reason": "test"},
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code != 200:
        # Already active is fine
        pass
