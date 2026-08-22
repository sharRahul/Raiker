"""The hooks surface: what is configured, whether it can fire, and what it did.

Hooks were the one extension surface with a real, enforcing backend and no way
to see it. Three properties this file exists to hold:

1. **A configuration file Raiker cannot read must not take the runtime with it.**
   ``HooksRegistry.load`` runs inside the ``AgentGateway`` constructor, so a typo
   in ``.raiker/hooks.json`` used to make *every prompt in the product* fail with
   a raw ``JSONDecodeError``. Failing closed for that file is right; failing
   closed for the whole runtime, silently, is not.
2. **A rule that can never fire has to say so.** ``HOOK_EVENTS`` is what a config
   may name; ``DISPATCHED_HOOK_EVENTS`` is what this build emits. The two differ,
   and the difference is derived here from the source rather than trusted, so the
   published set cannot drift from the code.
3. **A rule that cannot change an outcome has to say so.** Only ``PreToolUse``
   and ``PreCompact`` decisions are honoured, and only from a handler holding
   decision authority.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import utc_now
from raiker.control.dashboard import DashboardService
from raiker.gateway.agent_gateway import AgentGateway
from raiker.hooks.contracts import (
    DECIDING_HOOK_EVENTS,
    DISPATCHED_HOOK_EVENTS,
    HOOK_EVENT_SUMMARIES,
    HOOK_EVENTS,
    HookConfigError,
)
from raiker.hooks.owner_switch import hooks_disabled
from raiker.hooks.registry import HooksRegistry
from raiker.storage.sqlite import SQLiteStore

REPO_ROOT = Path(__file__).resolve().parents[1]

WORKING_CONFIG = {
    "schema_version": "1.0",
    "hooks": {
        "PreToolUse": [
            {
                "matcher": "shell",
                "if": "shell(rm -rf *)",
                "handlers": [
                    {"id": "block-rm", "type": "builtin", "builtin": "block_destructive_shell"}
                ],
            }
        ],
        "PostToolUse": [
            {
                "matcher": "*",
                "handlers": [
                    {
                        "id": "note-it",
                        "type": "command",
                        "command": ["scripts/note.sh"],
                        "timeout_ms": 1500,
                    }
                ],
            }
        ],
        "SessionEnd": [
            {
                "matcher": "*",
                "handlers": [
                    {"id": "on-end", "type": "command", "command": ["scripts/end.sh"]}
                ],
            }
        ],
    },
}


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir()
    (tmp_path / ".raiker").mkdir(exist_ok=True)
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    return tmp_path


def _write(workspace: Path, relative: str, text: str) -> None:
    path = workspace / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ── 1. A broken file must not take the runtime with it ───────────────────────


def test_a_malformed_hooks_file_loads_no_rules_and_does_not_raise(workspace: Path) -> None:
    _write(workspace, ".raiker/hooks.json", "{ this is not json")

    registry = HooksRegistry.load(workspace)

    assert registry.rules == []
    failed = registry.failed_sources()
    assert [source.path for source in failed] == [".raiker/hooks.json"]
    assert failed[0].error is not None and failed[0].error.startswith("invalid_json:")


def test_a_malformed_hooks_file_does_not_break_every_prompt(workspace: Path) -> None:
    _write(workspace, ".raiker/hooks.json", "{ this is not json")

    # The regression: this constructor raised, so no turn could run at all.
    gateway = AgentGateway(workspace)

    assert gateway.hook_dispatcher.is_active() is False


def test_a_broken_file_does_not_discard_a_good_one(workspace: Path) -> None:
    _write(workspace, "config/hooks.json", json.dumps(WORKING_CONFIG))
    _write(workspace, ".raiker/hooks.json", '{"schema_version": "0.9", "hooks": {}}')

    registry = HooksRegistry.load(workspace)

    assert [rule.event for rule in registry.rules] == ["PreToolUse", "PostToolUse", "SessionEnd"]
    assert [source.error for source in registry.failed_sources()] == ["invalid_hooks_config"]


def test_from_config_still_refuses_an_invalid_config(workspace: Path) -> None:
    # `load` is lenient about *files* so one typo cannot brick the product. The
    # explicit-parse path is not: a caller handing over a config wants to be told.
    with pytest.raises(HookConfigError, match="unknown_hook_event"):
        HooksRegistry.from_config(
            {"schema_version": "1.0", "hooks": {"Nope": [{"matcher": "*", "handlers": []}]}}
        )


# ── 1b. The owner can turn every hook off (BUG-222) ─────────────────────────


def _disable_hooks(workspace: Path, principal_id: str = "principal_owner") -> None:
    SQLiteStore(workspace).put_user_settings(
        principal_id, json.dumps({"hooks": {"disabled": True}}), utc_now()
    )


def test_the_owner_switch_stops_every_hook_without_touching_the_files(
    workspace: Path,
) -> None:
    _write(workspace, "config/hooks.json", json.dumps(WORKING_CONFIG))
    _disable_hooks(workspace)

    gateway = AgentGateway(workspace)
    gateway.hook_dispatcher.set_disabled(hooks_disabled(workspace, "principal_owner"))

    assert gateway.hook_dispatcher.is_active() is False
    # The rules are still loaded. Off is a state, not an erasure: the owner has to
    # be able to see what would run if they turned it back on.
    assert len(gateway.hook_dispatcher.registry.rules) == 3


def test_hooks_run_by_default(workspace: Path) -> None:
    # Configuring a hook is what asking for it to run means; the switch exists to
    # be reachable, not to be the posture.
    _write(workspace, "config/hooks.json", json.dumps(WORKING_CONFIG))

    gateway = AgentGateway(workspace)

    assert hooks_disabled(workspace, "principal_owner") is False
    assert gateway.hook_dispatcher.is_active() is True


def test_the_switch_is_an_owner_setting_not_a_fourth_config_file(workspace: Path) -> None:
    # A file a project ships must not be able to re-enable itself, so the switch
    # is never read from any of the three hook sources.
    _write(
        workspace,
        "config/hooks.json",
        json.dumps({**WORKING_CONFIG, "disabled": False}),
    )
    _disable_hooks(workspace)

    assert hooks_disabled(workspace, "principal_owner") is True


def test_the_read_model_reports_the_switch_and_keeps_the_rules(workspace: Path) -> None:
    _write(workspace, "config/hooks.json", json.dumps(WORKING_CONFIG))
    _disable_hooks(workspace)

    view = DashboardService(workspace).list_hooks("principal_owner")

    assert view["disabled"] is True
    assert view["active"] is False
    assert view["rule_count"] == 3
    assert len(view["rules"]) == 3


# ── 2. The published dispatched set matches the real call sites ──────────────


def _dispatched_events_in_source() -> set[str]:
    """Every hook event name this build really emits, read out of the source."""
    found: set[str] = set()
    for path in (REPO_ROOT / "raiker").rglob("*.py"):
        if path.parts[-2:] == ("hooks", "contracts.py"):
            continue
        text = path.read_text(encoding="utf-8")
        found.update(re.findall(r'event_name=\s*"([A-Za-z]+)"', text))
        found.update(re.findall(r'_dispatch_lifecycle_hook\(\s*"([A-Za-z]+)"', text))
        # `_notify_hook("PostToolUse", …)` and its ternary form. Only this scan is
        # narrowed to known event names: the ternary also carries the unrelated
        # `result.status == "success"`. The two scans above stay unfiltered, so a
        # genuinely new event name still shows up here as a mismatch.
        for block in re.findall(r"_notify_hook\(\s*(.*?)\n", text, re.S):
            found.update(
                name for name in re.findall(r'"([A-Za-z]+)"', block) if name in HOOK_EVENTS
            )
    return found


def test_the_published_dispatched_events_match_the_code() -> None:
    assert _dispatched_events_in_source() == DISPATCHED_HOOK_EVENTS


def test_every_accepted_event_has_a_summary_and_the_gap_is_named() -> None:
    assert set(HOOK_EVENT_SUMMARIES) == HOOK_EVENTS
    assert DISPATCHED_HOOK_EVENTS <= HOOK_EVENTS
    # The gap is the point of the surface: a rule here parses and never runs.
    assert {"SessionEnd"} == HOOK_EVENTS - DISPATCHED_HOOK_EVENTS
    assert DECIDING_HOOK_EVENTS <= DISPATCHED_HOOK_EVENTS


# ── 3. The read model says all three things ─────────────────────────────────


def test_the_read_model_reports_authority_reach_and_provenance(workspace: Path) -> None:
    _write(workspace, "config/hooks.json", json.dumps(WORKING_CONFIG))
    _write(workspace, ".raiker/hooks.json", "{ broken")

    view = DashboardService(workspace).list_hooks()

    assert view["active"] is True
    assert view["rule_count"] == 3
    rules = {rule["event"]: rule for rule in view["rules"]}

    # A builtin on PreToolUse is the one rule that can change an outcome.
    assert rules["PreToolUse"]["can_decide"] is True
    assert rules["PreToolUse"]["dispatched"] is True
    assert rules["PreToolUse"]["if_guard"] == "shell(rm -rf *)"
    assert rules["PreToolUse"]["source"] == "config/hooks.json"
    assert rules["PreToolUse"]["handlers"][0]["decision_authority"] is True

    # PostToolUse is dispatched but observation-only: its decision is not honoured
    # and the command handler was not given authority either.
    assert rules["PostToolUse"]["dispatched"] is True
    assert rules["PostToolUse"]["can_decide"] is False
    assert rules["PostToolUse"]["handlers"][0]["decision_authority"] is False

    # SessionEnd parses and never fires.
    assert rules["SessionEnd"]["dispatched"] is False
    assert rules["SessionEnd"]["can_decide"] is False

    # And the file that could not be read is visible rather than silent.
    assert [source["path"] for source in view["failed_sources"]] == [".raiker/hooks.json"]


def test_a_rule_naming_an_unknown_builtin_is_not_reported_as_enforcing(
    workspace: Path,
) -> None:
    # `run_builtin` raises for a name this build does not have, so the rule
    # matches and then fails every time. Reporting it as "can deny" would be the
    # surface asserting a guard that is not there.
    _write(
        workspace,
        "config/hooks.json",
        json.dumps(
            {
                "schema_version": "1.0",
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "shell",
                            "handlers": [
                                {"id": "typo", "type": "builtin", "builtin": "deny"},
                            ],
                        }
                    ]
                },
            }
        ),
    )

    view = DashboardService(workspace).list_hooks()
    rule = view["rules"][0]

    assert rule["dispatched"] is True
    assert rule["can_decide"] is False
    assert rule["handlers"][0]["available"] is False
    assert rule["handlers"][0]["decision_authority"] is False
    # And the names that do exist are published, because this page cannot offer a
    # form and the owner is writing the file by hand.
    assert "block_destructive_shell" in view["builtins"]


def test_a_real_builtin_is_reported_as_enforcing(workspace: Path) -> None:
    _write(
        workspace,
        "config/hooks.json",
        json.dumps(
            {
                "schema_version": "1.0",
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "shell",
                            "handlers": [
                                {
                                    "id": "guard",
                                    "type": "builtin",
                                    "builtin": "block_destructive_shell",
                                }
                            ],
                        }
                    ]
                },
            }
        ),
    )

    rule = DashboardService(workspace).list_hooks()["rules"][0]

    assert rule["can_decide"] is True
    assert rule["handlers"][0]["available"] is True
    assert rule["handlers"][0]["decision_authority"] is True


def test_the_read_model_is_honest_when_nothing_is_configured(workspace: Path) -> None:
    view = DashboardService(workspace).list_hooks()

    assert view["active"] is False
    assert view["rules"] == []
    assert view["failed_sources"] == []
    # Every source is still listed, so "no hooks" and "I never looked" differ.
    assert {source["path"] for source in view["sources"]} == {
        "config/managed-hooks.json",
        "config/hooks.json",
        ".raiker/hooks.json",
    }
    assert all(source["exists"] is False for source in view["sources"])
    # The event catalogue is always available, so the owner can see what a rule
    # could name before writing one.
    assert {event["event"] for event in view["events"]} == HOOK_EVENTS
    assert {event["event"] for event in view["events"] if not event["dispatched"]} == {
        "SessionEnd"
    }
