"""B6 and B7 — the agent's plan, and the subagent it can spawn for itself.

Two gaps in the loop, tested to the same standard as the ones already closed:

**B6.** Nothing tracked what the agent intended to do next, so a long change had
no visible spine and no recovery point. `update_plan` writes an ordered,
status-bearing checklist that survives the turn, is re-injected into the next
one, and reaches the workspace live. The tests hold it to being *fail-closed*
(a malformed plan never replaces a good one), *owner-scoped* (never readable
across accounts), and *bounded* (it cannot grow into a document).

**B7.** `spawn_subagent` delegates a wide, read-only search so its raw output
never enters the parent's context. The tests hold it to granting nothing: only
read-only tools are delegable, a write or a shell command is refused before the
subagent is created, it cannot spawn another subagent, and its findings reach
the calling model as untrusted data and the audit trail as counts.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.models import ToolAction
from raiker.models.contracts import ToolCallProposal
from raiker.models.tool_call_validation import (
    ToolCallRejected,
    default_tool_specs,
    validate_tool_call,
)
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.runtime.agent_plan import (
    MAX_PLAN_STEPS,
    PlanValidationError,
    load_plan,
    normalize_steps,
    plan_context_message,
    save_plan,
)
from raiker.runtime.identity.lifecycle import TurnMachineIdentityLifecycle
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.broker import ToolBroker
from raiker.tools.subagent_tools import SPAWNABLE_TOOLS

_OWNER = "principal_owner"
_SESSION = "sess_plan"
_TURN = "turn_1"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "plan_ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def store(workspace: Path) -> SQLiteStore:
    return SQLiteStore(workspace)


def _broker(workspace: Path, store: SQLiteStore) -> ToolBroker:
    return ToolBroker(
        workspace_root=workspace,
        policy_engine=PolicyEngine(StaticPolicyConfig(workspace), store=store),
        store=store,
        principal_id=_OWNER,
    )


def _run(broker: ToolBroker, tool_name: str, arguments: dict[str, Any]) -> Any:
    action = ToolAction(
        action_id=f"act_{tool_name}",
        tool_name=tool_name,
        arguments=arguments,
        risk_level="medium",
        requires_approval=False,
        proposed_by="model",
    )
    identity = TurnMachineIdentityLifecycle(
        broker.workspace_root, broker.store, broker.writer
    ).start(
        owner_principal_id=_OWNER,
        session_id=_SESSION,
        turn_id=_TURN,
        role_ids=("assistant",),
    )
    return broker.execute(
        action,
        session_id=_SESSION,
        turn_id=_TURN,
        machine_identity=identity,
    )


# ── B6: validation ───────────────────────────────────────────────────────────


class TestPlanValidation:
    def test_a_well_formed_plan_normalises(self) -> None:
        steps = normalize_steps(
            [
                {"title": "Read the migration", "status": "completed"},
                {"title": "Add the column", "status": "in_progress"},
                {"title": "Run the tests", "status": "pending"},
            ]
        )
        assert [step.status for step in steps] == ["completed", "in_progress", "pending"]

    def test_a_missing_status_defaults_to_pending(self) -> None:
        assert normalize_steps([{"title": "Do the thing"}])[0].status == "pending"

    def test_two_steps_in_progress_is_refused(self) -> None:
        """'What is happening right now' must have exactly one answer."""
        with pytest.raises(PlanValidationError) as excinfo:
            normalize_steps(
                [
                    {"title": "A", "status": "in_progress"},
                    {"title": "B", "status": "in_progress"},
                ]
            )
        assert excinfo.value.reason.startswith("plan_multiple_steps_in_progress")

    @pytest.mark.parametrize(
        ("raw", "reason"),
        [
            ("not a list", "plan_steps_not_a_list"),
            ([], "plan_steps_empty"),
            (["just a string"], "plan_step_not_an_object:0"),
            ([{"title": "  "}], "plan_step_missing_title:0"),
            ([{"title": "A", "status": "done"}], "plan_step_invalid_status:0:done"),
        ],
    )
    def test_malformed_plans_are_refused_by_name(self, raw: Any, reason: str) -> None:
        with pytest.raises(PlanValidationError) as excinfo:
            normalize_steps(raw)
        assert excinfo.value.reason == reason

    def test_a_plan_cannot_grow_into_a_document(self) -> None:
        too_many = [{"title": f"Step {i}", "status": "pending"} for i in range(MAX_PLAN_STEPS + 1)]
        with pytest.raises(PlanValidationError) as excinfo:
            normalize_steps(too_many)
        assert excinfo.value.reason.startswith("plan_too_many_steps")

    def test_a_long_title_is_refused_rather_than_truncated(self) -> None:
        with pytest.raises(PlanValidationError):
            normalize_steps([{"title": "x" * 5_000, "status": "pending"}])


# ── B6: persistence and scoping ──────────────────────────────────────────────


class TestPlanPersistence:
    def test_a_plan_round_trips_and_summarises(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        steps = normalize_steps(
            [
                {"title": "One", "status": "completed"},
                {"title": "Two", "status": "in_progress"},
                {"title": "Three", "status": "blocked", "note": "waiting on approval"},
            ]
        )
        save_plan(
            store, session_id=_SESSION, principal_id=_OWNER, turn_id=_TURN, steps=steps
        )
        loaded = load_plan(store, _SESSION, _OWNER)
        assert loaded is not None
        assert loaded["completed"] == 1
        assert loaded["blocked"] == 1
        assert loaded["current_step"] == "Two"
        assert loaded["steps"][2]["note"] == "waiting on approval"

    def test_a_plan_is_never_readable_by_another_account(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        save_plan(
            store,
            session_id=_SESSION,
            principal_id=_OWNER,
            turn_id=_TURN,
            steps=normalize_steps([{"title": "Private", "status": "pending"}]),
        )
        assert load_plan(store, _SESSION, "principal_someone_else") is None

    def test_an_update_replaces_the_plan_whole(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        for titles in (["A", "B", "C"], ["D"]):
            save_plan(
                store,
                session_id=_SESSION,
                principal_id=_OWNER,
                turn_id=_TURN,
                steps=normalize_steps([{"title": t, "status": "pending"} for t in titles]),
            )
        loaded = load_plan(store, _SESSION, _OWNER)
        assert loaded is not None
        assert [step["title"] for step in loaded["steps"]] == ["D"]

    def test_a_corrupt_row_reads_as_no_plan_rather_than_raising(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        """A plan is a recovery aid; it must never be able to stop a turn."""
        store.save_agent_plan(
            session_id=_SESSION, principal_id=_OWNER, turn_id=_TURN, steps_json="{not json"
        )
        assert load_plan(store, _SESSION, _OWNER) is None

    def test_the_context_message_states_each_step_and_its_state(self) -> None:
        message = plan_context_message(
            {
                "steps": [
                    {"title": "Done thing", "status": "completed"},
                    {"title": "Live thing", "status": "in_progress"},
                    {"title": "Stuck thing", "status": "blocked", "note": "needs a key"},
                ]
            }
        )
        assert "[x] Done thing" in message
        assert "[>] Live thing" in message
        assert "[!] Stuck thing — needs a key" in message


# ── B6: the governed tool ────────────────────────────────────────────────────


class TestUpdatePlanTool:
    def test_the_tool_is_advertised_with_a_list_schema(self) -> None:
        """Without an array schema a model sends a stringified plan."""
        spec = next(spec for spec in default_tool_specs() if spec.name == "update_plan")
        assert spec.parameters["properties"]["steps"]["type"] == "array"
        assert spec.parameters["required"] == ["steps"]

    def test_a_call_with_no_steps_is_rejected_before_the_broker(self) -> None:
        with pytest.raises(ToolCallRejected) as excinfo:
            validate_tool_call(
                ToolCallProposal(call_id="1", tool_name="update_plan", arguments={})
            )
        assert excinfo.value.reason == "missing_argument:steps"

    def test_a_validated_call_needs_no_approval(self) -> None:
        action = validate_tool_call(
            ToolCallProposal(
                call_id="1",
                tool_name="update_plan",
                arguments={"steps": [{"title": "A", "status": "pending"}]},
            )
        )
        assert action.requires_approval is False

    def test_the_broker_records_the_plan(self, workspace: Path, store: SQLiteStore) -> None:
        result, decision = _run(
            _broker(workspace, store),
            "update_plan",
            {"steps": [{"title": "Write the test", "status": "in_progress"}]},
        )
        assert decision.decision == "allow"
        assert result.status == "success"
        assert (result.output or {})["plan"]["current_step"] == "Write the test"
        assert load_plan(store, _SESSION, _OWNER) is not None

    def test_a_malformed_plan_leaves_the_stored_one_untouched(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        broker = _broker(workspace, store)
        _run(broker, "update_plan", {"steps": [{"title": "Good", "status": "pending"}]})
        result, _ = _run(broker, "update_plan", {"steps": [{"title": "", "status": "pending"}]})
        assert result.status == "failed"
        assert (result.error or {})["type"] == "plan_step_missing_title:0"
        stored = load_plan(store, _SESSION, _OWNER)
        assert stored is not None
        assert stored["steps"][0]["title"] == "Good"


# ── B7: the subagent the model may spawn ─────────────────────────────────────


class TestSpawnSubagent:
    def test_only_read_only_tools_are_delegable(self) -> None:
        for forbidden in (
            "write_file",
            "edit_file",
            "apply_patch",
            "shell",
            "run_command",
            "connector_write",
            "github_read",
            "spawn_subagent",
            "update_plan",
            "create_document",
        ):
            assert forbidden not in SPAWNABLE_TOOLS

    def test_a_write_step_is_refused_before_anything_runs(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        result, _ = _run(
            _broker(workspace, store),
            "spawn_subagent",
            {
                "objective": "Sneak a write past the parent",
                "steps": [{"tool_name": "write_file", "arguments": {"path": "x", "text": "y"}}],
            },
        )
        assert result.status == "failed"
        assert (result.error or {})["type"] == "subagent_tool_not_delegable:write_file"

    def test_a_subagent_cannot_spawn_another(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        result, _ = _run(
            _broker(workspace, store),
            "spawn_subagent",
            {
                "objective": "Recurse",
                "steps": [{"tool_name": "spawn_subagent", "arguments": {}}],
            },
        )
        assert (result.error or {})["type"] == "subagent_tool_not_delegable:spawn_subagent"

    def test_an_objective_is_required(self, workspace: Path, store: SQLiteStore) -> None:
        with pytest.raises(ToolCallRejected) as excinfo:
            validate_tool_call(
                ToolCallProposal(
                    call_id="1",
                    tool_name="spawn_subagent",
                    arguments={"steps": [{"tool_name": "glob", "arguments": {}}]},
                )
            )
        assert excinfo.value.reason == "missing_argument:objective"

    def test_it_returns_the_findings_as_untrusted_data(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        (workspace / "needle.txt").write_text("the needle is here\n", encoding="utf-8")
        result, decision = _run(
            _broker(workspace, store),
            "spawn_subagent",
            {
                "objective": "Find the needle",
                "name": "search",
                "steps": [
                    {"tool_name": "glob", "arguments": {"pattern": "*.txt"}},
                    {"tool_name": "read_file", "arguments": {"path": "needle.txt"}},
                ],
            },
        )
        assert decision.decision == "allow"
        assert result.status == "success"
        output = result.output or {}
        assert output["steps_executed"] == 2
        assert output["untrusted"] is True
        assert "UNTRUSTED SUBAGENT FINDINGS" in output["content"]
        # The findings really are the subagent's, not a fabricated summary.
        assert "the needle is here" in output["content"]

    def test_the_findings_never_reach_an_event_payload(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        """The digest is workspace content: it goes to the model and nowhere else."""
        (workspace / "secret-ish.txt").write_text("sensitive body text\n", encoding="utf-8")
        broker = _broker(workspace, store)
        result, _ = _run(
            broker,
            "spawn_subagent",
            {
                "objective": "Read it",
                "steps": [{"tool_name": "read_file", "arguments": {"path": "secret-ish.txt"}}],
            },
        )
        payload = ToolBroker._event_safe_result_payload(result)
        serialized = json.dumps(payload)
        assert "sensitive body text" not in serialized
        assert payload["output"]["content_redacted"] is True
        # What the audit trail keeps instead: the counts and the tools used.
        assert payload["output"]["steps_executed"] == 1

    def test_a_failing_step_stops_the_subagent_and_says_so(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        result, _ = _run(
            _broker(workspace, store),
            "spawn_subagent",
            {
                "objective": "Read a file that is not there",
                "steps": [{"tool_name": "read_file", "arguments": {"path": "missing.txt"}}],
            },
        )
        assert result.status == "failed"
        assert (result.error or {})["type"].startswith("subagent_step_failed:read_file")


# ── The class of defect this change found ────────────────────────────────────


class TestEveryEmittedEventIsDeclared:
    """An event the runtime emits but never declared kills the turn.

    `AgentEvent` validates `event_type` against `EVENT_TYPES` and raises
    `ContractValidationError` otherwise — inside the streaming turn, where it
    surfaces as "stream ended" with no stated cause. B6's own plan event hit
    this in live testing, and so did B4's `model_tool_calls_dropped`, which had
    been shipped undeclared: any turn that dropped a tool call died at the
    moment it tried to say so.

    Unit tests never caught it because they assert on results rather than on the
    durable log. This is the guard that does: a static scan of every literal
    event type the runtime emits, checked against the declared set.
    """

    def test_no_runtime_event_type_is_undeclared(self) -> None:
        import ast

        from raiker.contracts.models import EVENT_TYPES

        source_root = Path(__file__).resolve().parents[1] / "raiker"
        undeclared: dict[str, list[str]] = {}
        for path in sorted(source_root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                name = getattr(func, "attr", None) or getattr(func, "id", None)
                if name not in {"_event", "make_event", "append_event"}:
                    continue
                literals: list[str] = [
                    arg.value
                    for arg in node.args
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                ] + [
                    kw.value.value
                    for kw in node.keywords
                    if kw.arg == "event_type"
                    and isinstance(kw.value, ast.Constant)
                    and isinstance(kw.value.value, str)
                ]
                for literal in literals:
                    # Only bare identifiers are event types; a path or a
                    # sentence in the same position is another argument.
                    if not literal or "/" in literal or " " in literal:
                        continue
                    if literal not in EVENT_TYPES:
                        undeclared.setdefault(literal, []).append(f"{path.name}:{node.lineno}")
        assert undeclared == {}

    def test_the_new_loop_events_are_declared(self) -> None:
        from raiker.contracts.models import EVENT_TYPES

        for event_type in (
            "agent_plan_updated",
            "agent_plan_replayed",
            "subagent_completed",
            "model_tool_calls_dropped",
        ):
            assert event_type in EVENT_TYPES
