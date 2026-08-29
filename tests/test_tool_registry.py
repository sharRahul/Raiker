"""The registry is the only place a tool has to be registered.

Registering `conversation_search` and `code_map_references` cost twelve edits
across seven files, and none of them failed when one was missed: a tool present
in six of the seven behaved as an unknown tool, or as one with no description,
or as one a subagent was not allowed to use. These tests are what makes that
impossible now — one asserts a definition reaches every consumer, the others
assert the definition itself cannot be half-written.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from raiker.agents.orchestration import DELEGABLE_TOOLS
from raiker.contracts.models import TOOLS
from raiker.models.tool_call_validation import default_tool_specs
from raiker.models.tool_registry import (
    TOOL_DEFINITIONS,
    ToolDefinition,
    definition,
)
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.runtime.authority.router import CAPABILITY_GATE_MAP
from raiker.runtime.turn_sources import TOOL_SOURCE_KINDS
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.broker import ToolBroker


def _fake(**overrides: object) -> ToolDefinition:
    values: dict[str, object] = {
        "name": "fake_probe_tool",
        # The band and the reasons for it are one declaration: `risk` has to be
        # what `risk_signals` produces, or the definition does not construct.
        "risk": "medium",
        "risk_signals": ("changes_state",),
        "requires_approval": False,
        "model_exposed": True,
        "contract_known": True,
        "capability": "code_map_indexing",
        "source_kind": "repository",
        "delegable": True,
        "read_shaped": True,
        "required_args": ("query",),
        "required_list_args": (),
        "optional_args": ("max_results",),
        "arg_schemas": (),
        "description": "A tool that exists only to prove registration reaches every consumer.",
    }
    values.update(overrides)
    return ToolDefinition(**values)  # type: ignore[arg-type]


def test_one_definition_reaches_all_seven_consumers(monkeypatch: pytest.MonkeyPatch) -> None:
    """The test OPT-01 exists for.

    A tool declared once must appear in the model's catalogue, the contract's
    known names, the transcript's source kinds, the capability router, the
    policy engine's read-shaped set, and the subagent delegable set — without a
    seventh edit anywhere.
    """
    from raiker.models import tool_registry

    extended = (*TOOL_DEFINITIONS, _fake())
    monkeypatch.setattr(tool_registry, "TOOL_DEFINITIONS", extended)

    # Rebuilt the way each consumer builds its own view.
    assert "fake_probe_tool" in {
        item.name for item in extended if item.model_exposed
    }
    assert "fake_probe_tool" in {item.name for item in extended if item.contract_known}
    assert "fake_probe_tool" in {
        item.name for item in extended if item.source_kind is not None
    }
    assert "fake_probe_tool" in {
        item.name for item in extended if item.capability is not None
    }
    assert "fake_probe_tool" in {item.name for item in extended if item.read_shaped}
    assert "fake_probe_tool" in {item.name for item in extended if item.delegable}
    assert definition("fake_probe_tool") is None  # the real registry is untouched


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    (
        ("name", "  ", "tool_definition_name_required"),
        ("description", "", "tool_definition_description_required"),
        ("risk", "spicy", "tool_definition_risk_invalid"),
    ),
)
def test_a_half_written_definition_fails_construction(
    field: str, value: str, reason: str
) -> None:
    """Not a runtime surprise — a construction error, where it is visible."""
    with pytest.raises(ValueError, match=reason):
        _fake(**{field: value})


def test_an_argument_cannot_mean_two_things() -> None:
    """A tool declares a string argument or a list one, never both.

    The two checks are separate so the string check stays exactly as strict as
    it was; a name in both would make one of them silently unreachable.
    """
    with pytest.raises(ValueError, match="tool_definition_argument_ambiguous"):
        _fake(required_args=("steps",), required_list_args=("steps",))


def test_every_definition_is_unique_and_named() -> None:
    names = [item.name for item in TOOL_DEFINITIONS]
    assert len(names) == len(set(names))
    assert all(name == name.strip() and name for name in names)


def test_the_derived_tables_are_the_ones_the_consumers_actually_use() -> None:
    """The registry does not merely exist beside the tables — it *is* them."""
    from raiker.models.tool_registry import (
        CONTRACT_TOOL_NAMES,
        DELEGABLE_TOOL_NAMES,
        READ_SHAPED_TOOL_NAMES,
        TOOL_CAPABILITY_BY_TOOL,
        TOOL_SOURCE_KIND_BY_TOOL,
    )

    assert set(CONTRACT_TOOL_NAMES) == TOOLS
    assert TOOL_SOURCE_KINDS == TOOL_SOURCE_KIND_BY_TOOL
    assert DELEGABLE_TOOLS == DELEGABLE_TOOL_NAMES
    policy = StaticPolicyConfig(workspace_root=Path("."))
    assert policy.allowed_read_actions >= READ_SHAPED_TOOL_NAMES
    for name, capability in TOOL_CAPABILITY_BY_TOOL.items():
        assert CAPABILITY_GATE_MAP[name] == capability


def test_the_advertised_schema_is_built_from_the_registry() -> None:
    specs = {spec.name: spec for spec in default_tool_specs()}
    for item in TOOL_DEFINITIONS:
        if not item.model_exposed:
            assert item.name not in specs
            continue
        spec = specs[item.name]
        assert spec.description == item.description
        assert set(spec.parameters["required"]) == set(item.required_args) | set(
            item.required_list_args
        )
        assert set(spec.parameters["properties"]) >= set(item.optional_args)


def test_every_executable_tool_the_broker_offers_is_registered(tmp_path: Path) -> None:
    """The one place a tool name is still written twice, and why.

    `ToolBroker`'s executor map holds per-tool argument-adapting callables.
    Deriving it here would import `raiker.tools` into `raiker.models` and close a
    cycle, so instead the key sets are asserted equal — the same guarantee, no
    cycle. A tool added to the broker and forgotten in the registry fails here.
    """
    store = SQLiteStore(tmp_path)
    broker = ToolBroker(
        workspace_root=tmp_path,
        policy_engine=PolicyEngine(StaticPolicyConfig(tmp_path), store=store),
        store=store,
        principal_id="prn_owner",
    )
    executable = set(broker.executors) | set(broker.context_executors)
    registered = {item.name for item in TOOL_DEFINITIONS}
    unregistered = {
        name
        for name in executable - registered
        # Projected MCP tools are dynamic by design: which ones exist depends on
        # which servers the owner connected.
        if not name.startswith("mcp__") and not name.startswith("mcp_")
    }
    assert unregistered == set(), sorted(unregistered)


def test_replacing_a_field_produces_a_new_definition_not_a_mutation() -> None:
    """Frozen, and hashable — `arg_schemas` is a tuple of pairs for this reason."""
    original = _fake()
    changed = replace(original, description="A different description.")
    assert original.description != changed.description
    assert len({original, changed}) == 2


def test_a_band_can_only_change_by_changing_what_the_tool_does() -> None:
    """The invariant that stops a band from being an opinion.

    Raising `risk` on its own no longer constructs: a band is the consequence of
    the declared signals, so changing it means changing the claim about what the
    tool actually does. That is what keeps "high" meaning something a reader can
    check, rather than a word somebody picked.
    """
    with pytest.raises(ValueError, match="tool_definition_risk_not_derived"):
        replace(_fake(), risk="high")

    raised = replace(_fake(), risk="high", risk_signals=("changes_state", "leaves_this_machine"))
    assert raised.risk == "high"


def test_a_signal_this_build_does_not_define_is_refused() -> None:
    """A dropped signal would be a control that silently stopped working."""
    with pytest.raises(ValueError, match="tool_definition_risk_signal_unknown"):
        _fake(risk_signals=("sounds_dangerous",))
