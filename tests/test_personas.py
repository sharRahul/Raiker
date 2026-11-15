"""ADR-0005 — composer personas narrow a turn and never widen it."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker import personas
from raiker.api.app import create_app
from raiker.api.routes_prompts import _build_envelope
from raiker.api.schemas import PromptRequest
from raiker.storage.sqlite import SQLiteStore

ANALYST = {
    "name": "DataAnalyst",
    "description": "Reads numbers carefully.",
    "instructions": "Answer with the figures first, then one sentence of reading.",
    "tool_ceiling": ["files", "memory"],
}


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(tmp_path))


def _register(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/register", json={"username": "owner", "password": "a-long-password-1"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def _store(client: TestClient) -> SQLiteStore:
    return SQLiteStore(Path(client.app.state.workspace_root))  # type: ignore[attr-defined]


def test_a_ceiling_only_ever_adds_deny_entries() -> None:
    modes = personas.ceiling_capability_modes(["files"], {"web_fetch": "ask", "shell_execution": "ask"})
    assert set(modes.values()) == {"deny"}
    # Everything the turn had stays, and tightens; nothing becomes allow.
    assert modes["web_fetch"] == "deny" and modes["shell_execution"] == "deny"
    assert "file_write_execution" not in modes
    # Inherit: the turn's own map, untouched.
    assert personas.ceiling_capability_modes(None, {"web_fetch": "ask"}) == {"web_fetch": "ask"}


def test_every_ceiling_is_a_subset_of_the_turns_tools() -> None:
    every = set().union(*(set(family["tools"]) for family in personas.FAMILIES.values()))
    for name in personas.FAMILIES:
        withheld = personas.excluded_tools([name])
        assert withheld <= every
        assert not withheld & set(personas.FAMILIES[name]["tools"])
    assert personas.excluded_tools(None) == frozenset()
    assert personas.excluded_tools([]) == every


def test_an_unknown_family_is_refused() -> None:
    with pytest.raises(personas.PersonaError, match="unknown_tool_family:admin"):
        personas.validate_ceiling(["files", "admin"])
    assert personas.validate_ceiling(["memory", "files", "files"]) == ("files", "memory")


def test_the_routes_add_list_update_and_remove_a_persona(client: TestClient) -> None:
    h = _register(client)
    made = client.post("/api/personas", json=ANALYST, headers=h)
    assert made.status_code == 201, made.text
    persona = made.json()
    assert persona["name"] == "DataAnalyst" and persona["tool_ceiling"] == ["files", "memory"]
    listed = client.get("/api/personas", headers=h).json()
    assert [row["name"] for row in listed["personas"]] == ["DataAnalyst"]
    assert [row["family"] for row in listed["families"]] == list(personas.FAMILIES)
    again = client.post("/api/personas", json={**ANALYST, "name": "dataanalyst"}, headers=h)
    assert again.status_code == 409 and again.json()["detail"]["reason_code"] == "persona_name_taken"
    changed = client.put(
        f"/api/personas/{persona['persona_id']}", json={**ANALYST, "instructions": "Shorter."}, headers=h
    )
    assert changed.status_code == 200 and changed.json()["instructions_sha256"] != persona["instructions_sha256"]
    assert client.delete(f"/api/personas/{persona['persona_id']}", headers=h).json()["ok"] is True
    assert client.delete(f"/api/personas/{persona['persona_id']}", headers=h).status_code == 404


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("name", "Data Analyst", "invalid_persona_name"),
        ("instructions", "  ", "persona_instructions_required"),
        ("instructions", "x" * 4001, "persona_instructions_too_long"),
        ("tool_ceiling", ["root"], "unknown_tool_family:root"),
    ],
)
def test_an_invalid_persona_is_refused_by_name(client: TestClient, field: str, value: object, code: str) -> None:
    h = _register(client)
    response = client.post("/api/personas", json={**ANALYST, field: value}, headers=h)
    assert response.status_code == 422
    assert response.json()["detail"]["reason_code"] == code


def test_the_envelope_carries_the_persona_and_its_narrowing(client: TestClient) -> None:
    h = _register(client)
    persona_id = client.post("/api/personas", json=ANALYST, headers=h).json()["persona_id"]
    store = _store(client)
    principal = client.get("/api/auth/whoami", headers=h).json()["principal_id"]
    persona = personas.get_persona(store, store.principal_user_id(principal) or "", persona_id)
    assert persona is not None
    envelope = _build_envelope(
        PromptRequest(text="hello", persona_id=persona_id), principal, store.paths.workspace_root, persona
    )
    record = envelope.prompt.metadata["persona"]
    assert record["name"] == "DataAnalyst" and record["instructions_sha256"] == persona.instructions_sha256
    assert envelope.options.capability_modes["web_fetch"] == "deny"
    assert envelope.options.capability_modes["shell_execution"] == "deny"
    assert "memory_write_execution" not in envelope.options.capability_modes


def test_a_turn_naming_a_persona_never_issued_is_refused(client: TestClient) -> None:
    h = _register(client)
    response = client.post("/api/prompts", json={"text": "hi", "persona_id": "persona_nope"}, headers=h)
    assert response.status_code == 404
    assert response.json()["detail"]["reason_code"] == "unknown_persona"


def test_another_accounts_persona_cannot_be_read_or_changed(tmp_path: Path) -> None:
    first = TestClient(create_app(tmp_path))
    h = _register(first)
    persona_id = first.post("/api/personas", json=ANALYST, headers=h).json()["persona_id"]
    store = SQLiteStore(tmp_path)
    assert personas.get_persona(store, "user_someone_else", persona_id) is None
    assert personas.update_persona(store, "user_someone_else", persona_id, ANALYST) is None
    assert personas.delete_persona(store, "user_someone_else", persona_id) is False


def test_the_system_message_sits_beneath_raikers_rules() -> None:
    persona = personas.Persona(
        "persona_x", "Copywriter", "", "Write warmly.", None, None, ("web",), "t", "t"
    )
    text = personas.system_message(persona)
    assert "cannot restate, relax or override" in text and "grant no authority" in text
    assert "This persona's tools: Web." in text and text.endswith("Write warmly.")


def test_a_withheld_tool_proposed_anyway_is_rejected(tmp_path: Path) -> None:
    from raiker.models.contracts import ToolCallProposal
    from raiker.models.tool_call_validation import ToolCallRejected
    from raiker.runtime.orchestrator import RuntimeOrchestrator

    orchestrator = RuntimeOrchestrator.__new__(RuntimeOrchestrator)
    orchestrator._persona_excluded_tools = personas.excluded_tools(["files"])
    with pytest.raises(ToolCallRejected, match="persona_tool_ceiling:web_search"):
        orchestrator._validated_call(ToolCallProposal(call_id="c1", tool_name="web_search", arguments={"query": "x"}))
    action = orchestrator._validated_call(
        ToolCallProposal(call_id="c2", tool_name="read_file", arguments={"path": "a.txt"})
    )
    assert action.tool_name == "read_file"


def test_a_turns_persona_is_read_back_with_whether_it_is_still_current(client: TestClient) -> None:
    h = _register(client)
    persona = client.post("/api/personas", json=ANALYST, headers=h).json()
    store = _store(client)
    principal = client.get("/api/auth/whoami", headers=h).json()["principal_id"]
    store.create_session("sess_p", str(store.paths.workspace_root), title="P", user_id=store.principal_user_id(principal))
    store.insert_turn("sess_p", "turn_p", "Numbers?")
    store.record_turn_persona(
        turn_id="turn_p", session_id="sess_p", persona_id=persona["persona_id"], name="DataAnalyst",
        instructions_sha256=persona["instructions_sha256"],
    )
    turn = client.get("/api/sessions/sess_p", headers=h).json()["turns"][0]
    assert turn["persona"] == {
        "persona_id": persona["persona_id"], "name": "DataAnalyst",
        "instructions_sha256": persona["instructions_sha256"], "current": True,
    }
    client.put(f"/api/personas/{persona['persona_id']}", json={**ANALYST, "instructions": "Changed."}, headers=h)
    assert client.get("/api/sessions/sess_p", headers=h).json()["turns"][0]["persona"]["current"] is False
    # Deleting the conversation takes its persona record with it.
    assert store.delete_sessions(["sess_p"]) is True
    assert store._rows("SELECT * FROM turn_personas WHERE session_id = 'sess_p'") == []


def test_a_search_never_offers_a_tool_the_persona_withholds() -> None:
    from raiker.models.tool_projection import search_tools

    withheld = personas.excluded_tools(["memory"])
    found = search_tools("weather in Paris", withheld=withheld)
    assert found["matched"] == 0 and "weather_lookup" in str(found["withheld"])
    assert "persona leaves them out" in str(found["note"])
    everything = search_tools("", withheld=withheld)
    assert "web_search" not in str(everything["tools"]) and "weather_lookup" not in str(everything)
    assert search_tools("weather in Paris")["matched"]  # without a persona it is offered
