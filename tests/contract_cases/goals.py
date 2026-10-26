"""Durable goals and execution profiles (PA-D01, PA-D02)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from tests.contract_cases.base import Call, Cases, Seed, patched, plain

_MODEL = ("anthropic-hosted", "claude-haiku-4-5-20251001")
_PLAN = {
    "title": "Contract goal",
    "model_profile": _MODEL[0],
    "model": _MODEL[1],
    "criteria": [{"text": "It is done", "validator": "steps_finish"}],
    "steps": [{"title": "Do it", "instruction": "Write one line.", "criteria": [0]}],
}


def _allowed_chain(monkeypatch: Any) -> None:
    from raiker.goals import profiles
    from raiker.goals.profiles import ChainEntry

    monkeypatch.setattr(
        profiles, "model_chain",
        lambda _store, _owner, profile, *_model: [ChainEntry("anthropic-hosted", "anthropic", False, profile.allows(provider="anthropic", local=False))],
    )


def _profile(client: TestClient, h: dict[str, str]) -> str:
    _configure_model(client, h)
    return str(client.post("/api/execution-profiles", json={"template": "balanced"}, headers=h).json()["profile"]["profile_id"])


def _configure_model(client: TestClient, h: dict[str, str]) -> None:
    from raiker.storage.sqlite import SQLiteStore

    me = client.get("/api/auth/whoami", headers=h).json()
    workspace = client.app.state.workspace_root  # type: ignore[attr-defined]
    SQLiteStore(workspace).save_configured_model(str(me["principal_id"]), *_MODEL)


def _goal(client: TestClient, h: dict[str, str], *, to: str = "draft") -> dict[str, Any]:
    goal: dict[str, Any] = client.post("/api/goals", json=_PLAN, headers=h).json()
    steps = {"ready": ["accept"], "running": ["accept", "start"], "paused": ["accept", "start", "pause"]}.get(to, [])
    if steps:
        _profile(client, h)
    for action in steps:
        goal = client.post(f"/api/goals/{goal['goal_id']}/{action}", json={"base_revision": goal["revision"]}, headers=h).json()
    return goal


def _action(action: str, *, at: str) -> Seed:
    def seed(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
        if action == "accept":
            _profile(client, h)
        goal = _goal(client, h, to=at)
        return f"/api/goals/{goal['goal_id']}/{action}", {"base_revision": goal["revision"]}

    return patched(seed, _allowed_chain)


def _read(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    return f"/api/goals/{_goal(client, h)['goal_id']}"


def _plan(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    goal = _goal(client, h)
    return f"/api/goals/{goal['goal_id']}/plan", {**_PLAN, "base_revision": goal["revision"], "title": "Edited"}


def _confirm(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    goal = _goal(client, h, to="running")
    return f"/api/goals/{goal['goal_id']}/criteria/c1/confirm", {"base_revision": goal["revision"], "note": "ok"}


def _listed(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    _profile(client, h)
    _goal(client, h)
    return "/api/goals"


def _profiles(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    _profile(client, h)
    return "/api/execution-profiles"


def _update_profile(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    return f"/api/execution-profiles/{_profile(client, h)}", {"base_version": 1, "max_step_runs": 4}


def _active(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    return "/api/execution-profiles/active", {"profile_id": _profile(client, h)}


def _project(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    profile_id = _profile(client, h)
    project_id = client.post("/api/projects", json={"name": "Contract"}, headers=h).json()["project_id"]
    return f"/api/execution-profiles/projects/{project_id}", {"profile_id": profile_id}


def _two_chats(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    """QUI-F03 — the same aim in two conversations."""
    from raiker.storage.sqlite import SQLiteStore

    store = SQLiteStore(ws)
    principal = client.get("/api/auth/whoami", headers=h).json()["principal_id"]
    user_id = store.principal_user_id(principal)
    for session_id, prompt in (
        ("sess_aim_a", "Find a marathon training plan for the Berlin marathon"),
        ("sess_aim_b", "Adjust my Berlin marathon training plan for September"),
    ):
        store.create_session(session_id, str(ws), title=prompt[:30], user_id=user_id)
        store.insert_turn(session_id, f"turn_{session_id}", prompt)
        store.complete_turn(f"turn_{session_id}", "completed", "Done.")
    return "/api/goals/suggestion?session_id=sess_aim_b"


CASES: Cases = {
    ("GET", "/api/goals/suggestion"): _two_chats,
    ("POST", "/api/goals/suggestion/dismiss"): plain("/api/goals/suggestion/dismiss", {"keywords": ["berlin", "marathon", "training"]}),
    ("GET", "/api/goals"): _listed,
    ("POST", "/api/goals"): plain("/api/goals", _PLAN),
    ("GET", "/api/goals/{goal_id}"): _read,
    ("PUT", "/api/goals/{goal_id}/plan"): _plan,
    ("POST", "/api/goals/{goal_id}/accept"): _action("accept", at="draft"),
    ("POST", "/api/goals/{goal_id}/start"): _action("start", at="ready"),
    ("POST", "/api/goals/{goal_id}/pause"): _action("pause", at="running"),
    ("POST", "/api/goals/{goal_id}/resume"): _action("resume", at="paused"),
    ("POST", "/api/goals/{goal_id}/stop"): _action("stop", at="running"),
    ("POST", "/api/goals/{goal_id}/archive"): _action("archive", at="draft"),
    ("POST", "/api/goals/{goal_id}/criteria/{criterion_id}/confirm"): patched(_confirm, _allowed_chain),
    ("GET", "/api/execution-profiles"): _profiles,
    ("POST", "/api/execution-profiles"): plain("/api/execution-profiles", {"template": "private_local"}),
    ("PUT", "/api/execution-profiles/{profile_id}"): _update_profile,
    ("PUT", "/api/execution-profiles/active"): _active,
    ("PUT", "/api/execution-profiles/projects/{project_id}"): _project,
}
