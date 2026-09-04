"""Compatibility backlog #16 — the tool catalogue cost every turn its whole size.

Forty-nine built-in schemas entered every request whether or not the turn would
call one — ~6,400 tokens paid before a word of the owner's prompt, on every turn
of every conversation, and every tool a connected MCP server advertises stacked
on top. The reference platforms answer this with a tool search; Raiker does the
same, and the property that has to hold is the one a governed product cannot get
wrong:

**Deferring is not gating.** A deferred tool is not withheld, not restricted,
and not harder to reach. The model is told every name that exists, gets the
exact schema on request, and the tool it then calls passes the identical
capability gate, decision mode, policy review and approval it always did. What
changes is what every request has to carry.
"""

from __future__ import annotations

import json
from typing import Any, cast

from raiker.models.contracts import ToolSpec
from raiker.models.tool_call_validation import default_tool_specs, tool_spec
from raiker.models.tool_projection import (
    ALWAYS_PROJECTED,
    DEFERRABLE_TOOL_NAMES,
    TOOL_SEARCH,
    deferred_tool_names,
    matching_tools,
    project_specs,
    search_tools,
)
from raiker.models.tool_registry import MODEL_EXPOSED_TOOLS


def _tokens(specs: list[ToolSpec]) -> int:
    blob = json.dumps(
        [{"name": s.name, "description": s.description, "parameters": s.parameters}
         for s in specs]
    )
    return len(blob) // 4


class TestEveryToolIsStillReachable:
    def test_the_two_halves_are_the_whole_catalogue(self) -> None:
        """A tool in neither half would be gone, not deferred."""
        assert ALWAYS_PROJECTED | DEFERRABLE_TOOL_NAMES | {TOOL_SEARCH} == MODEL_EXPOSED_TOOLS

    def test_nothing_is_in_both(self) -> None:
        assert not (ALWAYS_PROJECTED & DEFERRABLE_TOOL_NAMES)

    def test_the_search_tool_is_never_deferred(self) -> None:
        """It is how everything else is reached."""
        assert TOOL_SEARCH not in DEFERRABLE_TOOL_NAMES
        assert TOOL_SEARCH in {spec.name for spec in project_specs(default_tool_specs())}

    def test_a_new_tool_is_deferred_rather_than_lost(self) -> None:
        """The split is derived, so nobody has to remember to add a name twice."""
        assert MODEL_EXPOSED_TOOLS - ALWAYS_PROJECTED - {TOOL_SEARCH} == DEFERRABLE_TOOL_NAMES

    def test_every_deferred_tool_is_named_in_the_request(self) -> None:
        """Not carried is not the same as not available, and the model is told so."""
        search = next(
            spec for spec in project_specs(default_tool_specs()) if spec.name == TOOL_SEARCH
        )
        for name in deferred_tool_names():
            assert name in search.description


class TestWhatItSaves:
    def test_the_projection_is_materially_smaller(self) -> None:
        full = default_tool_specs()
        projected = project_specs(full)
        # Including the catalogue line that keeps every deferred tool reachable.
        assert _tokens(projected) < _tokens(full) * 0.7

    def test_carrying_everything_stays_available(self) -> None:
        """`defer=False` is the setting, and a caller with no turn state."""
        full = default_tool_specs()
        assert project_specs(full, defer=False) == full


class TestWhatComesBack:
    def test_a_search_returns_the_same_schema_the_request_would_have(self) -> None:
        """Two renderings of one schema is a drift waiting to happen; there is one."""
        tools = cast(list[dict[str, Any]], search_tools("git_commit")["tools"])
        found = next(item for item in tools if item["name"] == "git_commit")
        expected = tool_spec("git_commit")
        assert found["description"] == expected.description
        assert found["parameters"] == expected.parameters

    def test_it_finds_a_tool_by_what_it_does(self) -> None:
        """A model that has not guessed the name should still reach it."""
        assert "git_commit" in matching_tools("commit my work")
        assert "gcal_read" in matching_tools("read my calendar")

    def test_an_empty_query_lists_the_catalogue(self) -> None:
        """"What else is there" is a fair question and the list is small."""
        result = search_tools("")
        assert result["matched"] == len(deferred_tool_names())

    def test_nothing_matched_says_what_exists(self) -> None:
        result = search_tools("zzzz nothing at all")
        assert result["matched"] == 0
        assert result["available"] == list(deferred_tool_names())

    def test_a_core_tool_is_not_returned_by_the_search(self) -> None:
        """It is already in the request; returning it again would be noise."""
        assert "read_file" not in matching_tools("read a file")


class TestRevealingOne:
    def test_a_revealed_tool_joins_the_request(self) -> None:
        projected = project_specs(default_tool_specs(), revealed=frozenset({"git_commit"}))
        assert "git_commit" in {spec.name for spec in projected}

    def test_and_leaves_the_others_deferred(self) -> None:
        projected = project_specs(default_tool_specs(), revealed=frozenset({"git_commit"}))
        names = {spec.name for spec in projected}
        assert "gcal_read" not in names
        search = next(spec for spec in projected if spec.name == TOOL_SEARCH)
        # No longer offered as available-on-request, because it is now present.
        assert "git_commit:" not in search.description
        assert "gcal_read:" in search.description


class TestItGrantsNothing:
    def test_the_search_tool_needs_no_capability_and_no_approval(self) -> None:
        from raiker.models.tool_registry import definition

        entry = definition(TOOL_SEARCH)
        assert entry is not None
        assert entry.capability is None
        assert entry.requires_approval is False
        assert entry.risk == "low"

    def test_a_deferred_tool_keeps_its_own_band_and_gate(self) -> None:
        """Deferring a schema changes nothing about what calling it costs."""
        from raiker.models.tool_registry import (
            APPROVAL_TOOL_NAMES,
            TOOL_CAPABILITY_BY_TOOL,
        )

        assert TOOL_CAPABILITY_BY_TOOL.get("git_commit") is not None
        assert "git_commit" in APPROVAL_TOOL_NAMES
        assert "shell" in APPROVAL_TOOL_NAMES

    def test_a_search_cannot_invent_a_tool(self) -> None:
        """Every name it returns is a registered, model-exposed tool."""
        for name in matching_tools("anything at all read write run"):
            assert name in MODEL_EXPOSED_TOOLS


class TestTheTurnKeepsWhatItFetched:
    """A schema fetched once must stay callable, or the loop cannot use it."""

    def _orchestrator(self, tmp_path):  # type: ignore[no-untyped-def]
        from raiker.cli.principal_resolver import bootstrap_owner
        from raiker.events.writer import EventLogWriter
        from raiker.policy.config import StaticPolicyConfig
        from raiker.policy.engine import PolicyEngine
        from raiker.runtime.orchestrator import RuntimeOrchestrator
        from raiker.storage.sqlite import SQLiteStore
        from raiker.tools.broker import ToolBroker

        bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
        store = SQLiteStore(tmp_path)
        writer = EventLogWriter(store)
        return RuntimeOrchestrator(
            workspace_root=tmp_path,
            writer=writer,
            tool_broker=ToolBroker(
                workspace_root=tmp_path,
                policy_engine=PolicyEngine(StaticPolicyConfig(tmp_path)),
                store=store,
                writer=writer,
                principal_id="principal_owner",
            ),
            model_router=None,  # type: ignore[arg-type]
        )

    def _result(self, tool_names: list[str], status: str = "success"):  # type: ignore[no-untyped-def]
        from raiker.contracts.models import ToolAction, ToolResult

        action = ToolAction(
            action_id="act_1",
            tool_name=TOOL_SEARCH,
            arguments={"query": "anything"},
            risk_level="low",
            requires_approval=False,
            proposed_by="principal_owner",
        )
        result = ToolResult(
            action_id="act_1",
            tool_name=TOOL_SEARCH,
            status=status,
            output={"tools": [{"name": name} for name in tool_names]},
            error=None,
            started_at="2026-09-04T00:00:00Z",
            completed_at="2026-09-04T00:00:01Z",
        )
        return action, result

    def test_a_searched_tool_joins_the_rest_of_the_turn(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        orchestrator = self._orchestrator(tmp_path)
        assert "git_commit" not in {spec.name for spec in orchestrator._turn_tool_specs()}

        orchestrator._reveal_searched_tools(*self._result(["git_commit"]))

        assert "git_commit" in {spec.name for spec in orchestrator._turn_tool_specs()}

    def test_a_failed_search_reveals_nothing(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        orchestrator = self._orchestrator(tmp_path)
        orchestrator._reveal_searched_tools(*self._result(["git_commit"], status="failed"))
        assert "git_commit" not in {spec.name for spec in orchestrator._turn_tool_specs()}

    def test_a_name_the_registry_does_not_have_is_ignored(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """Read from the result, so the catalogue cannot be widened by naming."""
        orchestrator = self._orchestrator(tmp_path)
        orchestrator._reveal_searched_tools(*self._result(["rm_minus_rf", "read_file"]))
        names = {spec.name for spec in orchestrator._turn_tool_specs()}
        assert "rm_minus_rf" not in names

    def test_another_tool_result_reveals_nothing(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        from raiker.contracts.models import ToolAction, ToolResult

        orchestrator = self._orchestrator(tmp_path)
        orchestrator._reveal_searched_tools(
            ToolAction(
                action_id="act_2",
                tool_name="read_file",
                arguments={"path": "x"},
                risk_level="low",
                requires_approval=False,
                proposed_by="principal_owner",
            ),
            ToolResult(
                action_id="act_2",
                tool_name="read_file",
                status="success",
                output={"tools": [{"name": "git_commit"}]},
                error=None,
                started_at="2026-09-04T00:00:00Z",
                completed_at="2026-09-04T00:00:01Z",
            ),
        )
        assert "git_commit" not in {spec.name for spec in orchestrator._turn_tool_specs()}


class TestTheOwnerSeesItRun:
    """A tool the transcript cannot name is a tool that ran invisibly."""

    def test_the_row_says_what_it_looked_for(self) -> None:
        from raiker.tools.presentation import tool_row

        row = tool_row(TOOL_SEARCH, {"query": "commit my work"})
        assert row.label == "Look up a tool"
        assert "commit my work" in row.action
        # The plan family: the turn working out what it can do next. It reaches
        # nothing and changes nothing, so it must not sit in a family that
        # implies either.
        assert row.family == "plan"
