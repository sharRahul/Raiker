"""Workstream C / Slice C1 — subagent per-spawn budgets.

A subagent runs under a four-dimensional budget (steps, tool calls, wall-clock,
estimated tokens). Every dimension is bounded, every dimension is enforced by
:class:`SubagentRunner`, and a breach of *any* dimension fails the subagent
closed — nothing is silently truncated. The budget is persisted on the
subagent's contract so the bounded run stays auditable after the fact.
"""

from __future__ import annotations

import json
from pathlib import Path

from raiker.agents.orchestration import (
    MAX_SUBAGENT_STEPS,
    MAX_SUBAGENT_TOKENS,
    MAX_SUBAGENT_TOOL_CALLS,
    SubagentBudget,
    SubagentRunner,
    estimate_step_tokens,
    parse_subagent_spec,
)
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.storage.sqlite import SQLiteStore


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "sub"
    ws.mkdir()
    (ws / "hello.txt").write_text("hi", encoding="utf-8")
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


def _read_steps(n: int) -> list[dict[str, object]]:
    return [{"tool_name": "read_file", "arguments": {"path": "hello.txt"}} for _ in range(n)]


# ── Budget record: shape, parsing, clamping ──────────────────────────────────


def test_effective_budget_clamps_down_to_hard_caps() -> None:
    # A caller may only *shrink* the process-wide hard caps, never grow them.
    inflated = SubagentBudget(
        max_steps=10_000,
        max_tool_calls=10_000,
        max_runtime_seconds=30,
        max_tokens=10_000_000,
    ).effective()
    assert inflated.max_steps == MAX_SUBAGENT_STEPS
    assert inflated.max_tool_calls == MAX_SUBAGENT_TOOL_CALLS
    assert inflated.max_tokens == MAX_SUBAGENT_TOKENS
    assert inflated.max_runtime_seconds == 30

    shrunk = SubagentBudget(
        max_steps=2, max_tool_calls=1, max_runtime_seconds=5, max_tokens=42
    ).effective()
    assert (shrunk.max_steps, shrunk.max_tool_calls, shrunk.max_tokens) == (2, 1, 42)


def test_parse_defaults_and_overrides_budget() -> None:
    default = parse_subagent_spec({"parent_task_id": "t", "steps": []})
    assert default.max_tool_calls == MAX_SUBAGENT_TOOL_CALLS
    assert default.max_tokens == MAX_SUBAGENT_TOKENS

    override = parse_subagent_spec(
        {"parent_task_id": "t", "steps": [], "max_tool_calls": 3, "max_tokens": 100}
    )
    assert override.max_tool_calls == 3
    assert override.max_tokens == 100


def test_estimate_step_tokens_is_deterministic_and_positive() -> None:
    a = estimate_step_tokens("read_file", {"path": "hello.txt"})
    b = estimate_step_tokens("read_file", {"path": "hello.txt"})
    assert a == b and a >= 1


# ── Budget record persistence ────────────────────────────────────────────────


def test_budget_record_persisted_on_contract(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    spec = parse_subagent_spec(
        {
            "parent_task_id": "task_1",
            "name": "scout",
            "steps": _read_steps(1),
            "max_steps": 7,
            "max_tool_calls": 4,
            "max_tokens": 5_000,
        }
    )
    outcome = SubagentRunner(ws, store).run(spec, principal_id="principal_owner")
    assert outcome.ok, outcome.reason_code
    with store.connect() as connection:
        active = connection.execute(
            "SELECT COUNT(*) AS count FROM turn_machine_identities WHERE is_active = 1"
        ).fetchone()
    assert active is not None and active["count"] == 0
    contract = store.list_subagent_contracts()[0]
    assert contract["max_steps"] == 7
    assert contract["max_tool_calls"] == 4
    assert contract["max_tokens"] == 5_000
    # The outcome carries the enforced budget for the metadata-only event payload.
    assert outcome.artifacts["budget"]["max_tool_calls"] == 4


# ── Fail-closed enforcement, per dimension ───────────────────────────────────


def test_within_budget_completes(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    spec = parse_subagent_spec(
        {"parent_task_id": "t", "name": "ok", "steps": _read_steps(2)}
    )
    outcome = SubagentRunner(ws, store).run(spec, principal_id="principal_owner")
    assert outcome.ok
    assert outcome.artifacts["steps_executed"] == 2


def test_tool_call_budget_fails_closed(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    # Two steps fit the step budget, but the tool-call budget of 1 must stop the
    # subagent before it dispatches the second call.
    spec = parse_subagent_spec(
        {
            "parent_task_id": "t",
            "name": "greedy",
            "steps": _read_steps(2),
            "max_steps": 25,
            "max_tool_calls": 1,
        }
    )
    outcome = SubagentRunner(ws, store).run(spec, principal_id="principal_owner")
    assert not outcome.ok
    assert outcome.reason_code == "subagent_tool_call_budget_exceeded"
    assert store.list_subagent_contracts()[0]["status"] == "failed"


def test_token_budget_fails_closed(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    # A token cap of 1 is exceeded by the first step's estimate; the subagent
    # fails closed rather than continuing.
    spec = parse_subagent_spec(
        {
            "parent_task_id": "t",
            "name": "chatty",
            "steps": _read_steps(2),
            "max_tokens": 1,
        }
    )
    outcome = SubagentRunner(ws, store).run(spec, principal_id="principal_owner")
    assert not outcome.ok
    assert outcome.reason_code == "subagent_token_budget_exceeded"


def test_subagent_has_its_own_principal_and_parks_mutation_for_parent(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    spec = parse_subagent_spec(
        {
            "parent_task_id": "t",
            "steps": [{"tool_name": "write_file", "arguments": {"path": "x.txt", "text": "nope"}}],
        }
    )

    outcome = SubagentRunner(ws, store).run(spec, principal_id="principal_owner")

    assert outcome.reason_code == "subagent_mutation_proposed"
    contract = store.list_subagent_contracts()[0]
    subagent = store.get_principal(outcome.ref_id)
    assert subagent is not None and subagent["principal_type"] == "ai_agent"
    # The exact delegable set, written out rather than derived from
    # DELEGABLE_TOOLS: a subagent must never widen the parent's authority, so
    # adding a name here has to be a deliberate edit to a test that says what
    # the set is — not a constant the production code can quietly grow.
    # `conversation_search` and `code_map_references` (RAIKER-2020) are both
    # local, read-only and egress-free, which is the rule this list encodes.
    assert json.loads(contract["allowed_tools_json"]) == sorted(
        ["code_map_references", "code_map_search", "conversation_search", "diff_files",
         "git_diff", "git_log", "git_status", "glob", "grep",
         "list_directory", "memory_get", "memory_list", "memory_search", "read_file",
         "skill_load", "stat_path", "vector_get"]
    )
    assert store.list_approvals(status="pending")
    assert not (ws / "x.txt").exists()
