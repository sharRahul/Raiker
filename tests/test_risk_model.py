"""What "low", "medium", "high" and "critical" mean, and that they still mean it.

Raiker validated risk bands against a four-name set and defined none of them. The
symptom was not a crash: it was that every tool's band happened to equal
`read_shaped ? medium : high`, four names carried one bit, and `low` and
`critical` were unreachable although both have real runtime behaviour behind
them — `auto` runs only `low` unprompted, and `critical` takes the human-only
floor.

These tests hold the definitions to being definitions:

* a band is derived from declared properties, never chosen;
* raising a band means changing the claim about what a tool does;
* every band a consumer branches on is reachable by something;
* the modules that used to restate a band now read it.
"""

from __future__ import annotations

import pytest

from raiker.contracts.models import RISK_LEVELS
from raiker.models.tool_call_validation import risk_for_tool
from raiker.models.tool_registry import TOOL_DEFINITIONS, mcp_tool_risk_band, tool_risk_band
from raiker.policy.risk import (
    BLOCKED,
    RISK_BANDS,
    RISK_SIGNALS,
    RiskModelError,
    assess,
    band,
    describe_risk_model,
    rank,
    strictest,
)

# ── The vocabulary is defined, not just validated ────────────────────────────


def test_every_name_the_contract_accepts_is_defined_or_is_the_refusal() -> None:
    """No band may exist that nothing explains.

    `RISK_LEVELS` is what a `ToolAction` will accept. Every one of those names
    now has to be either a defined band or the terminal refusal record, because
    a name a contract accepts and no document defines is exactly what this
    module was written to remove.
    """
    defined = {item.name for item in RISK_BANDS} | {BLOCKED}
    assert defined == set(RISK_LEVELS)


def test_each_band_says_what_puts_an_action_in_it_and_what_undoes_it() -> None:
    for item in RISK_BANDS:
        assert item.summary.strip(), item.name
        # The two fields that carry the actual promise. A band whose definition
        # or undo story is blank is a word again.
        assert len(item.definition) > 80, item.name
        assert item.undo.strip(), item.name
        assert item.disposition.strip(), item.name
        assert item.examples, item.name


def test_the_bands_are_totally_ordered_and_the_refusal_outranks_them_all() -> None:
    ranks = [rank(item.name) for item in RISK_BANDS]
    assert ranks == sorted(ranks)
    assert len(set(ranks)) == len(ranks)
    # A refusal must never compare as milder than the worst band.
    assert rank(BLOCKED) > max(ranks)


def test_an_unknown_band_is_an_error_rather_than_a_default() -> None:
    with pytest.raises(RiskModelError):
        band("spicy")
    with pytest.raises(RiskModelError):
        rank("spicy")


# ── Assessment raises floors and never lowers them ───────────────────────────


def test_nothing_raised_is_the_declared_band() -> None:
    assert assess(declared="medium").band == "medium"
    assert assess(declared="medium", signals={}).band == "medium"


def test_a_signal_raises_the_band_and_is_recorded() -> None:
    result = assess(declared="low", signals={"leaves_this_machine": True})
    assert result.band == "high"
    assert result.signals == ("leaves_this_machine",)
    assert "risk_signal:leaves_this_machine" in result.reasons
    assert "risk_band:high" in result.reasons


def test_a_signal_can_never_lower_a_declared_band() -> None:
    """The asymmetry the whole model rests on.

    `changes_state` floors at medium. Applied to a tool that already declares
    `high`, it must leave it at high — otherwise a context that looked mild
    would be a way to talk a dangerous action down, which is the shape of every
    permission bypass.
    """
    assert assess(declared="high", signals={"changes_state": True}).band == "high"


def test_the_highest_floor_wins_so_signals_never_argue() -> None:
    result = assess(
        declared="low",
        signals={"changes_state": True, "changes_authority": True, "leaves_this_machine": True},
    )
    assert result.band == "critical"


def test_an_owner_floor_may_raise_and_is_recorded() -> None:
    result = assess(declared="low", owner_floor="high")
    assert result.band == "high"
    assert "risk_owner_floor:high" in result.reasons


def test_an_owner_floor_below_the_declared_band_changes_nothing() -> None:
    """An owner setting can make Raiker ask more often. That is all it can do."""
    assert assess(declared="high", owner_floor="low").band == "high"


def test_a_signal_this_build_does_not_define_is_refused() -> None:
    """A silently dropped signal would be a control that stopped working quietly."""
    with pytest.raises(RiskModelError, match="unknown_risk_signal"):
        assess(declared="low", signals={"sounds_bad": True})


def test_strictest_is_low_when_asked_about_nothing() -> None:
    assert strictest() == "low"
    assert strictest("low", "critical", "medium") == "critical"


# ── The registry declares properties, and the band follows ───────────────────


def test_every_tool_band_is_derived_from_its_own_signals() -> None:
    """Enforced at import by `__post_init__`; asserted here so the reason is stated.

    A definition whose declared band disagrees with its declared signals does not
    construct, so this can only fail if that check is removed.
    """
    for definition in TOOL_DEFINITIONS:
        derived = assess(
            declared="low", signals=dict.fromkeys(definition.risk_signals, True)
        ).band
        assert derived == definition.risk, definition.name


def test_a_tool_that_declares_no_signal_is_low_and_that_is_the_point() -> None:
    """`low` is a claim, not an omission: it says this changes and reaches nothing."""
    silent = [d for d in TOOL_DEFINITIONS if not d.risk_signals]
    assert silent, "no tool is low, which is the state this model was written to fix"
    assert {d.risk for d in silent} == {"low"}


def test_the_bands_a_consumer_branches_on_are_reachable() -> None:
    """The defect that started this.

    `auto_requires_approval` runs only `low` unprompted and the router floors
    `critical` to a human. Before the reclassification no tool produced either,
    so both branches were dead: 31 tools were medium, 15 were high, and `auto`
    could never run anything without asking. `critical` is reached through
    `classify_critical` at the authority layer rather than by a tool declaring
    it, which is why it is checked there rather than here.
    """
    bands = {d.risk for d in TOOL_DEFINITIONS}
    assert "low" in bands
    assert "medium" in bands
    assert "high" in bands


def test_leaving_the_machine_is_never_below_high() -> None:
    """The conformance rule that catches the next mistake rather than this one.

    A tool that declares it leaves the machine, spends the owner's credential, or
    is visible to somebody else cannot be banded below `high` — the definition
    says so, and this asserts the definitions are applied rather than admired.
    """
    outward = {"leaves_this_machine", "observable_by_others", "spends_owner_credential"}
    for definition in TOOL_DEFINITIONS:
        if outward & set(definition.risk_signals):
            assert rank(definition.risk) >= rank("high"), definition.name


def test_a_local_read_is_not_banded_like_a_credentialled_one() -> None:
    """The distinction the old two-band vocabulary could not express."""
    assert tool_risk_band("read_file") == "low"
    assert tool_risk_band("gmail_read") == "high"
    assert tool_risk_band("web_fetch") == "high"
    assert tool_risk_band("consult_advisor") == "high"


def test_an_unregistered_tool_has_no_band_rather_than_a_default() -> None:
    with pytest.raises(ValueError, match="unknown_tool_risk"):
        tool_risk_band("no_such_tool")


def test_a_projected_mcp_tool_carries_the_declared_class_band() -> None:
    assert mcp_tool_risk_band() == "high"
    assert risk_for_tool("mcp__server__anything") == "high"


def test_every_delegable_tool_is_low_so_the_subagent_cannot_launder_one() -> None:
    """Why the subagent runner may read the band instead of asserting it.

    It used to write `low` for every step. That was true of every delegable tool
    and would have stopped being true the moment one was marked delegable, with
    no failure to notice — and `low` is the band `auto` runs unprompted.
    """
    for definition in TOOL_DEFINITIONS:
        if definition.delegable:
            assert definition.risk == "low", definition.name
            assert risk_for_tool(definition.name) == "low", definition.name


# ── The model is readable, which is what "not hard-coded" means here ─────────


def test_the_whole_model_renders_as_data() -> None:
    described = describe_risk_model()
    assert [item["name"] for item in described["bands"]] == [b.name for b in RISK_BANDS]
    assert {item["name"] for item in described["signals"]} == {s.name for s in RISK_SIGNALS}
    for item in described["signals"]:
        assert item["raises_to"] in {b.name for b in RISK_BANDS}
        assert item["question"].endswith("?"), item["name"]
    assert described["rules"]
