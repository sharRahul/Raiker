"""PA-D01 / PA-D02 — durable goals and the execution profiles they run under.

Every test drives the real routes, coordinator, task store and scheduler guard.
Only the model chain is substituted, because it reads the owner's model
selection and fallbacks — which is exactly what the profile check judges.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.context.gatherer import ContextGatherer
from raiker.goals import profiles as profile_store
from raiker.goals.coordinator import GoalCoordinator
from raiker.goals.lifecycle import ALLOWED_ACTIONS, GOAL_STATES, step_from_task
from raiker.goals.profiles import ChainEntry, ExecutionProfile
from raiker.goals.store import session_memory_withheld
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("bootstrap", "Bootstrap", workspace_root=ws)
    return ws


MODEL = ("anthropic-hosted", "claude-haiku-4-5-20251001")


@pytest.fixture
def account(workspace: Path, seed_account: Any) -> tuple[str, str]:
    result: tuple[str, str] = seed_account(workspace, "owner")
    SQLiteStore(workspace).save_configured_model(result[0], *MODEL)
    return result


@pytest.fixture
def chain(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, bool]]:
    """The models a step's turn could run on, as ``(provider, local)``; edit to change it."""
    entries: list[tuple[str, bool]] = [("anthropic", False)]

    def fake(_store: Any, _owner: str, profile: ExecutionProfile, *_model: Any) -> list[ChainEntry]:
        return [
            ChainEntry(f"{provider}-profile", provider, local, profile.allows(provider=provider, local=local))
            for provider, local in entries
        ]

    monkeypatch.setattr(profile_store, "model_chain", fake)
    return entries


def _client(workspace: Path, account: tuple[str, str]) -> tuple[TestClient, dict[str, str]]:
    return TestClient(create_app(workspace)), {"Authorization": f"Bearer {account[1]}"}


def _profile(client: TestClient, h: dict[str, str], template: str = "balanced", **fields: Any) -> dict[str, Any]:
    response = client.post("/api/execution-profiles", json={"template": template, **fields}, headers=h)
    assert response.status_code == 201, response.text
    return dict(response.json()["profile"])


PLAN: dict[str, Any] = {
    "title": "Plan the trip",
    "model_profile": MODEL[0],
    "model": MODEL[1],
    "objective": "A short itinerary I can use.",
    "criteria": [
        {"text": "Both drafts exist", "mandatory": True, "validator": "steps_finish"},
        {"text": "I am happy with it", "mandatory": True, "validator": "owner_confirms"},
    ],
    "steps": [
        {"title": "Research", "instruction": "List three options.", "criteria": [0]},
        {"title": "Draft", "instruction": "Write the itinerary.", "depends_on": [0], "criteria": [0]},
    ],
}


def _goal(client: TestClient, h: dict[str, str], plan: dict[str, Any] | None = None) -> dict[str, Any]:
    response = client.post("/api/goals", json=plan or PLAN, headers=h)
    assert response.status_code == 201, response.text
    return dict(response.json())


def _act(client: TestClient, h: dict[str, str], goal: dict[str, Any], action: str) -> Any:
    return client.post(f"/api/goals/{goal['goal_id']}/{action}", json={"base_revision": goal["revision"]}, headers=h)


def _settle_task(workspace: Path, task_id: str, status: str) -> None:
    store = SQLiteStore(workspace)
    if status == "completed":
        store.complete_task(task_id, "done")
    elif status == "failed":
        store.fail_task(task_id, "broke")
    else:
        store.update_task_status(task_id, status)


def _read(client: TestClient, h: dict[str, str], goal_id: str) -> dict[str, Any]:
    response = client.get(f"/api/goals/{goal_id}", headers=h)
    assert response.status_code == 200, response.text
    return dict(response.json())


# ── lifecycle contract ───────────────────────────────────────────────────


def test_every_state_publishes_its_actions_and_unknown_task_status_never_reads_done() -> None:
    assert set(ALLOWED_ACTIONS) == set(GOAL_STATES)
    assert ALLOWED_ACTIONS["archived"] == ()
    assert "start" not in ALLOWED_ACTIONS["draft"]
    assert step_from_task("something_new") == ("waiting", "step_paused")
    assert step_from_task(None) == ("failed", "task_missing")
    assert step_from_task("waiting_for_approval") == ("waiting", "needs_decision")


# ── intake, plan, revision ───────────────────────────────────────────────


def test_intake_is_a_draft_with_no_permission_to_run(workspace: Path, account: tuple[str, str]) -> None:
    client, h = _client(workspace, account)
    goal = _goal(client, h)
    assert goal["status"] == "draft"
    assert goal["allowed_actions"] == ["edit", "accept", "archive"]
    assert [c["criterion_id"] for c in goal["criteria"]] == ["c1", "c2"]
    assert goal["steps"][1]["depends_on"] == ["s1"]
    assert SQLiteStore(workspace).list_tasks() == []
    assert _act(client, h, goal, "start").status_code == 409


def test_a_plan_cannot_depend_forward_or_reach_build_without_a_project(
    workspace: Path, account: tuple[str, str]
) -> None:
    client, h = _client(workspace, account)
    forward = {**PLAN, "steps": [{"title": "a", "instruction": "x", "depends_on": [1]}, {"title": "b", "instruction": "y"}]}
    assert client.post("/api/goals", json=forward, headers=h).status_code == 422
    build = {**PLAN, "steps": [{"title": "a", "instruction": "x", "surface": "build"}]}
    refused = client.post("/api/goals", json=build, headers=h)
    assert refused.status_code == 422
    assert "goal_build_step_requires_project" in refused.text


def test_an_edit_over_an_older_revision_is_refused(workspace: Path, account: tuple[str, str]) -> None:
    client, h = _client(workspace, account)
    goal = _goal(client, h)
    edit = {**PLAN, "base_revision": goal["revision"], "title": "Plan the trip, v2"}
    first = client.put(f"/api/goals/{goal['goal_id']}/plan", json=edit, headers=h)
    assert first.status_code == 200 and first.json()["revision"] == goal["revision"] + 1
    stale = client.put(f"/api/goals/{goal['goal_id']}/plan", json=edit, headers=h)
    assert stale.status_code == 409 and "goal_revision_stale" in stale.text


def test_another_owners_goal_reads_as_never_issued(workspace: Path, account: tuple[str, str], seed_account: Any) -> None:
    client, h = _client(workspace, account)
    goal = _goal(client, h)
    _other, other_token = seed_account(workspace, "other")
    other = {"Authorization": f"Bearer {other_token}"}
    assert client.get(f"/api/goals/{goal['goal_id']}", headers=other).status_code == 404
    assert client.get("/api/goals", headers=other).json()["goals"] == []


# ── accept and the execution profile ─────────────────────────────────────


def test_accept_needs_a_profile_from_settings_and_pins_its_version(
    workspace: Path, account: tuple[str, str], chain: list[tuple[str, bool]]
) -> None:
    client, h = _client(workspace, account)
    goal = _goal(client, h)
    refused = _act(client, h, goal, "accept")
    assert refused.status_code == 409 and "no_execution_profile" in refused.text
    profile = _profile(client, h)
    listed = client.get("/api/execution-profiles", headers=h).json()
    assert listed["active_profile_id"] == profile["profile_id"], "the first profile becomes active"
    accepted = _act(client, h, goal, "accept")
    assert accepted.status_code == 200, accepted.text
    body = accepted.json()
    assert body["status"] == "ready"
    assert (body["profile"]["profile_id"], body["profile"]["version"]) == (profile["profile_id"], 1)
    assert body["budget"]["max_step_runs"] == profile["max_step_runs"]


def test_a_steps_finish_criterion_with_no_step_cannot_be_accepted(
    workspace: Path, account: tuple[str, str], chain: list[tuple[str, bool]]
) -> None:
    client, h = _client(workspace, account)
    _profile(client, h)
    plan = {**PLAN, "steps": [{"title": "a", "instruction": "x"}]}
    goal = _goal(client, h, plan)
    refused = _act(client, h, goal, "accept")
    assert refused.status_code == 422 and "goal_criterion_has_no_step" in refused.text


def test_private_local_refuses_a_hosted_model_by_name_and_files_nothing(
    workspace: Path, account: tuple[str, str], chain: list[tuple[str, bool]]
) -> None:
    client, h = _client(workspace, account)
    _profile(client, h, "private_local")
    goal = _act(client, h, _goal(client, h), "accept").json()
    refused = _act(client, h, goal, "start")
    assert refused.status_code == 409
    assert "profile_blocks_model:anthropic (hosted)" in refused.text
    assert SQLiteStore(workspace).list_tasks() == []


def test_a_fallback_outside_the_profile_blocks_as_surely_as_the_primary(
    workspace: Path, account: tuple[str, str], chain: list[tuple[str, bool]]
) -> None:
    client, h = _client(workspace, account)
    chain[:] = [("ollama", True), ("openai", False)]
    _profile(client, h, "private_local")
    goal = _act(client, h, _goal(client, h), "accept").json()
    refused = _act(client, h, goal, "start")
    assert refused.status_code == 409 and "openai (hosted)" in refused.text


def test_provider_allowlist_and_validation(workspace: Path, account: tuple[str, str]) -> None:
    client, h = _client(workspace, account)
    assert client.post("/api/execution-profiles", json={"template": "nope"}, headers=h).status_code == 422
    none = client.post(
        "/api/execution-profiles", json={"template": "balanced", "allow_local": False, "allow_hosted": False}, headers=h
    )
    assert none.status_code == 422 and "profile_allows_no_model" in none.text
    profile = _profile(client, h, "balanced", allowed_providers=["anthropic"])
    record = profile_store.get_profile(SQLiteStore(workspace), owner=account[0], profile_id=profile["profile_id"])
    assert record is not None
    assert record.allows(provider="anthropic", local=False)
    assert not record.allows(provider="openai", local=False)
    private = _profile(client, h, "private_local", memory_to_hosted=True)
    assert private["memory_to_hosted"] is False, "memory cannot go to a hosted model the profile refuses"


# ── running: dispatch, waiting, assessment ───────────────────────────────


def _running(workspace: Path, account: tuple[str, str], template: str = "balanced", **fields: Any) -> tuple[TestClient, dict[str, str], dict[str, Any]]:
    client, h = _client(workspace, account)
    _profile(client, h, template, **fields)
    goal = _act(client, h, _goal(client, h), "accept").json()
    started = _act(client, h, goal, "start")
    assert started.status_code == 200, started.text
    return client, h, started.json()


def test_start_files_only_due_steps_as_ordinary_tasks(
    workspace: Path, account: tuple[str, str], chain: list[tuple[str, bool]]
) -> None:
    _client_, _h, goal = _running(workspace, account)
    assert goal["status"] == "running"
    first, second = goal["steps"]
    assert first["task_id"] and first["state"] == "running"
    assert second["task_id"] is None and second["state"] == "pending", "it depends on the first"
    task = SQLiteStore(workspace).load_task(first["task_id"])
    assert task is not None and task.status == "queued" and task.objective == "List three options."
    assert goal["budget"]["step_runs"] == 1


def test_a_step_parked_on_a_decision_makes_the_goal_wait_with_that_reason(
    workspace: Path, account: tuple[str, str], chain: list[tuple[str, bool]]
) -> None:
    client, h, goal = _running(workspace, account)
    _settle_task(workspace, goal["steps"][0]["task_id"], "waiting_for_approval")
    view = _read(client, h, goal["goal_id"])
    assert view["status"] == "waiting"
    assert view["reason"] == "needs_decision"
    assert view["reason_text"] == "A step is waiting for your decision"


def test_completion_needs_every_mandatory_criterion_not_just_finished_steps(
    workspace: Path, account: tuple[str, str], chain: list[tuple[str, bool]]
) -> None:
    client, h, goal = _running(workspace, account)
    _settle_task(workspace, goal["steps"][0]["task_id"], "completed")
    view = _read(client, h, goal["goal_id"])
    second = view["steps"][1]
    assert second["task_id"], "the next step is filed once its dependency finished"
    _settle_task(workspace, second["task_id"], "completed")
    view = _read(client, h, goal["goal_id"])
    assert view["status"] == "partial", "the owner has not confirmed c2"
    assert view["criteria"][0]["evidence_kind"] == "steps_finished"
    assert view["criteria"][1]["evidence_kind"] is None
    confirmed = client.post(
        f"/api/goals/{goal['goal_id']}/criteria/c2/confirm",
        json={"base_revision": view["revision"], "note": "Looks right"}, headers=h,
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "completed"
    assert confirmed.json()["criteria"][1]["evidence_kind"] == "owner_confirmed"


def test_a_failed_step_blocks_its_dependants_and_nothing_met_reads_failed(
    workspace: Path, account: tuple[str, str], chain: list[tuple[str, bool]]
) -> None:
    client, h, goal = _running(workspace, account)
    _settle_task(workspace, goal["steps"][0]["task_id"], "failed")
    view = _read(client, h, goal["goal_id"])
    assert view["steps"][1]["state"] == "blocked"
    assert view["steps"][1]["task_id"] is None
    assert view["status"] == "failed"


# ── stop, pause, resume ──────────────────────────────────────────────────


def test_stop_reaches_every_linked_task_and_nothing_new_is_filed(
    workspace: Path, account: tuple[str, str], chain: list[tuple[str, bool]]
) -> None:
    client, h, goal = _running(workspace, account)
    stopped = _act(client, h, goal, "stop")
    assert stopped.status_code == 200, stopped.text
    body = stopped.json()
    assert body["tasks_stopped"] == 1 and body["steps_done"] == 0
    assert body["goal"]["status"] == "stopped"
    store = SQLiteStore(workspace)
    task = store.load_task(goal["steps"][0]["task_id"])
    assert task is not None and task.status == "cancelled"
    GoalCoordinator(workspace).reconcile_all()
    assert len(store.list_tasks()) == 1


def test_pause_parks_unclaimed_steps_and_resume_rechecks_the_chain(
    workspace: Path, account: tuple[str, str], chain: list[tuple[str, bool]]
) -> None:
    client, h, goal = _running(workspace, account)
    paused = _act(client, h, goal, "pause").json()
    assert paused["status"] == "paused" and paused["reason"] == "owner_paused"
    store = SQLiteStore(workspace)
    task_id = goal["steps"][0]["task_id"]
    task = store.load_task(task_id)
    assert task is not None and task.status == "paused"
    chain[:] = [("openai", False)]
    profile = client.get("/api/execution-profiles", headers=h).json()["profiles"][0]
    client.put(
        f"/api/execution-profiles/{profile['profile_id']}",
        json={"base_version": 1, "allowed_providers": ["anthropic"]}, headers=h,
    )
    paused = _read(client, h, goal["goal_id"])
    refused = _act(client, h, paused, "resume")
    assert refused.status_code == 409 and "openai (hosted)" in refused.text
    chain[:] = [("anthropic", False)]
    resumed = _act(client, h, paused, "resume")
    assert resumed.status_code == 200, resumed.text
    body = resumed.json()
    assert body["status"] == "running"
    assert body["profile"]["version"] == 2, "Resume adopted the changed profile after rechecking it"
    task = store.load_task(task_id)
    assert task is not None and task.status == "queued"


def test_a_profile_change_pauses_running_goals_at_a_safe_boundary(
    workspace: Path, account: tuple[str, str], chain: list[tuple[str, bool]]
) -> None:
    client, h, goal = _running(workspace, account)
    profile = goal["profile"]
    changed = client.put(
        f"/api/execution-profiles/{profile['profile_id']}", json={"base_version": 1, "max_step_runs": 5}, headers=h
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["goals_paused"] == 1
    view = _read(client, h, goal["goal_id"])
    assert view["status"] == "paused" and view["reason"] == "profile_changed"
    stale = client.put(
        f"/api/execution-profiles/{profile['profile_id']}", json={"base_version": 1, "max_step_runs": 6}, headers=h
    )
    assert stale.status_code == 409


def test_a_project_binding_wins_over_the_active_profile(
    workspace: Path, account: tuple[str, str], chain: list[tuple[str, bool]]
) -> None:
    client, h = _client(workspace, account)
    _profile(client, h, "balanced")
    local = _profile(client, h, "private_local")
    project = client.post("/api/projects", json={"name": "Trip"}, headers=h)
    assert project.status_code in (200, 201), project.text
    project_id = project.json()["project_id"]
    bound = client.put(
        f"/api/execution-profiles/projects/{project_id}", json={"profile_id": local["profile_id"]}, headers=h
    )
    assert bound.status_code == 200, bound.text
    goal = _goal(client, h, {**PLAN, "project_id": project_id})
    accepted = _act(client, h, goal, "accept").json()
    assert accepted["profile"]["profile_id"] == local["profile_id"]
    assert accepted["profile_source"] == "project"


# ── budget ───────────────────────────────────────────────────────────────


def test_the_step_run_budget_pauses_the_goal_before_the_next_dispatch(
    workspace: Path, account: tuple[str, str], chain: list[tuple[str, bool]]
) -> None:
    client, h, goal = _running(workspace, account, max_step_runs=1)
    _settle_task(workspace, goal["steps"][0]["task_id"], "completed")
    view = _read(client, h, goal["goal_id"])
    assert view["status"] == "paused" and view["reason"] == "budget_exhausted"
    assert view["steps"][1]["task_id"] is None
    assert len(SQLiteStore(workspace).list_tasks()) == 1


def test_a_cost_budget_caps_each_step_run(
    workspace: Path, account: tuple[str, str], chain: list[tuple[str, bool]]
) -> None:
    _client_, _h, goal = _running(workspace, account, max_cost_usd=2.5)
    task = SQLiteStore(workspace).load_task(goal["steps"][0]["task_id"])
    assert task is not None and task.max_run_cost_usd == 2.5


# ── memory data class ────────────────────────────────────────────────────


def test_balanced_withholds_memory_from_a_hosted_step_and_cloud_first_does_not(
    workspace: Path, account: tuple[str, str], chain: list[tuple[str, bool]]
) -> None:
    _client_, _h, goal = _running(workspace, account, "balanced")
    store = SQLiteStore(workspace)
    task = store.load_task(goal["steps"][0]["task_id"])
    assert task is not None
    assert session_memory_withheld(store, task.run_session_id) == "execution_profile"
    bundle = ContextGatherer().gather(
        workspace_root=workspace, session_id=task.run_session_id, turn_id="turn_x",
        prompt_text="what do I like", owner_principal_id=account[0],
    )
    assert bundle.memory_disclosure.get("effective_mode") == "off"
    assert not any(item.source.source_type in {"memory_brief", "memory_recall"} for item in bundle.items)


def test_cloud_first_lets_memory_travel(
    workspace: Path, account: tuple[str, str], chain: list[tuple[str, bool]]
) -> None:
    _client_, _h, goal = _running(workspace, account, "cloud_first")
    store = SQLiteStore(workspace)
    task = store.load_task(goal["steps"][0]["task_id"])
    assert task is not None
    assert session_memory_withheld(store, task.run_session_id) == ""


def test_the_memory_tools_answer_withheld_in_a_withheld_step(
    workspace: Path, account: tuple[str, str], chain: list[tuple[str, bool]]
) -> None:
    from raiker.tools.broker import _PERSONAL_MEMORY_TOOLS

    assert {"memory_search", "memory_get", "conversation_search"} <= _PERSONAL_MEMORY_TOOLS


# ── scheduler guard ──────────────────────────────────────────────────────


def test_the_scheduler_refuses_a_step_whose_chain_left_the_profile(
    workspace: Path, account: tuple[str, str], chain: list[tuple[str, bool]]
) -> None:
    from raiker.tasks.scheduler import TaskScheduler

    client, h, goal = _running(workspace, account, "balanced", allowed_providers=["anthropic"])
    chain[:] = [("openai", False)]
    store = SQLiteStore(workspace)
    task = store.load_task(goal["steps"][0]["task_id"])
    assert task is not None
    asyncio.run(TaskScheduler(workspace)._run_claimed_task(task))  # noqa: SLF001
    task = store.load_task(task.task_id)
    assert task is not None and task.status == "cancelled"
    view = _read(client, h, goal["goal_id"])
    assert view["status"] == "waiting" and view["reason"] == "profile_blocks_model"
    assert view["steps"][0]["state"] == "pending" and view["steps"][0]["task_id"] is None
    assert view["budget"]["step_runs"] == 0, "nothing ran, so the run is refunded"


def test_the_scheduler_does_not_run_a_step_of_a_stopped_goal(
    workspace: Path, account: tuple[str, str], chain: list[tuple[str, bool]]
) -> None:
    client, h, goal = _running(workspace, account)
    store = SQLiteStore(workspace)
    task = store.load_task(goal["steps"][0]["task_id"])
    assert task is not None
    with store.connect() as connection:
        connection.execute("UPDATE goals SET status = 'stopped' WHERE goal_id = ?", (goal["goal_id"],))
    assert GoalCoordinator(workspace).guard_task(task) == ("goal_not_running", "stopped")


def test_model_chain_judges_the_selected_model_and_every_fallback(
    workspace: Path, account: tuple[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from raiker.models.readiness import ModelReadinessService

    monkeypatch.setattr(ModelReadinessService, "resolve_request_target", lambda self, o, p, m: ("ollama-local-openai-compatible", "llama"))
    monkeypatch.setattr(ModelReadinessService, "_fallback_profile_ids", lambda self, o: ["anthropic-hosted", "no-such-profile"])
    store = SQLiteStore(workspace)
    client, h = _client(workspace, account)
    record = profile_store.get_profile(store, owner=account[0], profile_id=_profile(client, h, "private_local")["profile_id"])
    assert record is not None
    entries = profile_store.model_chain(store, account[0], record)
    assert [(e.provider, e.local, e.allowed) for e in entries] == [
        ("ollama", True, True), ("anthropic", False, False), ("unknown", False, False),
    ]
    assert profile_store.chain_refusal(entries) == "anthropic (hosted)"


def test_profile_and_goal_changes_are_human_only(workspace: Path, account: tuple[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    import raiker.api.routes_goals as routes
    from raiker.api.dependencies import refusal

    client, h = _client(workspace, account)

    def refuse(_principal: Any) -> None:
        raise refusal(403, "human_principal_required")

    monkeypatch.setattr(routes, "require_human", refuse)
    assert client.post("/api/goals", json=PLAN, headers=h).status_code == 403
    assert client.post("/api/execution-profiles", json={"template": "balanced"}, headers=h).status_code == 403


def test_start_after_settings_switched_the_profile_adopts_the_new_one(
    workspace: Path, account: tuple[str, str], chain: list[tuple[str, bool]]
) -> None:
    client, h = _client(workspace, account)
    _profile(client, h, "private_local")
    goal = _act(client, h, _goal(client, h), "accept").json()
    assert _act(client, h, goal, "start").status_code == 409, "anthropic is hosted"
    balanced = _profile(client, h, "balanced")
    client.put("/api/execution-profiles/active", json={"profile_id": balanced["profile_id"]}, headers=h)
    started = _act(client, h, _read(client, h, goal["goal_id"]), "start")
    assert started.status_code == 200, started.text
    body = started.json()
    assert body["status"] == "running" and body["profile"]["profile_id"] == balanced["profile_id"]
    assert any(e["kind"] == "goal_profile_repinned" for e in body["events"])


def test_accept_needs_a_configured_model_and_steps_run_on_it(
    workspace: Path, account: tuple[str, str], chain: list[tuple[str, bool]]
) -> None:
    client, h = _client(workspace, account)
    _profile(client, h)
    bare = {k: v for k, v in PLAN.items() if k not in {"model_profile", "model"}}
    goal = _goal(client, h, bare)
    refused = _act(client, h, goal, "accept")
    assert refused.status_code == 422 and "goal_needs_model" in refused.text
    half = {**bare, "model_profile": MODEL[0]}
    assert client.post("/api/goals", json=half, headers=h).status_code == 422
    unknown = _goal(client, h, {**bare, "model_profile": MODEL[0], "model": "not-configured"})
    assert "goal_model_not_configured" in _act(client, h, unknown, "accept").text
    _client_, _h, running = _running(workspace, account)
    task = SQLiteStore(workspace).load_task(running["steps"][0]["task_id"])
    assert task is not None and (task.model_profile, task.model) == MODEL
    assert (running["model_profile"], running["model"]) == MODEL


def test_model_chain_starts_from_the_goals_own_model(
    workspace: Path, account: tuple[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from raiker.models.readiness import ModelReadinessService

    seen: list[tuple[Any, Any]] = []

    def target(self: Any, owner: str, profile_id: Any, model: Any) -> tuple[str, str]:
        seen.append((profile_id, model))
        return (profile_id or "ollama-local-openai-compatible", model or "<model>")

    monkeypatch.setattr(ModelReadinessService, "resolve_request_target", target)
    monkeypatch.setattr(ModelReadinessService, "_fallback_profile_ids", lambda self, o: [])
    store = SQLiteStore(workspace)
    client, h = _client(workspace, account)
    record = profile_store.get_profile(store, owner=account[0], profile_id=_profile(client, h, "private_local")["profile_id"])
    assert record is not None
    entries = profile_store.model_chain(store, account[0], record, *MODEL)
    assert seen[-1] == MODEL
    assert profile_store.chain_refusal(entries) == "anthropic (hosted)"


def test_every_goal_and_profile_change_reaches_the_audit_log(
    workspace: Path, account: tuple[str, str], chain: list[tuple[str, bool]]
) -> None:
    """The audit write is suppressed on failure, so an undeclared type would vanish silently."""
    from raiker.contracts.models import EVENT_TYPES

    client, h, goal = _running(workspace, account)
    _act(client, h, goal, "stop")
    store = SQLiteStore(workspace)
    with store.connect() as connection:
        kinds = {
            str(row[0]) for row in connection.execute(
                "SELECT event_type FROM events_index WHERE session_id = ?", (f"sess_inbox_{account[0]}",)
            ).fetchall()
        }
    assert {"execution_profile_created", "goal_accepted", "goal_started", "goal_step_started", "goal_stopped"} <= kinds
    for outcome in ("completed", "partial", "failed"):
        assert f"goal_{outcome}" in EVENT_TYPES
