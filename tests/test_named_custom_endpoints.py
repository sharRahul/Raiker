"""Hermes Agent's named custom endpoints, as four OpenAI-compatible slots.

Each slot is its own profile — its own endpoint, key, catalogue, readiness and
egress decision — and carries the owner's own name for it. The endpoint's
location (this machine, a private network, the internet) is classified from
its address, so a home-lab server needs the home-lab gate and a hosted one the
hosted gate, exactly as for the single endpoint before.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.auth.vault_key_file import VAULT_KEY_ENV
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.models.connections import get_model_connection
from raiker.models.factory import ModelProviderFactory
from raiker.models.registry import ModelProfileRegistry, profile_with_model
from raiker.storage.sqlite import SQLiteStore

SLOTS = [
    "generic-openai-compatible",
    "generic-openai-compatible-2",
    "generic-openai-compatible-3",
    "generic-openai-compatible-4",
]
OWNER = "principal_owner"


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv(VAULT_KEY_ENV, Fernet.generate_key().decode())
    ws = tmp_path / "named"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


@pytest.fixture
def auth(workspace: Path) -> dict[str, str]:
    raw, _ = ApiSessionStore(workspace).create_session(OWNER)
    return {"Authorization": f"Bearer {raw}"}


def test_four_independent_slots_ship() -> None:
    registry = ModelProfileRegistry.load()
    profiles = [registry.resolve_profile_id(slot) for slot in SLOTS]
    assert {profile.provider for profile in profiles} == {"openai-compatible"}
    assert len({profile.profile_id for profile in profiles}) == 4


def test_each_slot_keeps_its_own_name_endpoint_and_key(
    client: TestClient, auth: dict[str, str], workspace: Path
) -> None:
    for slot, name, port in [(SLOTS[0], "Home GPU", 8000), (SLOTS[1], "  Work \n vLLM ", 8001)]:
        resp = client.put(
            f"/api/models/{slot}/connection",
            json={"endpoint": f"http://127.0.0.1:{port}/v1", "label": name},
            headers=auth,
        )
        assert resp.status_code == 200, resp.text
    store = SQLiteStore(workspace)
    first = get_model_connection(store, OWNER, SLOTS[0]) or {}
    second = get_model_connection(store, OWNER, SLOTS[1]) or {}
    assert (first["label"], first["endpoint"]) == ("Home GPU", "http://127.0.0.1:8000/v1")
    # One line of display text, however it was typed.
    assert (second["label"], second["endpoint"]) == ("Work vLLM", "http://127.0.0.1:8001/v1")

    cards = {p["profile_id"]: p for p in client.get("/api/models", headers=auth).json()["profiles"]}
    assert cards[SLOTS[0]]["connection_label"] == "Home GPU"
    assert cards[SLOTS[1]]["connection_label"] == "Work vLLM"
    assert cards[SLOTS[2]]["connection_label"] == ""


def test_renaming_alone_keeps_the_key_and_re_pasting_the_key_keeps_the_name(
    client: TestClient, auth: dict[str, str], workspace: Path
) -> None:
    slot = SLOTS[2]
    client.put(
        f"/api/models/{slot}/connection",
        json={"endpoint": "http://127.0.0.1:8002/v1", "api_key": "first", "label": "Lab"},
        headers=auth,
    )
    client.put(f"/api/models/{slot}/connection", json={"label": "Lab box"}, headers=auth)
    saved = get_model_connection(SQLiteStore(workspace), OWNER, slot) or {}
    assert (saved["api_key"], saved["label"]) == ("first", "Lab box")

    client.put(
        f"/api/models/{slot}/connection",
        json={"endpoint": "http://127.0.0.1:8002/v1", "api_key": "second"},
        headers=auth,
    )
    saved = get_model_connection(SQLiteStore(workspace), OWNER, slot) or {}
    assert (saved["api_key"], saved["label"]) == ("second", "Lab box")


def test_a_name_longer_than_forty_characters_is_refused(client: TestClient, auth: dict[str, str]) -> None:
    resp = client.put(f"/api/models/{SLOTS[0]}/connection", json={"label": "x" * 41}, headers=auth)
    assert resp.status_code == 422


def test_where_a_slot_points_decides_which_gate_it_needs() -> None:
    profile = profile_with_model(ModelProfileRegistry.load().resolve_profile_id(SLOTS[3]), "m")
    local = ModelProviderFactory(connection={"endpoint": "http://127.0.0.1:30000/v1"}).resolve(profile)
    assert local.endpoint_kind not in {"private_network", "remote_hosted"}
    with pytest.raises(Exception, match="private_network"):
        ModelProviderFactory(connection={"endpoint": "http://192.168.1.20:8000/v1"}).resolve(profile)
    with pytest.raises(Exception, match="hosted"):
        ModelProviderFactory(connection={"endpoint": "https://gpu.example.com/v1"}).resolve(profile)
