"""A plugin that is installed now provides something (BUG-221).

Installing a plugin used to validate a manifest, verify a supply chain, resolve a
signature, write a record — and contribute nothing. The tab said so, which was
honest, but the surface as a whole read as an install flow for something that
could not be installed.

The answer this file holds to account is deliberately narrow: a plugin does not
get an execution surface of its own. It contributes through one that already
governs the thing contributed, and hooks are the first. Four properties follow,
and each is a test below:

1. **Asking is required.** No ``event:hook`` permission, no rules — and the
   refusal is named on the plan the owner reads *before* installing.
2. **A plugin cannot outrank the owner.** ``plugin`` sits below ``managed``,
   ``user``, ``project`` and ``local``, so a plugin rule can make an action
   stricter and can never override a deny the owner set.
3. **Revocation has teeth.** Revoking removes the rules from disk rather than
   annotating a record, because ``HooksRegistry.load`` reads files and has no
   store to consult.
4. **A broken contribution takes nothing else with it.** The same fail-closed
   property the three owner-authored config files already have.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.control.dashboard import DashboardService
from raiker.hooks.contracts import HOOK_SCOPES
from raiker.hooks.registry import PLUGIN_HOOKS_DIR, HooksRegistry
from raiker.plugins.contributions import (
    HOOK_CONTRIBUTION_PERMISSION,
    PluginContributionError,
    contribution_summary,
    install_contributions,
    installed_contributions,
    plugin_hooks_path,
    remove_contributions,
)
from raiker.plugins.policy import plan_plugin_registration

HOOKS_BLOCK = {
    "PreToolUse": [
        {
            "matcher": "shell",
            "handlers": [
                {"id": "plugin-guard", "type": "builtin", "builtin": "block_destructive_shell"}
            ],
        }
    ],
    "PostToolUse": [
        {
            "matcher": "*",
            "handlers": [
                {"id": "plugin-note", "type": "command", "command": ["scripts/note.sh"]}
            ],
        }
    ],
}


def _manifest(**overrides: Any) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "id": "acme-guard",
        "name": "Acme Guard",
        "version": "1.2.0",
        "trust_level": "local_dev",
        "permissions": [HOOK_CONTRIBUTION_PERMISSION],
        "contributes": {"hooks": HOOKS_BLOCK},
    }
    manifest.update(overrides)
    # Supply-chain fields are required before any plan is not denied, so a
    # contribution test that omitted them would only ever prove the denial. They
    # are computed after the overrides so they cover the manifest under test.
    from raiker.plugins.verify import plugin_checksum

    manifest["supply_chain"] = {"checksum": plugin_checksum(manifest), "signature": "sig-acme"}
    return manifest


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir(exist_ok=True)
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    return tmp_path


def _install(workspace: Path, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest = manifest if manifest is not None else _manifest()
    return install_contributions(
        workspace,
        manifest,
        plugin_id=str(manifest["id"]),
        permissions=list(manifest.get("permissions", [])),
    )


# ── 1. Asking is required, and the refusal is named on the plan ──────────────


def test_a_plugin_that_did_not_ask_contributes_nothing(workspace: Path) -> None:
    manifest = _manifest(permissions=["memory:read"])

    summary = _install(workspace, manifest)

    assert summary["hooks"] == 0
    assert summary["refused"] == [
        f"hooks_contribution_requires_permission:{HOOK_CONTRIBUTION_PERMISSION}"
    ]
    assert HooksRegistry.load(workspace).rules == []


def test_the_plan_says_what_the_plugin_would_provide_before_it_is_installed() -> None:
    # The permission diff the owner reads has to answer "and what does it do?",
    # or approving it is a decision made without the relevant fact.
    plan = plan_plugin_registration(_manifest()).to_dict()

    assert plan["contributions"]["hooks"] == 2
    assert plan["contributions"]["events"] == ["PostToolUse", "PreToolUse"]
    assert plan["contributions"]["refused"] == []


def test_the_plan_names_the_refusal_rather_than_reporting_nothing() -> None:
    plan = plan_plugin_registration(_manifest(permissions=["memory:read"])).to_dict()

    assert plan["contributions"]["hooks"] == 0
    assert plan["contributions"]["refused"] != []


def test_asking_to_contribute_hooks_is_never_silently_approved() -> None:
    # `event:hook` is not in SAFE_READ_ONLY, so a plugin asking for it cannot be
    # auto-planned: the owner has to see it. That is the whole reason the
    # permission is required rather than inferred from the manifest's contents.
    plan = plan_plugin_registration(_manifest())

    assert plan.status == "pending_approval"


def test_a_plugin_with_no_contributes_block_is_not_an_error() -> None:
    summary = contribution_summary({"id": "plain", "permissions": []}, [])

    assert summary == {"hooks": 0, "events": [], "refused": []}


# ── 2. A plugin cannot outrank the owner ─────────────────────────────────────


def test_plugin_rules_load_at_plugin_scope_below_every_owner_scope(
    workspace: Path,
) -> None:
    _install(workspace)

    rules = HooksRegistry.load(workspace).rules

    assert {rule.scope for rule in rules} == {"plugin"}
    plugin_rank = HOOK_SCOPES.index("plugin")
    for owner_scope in ("managed", "user", "project", "local"):
        assert HOOK_SCOPES.index(owner_scope) < plugin_rank


def test_a_plugin_rule_cannot_override_a_managed_deny(workspace: Path) -> None:
    from raiker.hooks.decision import HandlerDecision, combine

    _install(workspace)

    # Whatever a plugin returns, a managed deny stands. Hooks may only make an
    # action stricter, so there is no value a plugin handler can return that
    # widens one — this asserts the property rather than trusting the ordering.
    for plugin_decision in ("allow", "ask", "no_decision", "deny"):
        assert (
            combine(
                [
                    HandlerDecision("managed", "deny", True),
                    HandlerDecision("plugin", plugin_decision, True),
                ]
            )
            == "deny"
        )


def test_the_owner_switch_reaches_plugin_rules_too(workspace: Path) -> None:
    from raiker.hooks.dispatcher import HookDispatcher

    _install(workspace)
    dispatcher = HookDispatcher(HooksRegistry.load(workspace), workspace_root=workspace)
    assert dispatcher.is_active() is True

    dispatcher.set_disabled(True)

    assert dispatcher.is_active() is False


# ── 3. Revocation has teeth ──────────────────────────────────────────────────


def test_revoking_removes_the_rules_from_disk(workspace: Path) -> None:
    _install(workspace)
    assert len(HooksRegistry.load(workspace).rules) == 2

    assert remove_contributions(workspace, "acme-guard") is True

    assert HooksRegistry.load(workspace).rules == []
    assert not plugin_hooks_path(workspace, "acme-guard").exists()


def test_the_revocation_executor_removes_them(workspace: Path) -> None:
    """The state this prevents: the page says revoked, the runtime still runs it.

    An install record flipped to ``revoked`` stops the brokered execution path,
    but ``HooksRegistry.load`` reads files and never sees a record — so unless
    revocation deletes the file, a revoked plugin keeps enforcing.
    """
    from raiker.plugins.registry import record_plugin_install
    from raiker.runtime.authority.models import Principal, PrincipalType
    from raiker.runtime.authority.router import GovernedAction
    from raiker.runtime.executors.tier4_plugins import PluginRevocationExecutor
    from raiker.storage.sqlite import SQLiteStore

    store = SQLiteStore(workspace)
    _install(workspace)
    record_plugin_install(
        store=store,
        plugin_id="acme-guard",
        version="1.2.0",
        trust_level="local_dev",
        permissions_json=json.dumps([HOOK_CONTRIBUTION_PERMISSION]),
    )

    result = PluginRevocationExecutor(workspace, store).execute(
        GovernedAction(
            action_id="act_1",
            principal_id="principal_owner",
            action_type="plugin_revocation",
            tool_or_service_name="plugin_revocation_cap",
            arguments={"plugin_id": "acme-guard", "reason": "no longer needed"},
        ),
        Principal(
            principal_id="principal_owner",
            principal_type=PrincipalType.HUMAN,
            display_name="Owner",
        ),
    )

    assert result.ok is True
    assert result.artifacts["contributions_removed"] is True
    assert HooksRegistry.load(workspace).rules == []


def test_reinstalling_replaces_rather_than_accumulates(workspace: Path) -> None:
    # A stale copy of an older version's rules would still be loaded, so an
    # upgrade that dropped a rule has to drop it here too.
    _install(workspace)
    _install(workspace, _manifest(contributes={"hooks": {"PreToolUse": HOOKS_BLOCK["PreToolUse"]}}))

    rules = HooksRegistry.load(workspace).rules

    assert [rule.event for rule in rules] == ["PreToolUse"]


def test_an_upgrade_that_contributes_nothing_removes_the_old_rules(
    workspace: Path,
) -> None:
    _install(workspace)

    _install(workspace, _manifest(contributes={}))

    assert HooksRegistry.load(workspace).rules == []


# ── 4. Fail-closed, and nothing else goes with it ────────────────────────────


def test_an_unsafe_plugin_id_is_refused_rather_than_sanitised(workspace: Path) -> None:
    # Sanitising invites two ids collapsing onto the same folder, where one
    # plugin would silently overwrite another's rules.
    with pytest.raises(PluginContributionError, match="unsafe_plugin_id"):
        plugin_hooks_path(workspace, "../../etc")


def test_a_malformed_contribution_is_refused_at_plan_time(workspace: Path) -> None:
    manifest = _manifest(contributes={"hooks": {"NotAnEvent": [{"matcher": "*", "handlers": []}]}})

    summary = _install(workspace, manifest)

    assert summary["hooks"] == 0
    assert any(reason.startswith("invalid_hooks_contribution:") for reason in summary["refused"])
    assert HooksRegistry.load(workspace).rules == []


def test_a_broken_plugin_file_does_not_discard_the_owners_rules(workspace: Path) -> None:
    (workspace / "config" / "hooks.json").write_text(
        json.dumps({"schema_version": "1.0", "hooks": {"PreToolUse": HOOKS_BLOCK["PreToolUse"]}}),
        encoding="utf-8",
    )
    broken = workspace / PLUGIN_HOOKS_DIR / "rogue" / "hooks.json"
    broken.parent.mkdir(parents=True, exist_ok=True)
    broken.write_text("{ not json", encoding="utf-8")

    registry = HooksRegistry.load(workspace)

    assert [rule.scope for rule in registry.rules] == ["project"]
    assert [source.path for source in registry.failed_sources()] == [
        f"{PLUGIN_HOOKS_DIR}/rogue/hooks.json"
    ]


def test_each_plugin_rule_names_the_plugin_it_came_from(workspace: Path) -> None:
    # Two plugins load at the same scope, so scope stopped identifying a file.
    # Crediting one plugin with another's rules is the failure this rules out.
    _install(workspace)
    _install(workspace, _manifest(id="beta-watch"))

    view = DashboardService(workspace).list_hooks()
    sources = {rule["source"] for rule in view["rules"]}

    assert sources == {
        f"{PLUGIN_HOOKS_DIR}/acme-guard/hooks.json",
        f"{PLUGIN_HOOKS_DIR}/beta-watch/hooks.json",
    }


# ── The read model says what is installed and what it provides ───────────────


def test_the_read_model_reports_what_each_plugin_provides(workspace: Path) -> None:
    from raiker.plugins.registry import record_plugin_install
    from raiker.storage.sqlite import SQLiteStore

    _install(workspace)
    record_plugin_install(
        store=SQLiteStore(workspace),
        plugin_id="acme-guard",
        version="1.2.0",
        trust_level="local_dev",
        permissions_json=json.dumps([HOOK_CONTRIBUTION_PERMISSION]),
    )

    view = DashboardService(workspace).list_plugins()

    assert view["plugins"][0]["contributions"]["hooks"] == 2
    assert view["plugins"][0]["contributions"]["events"] == ["PostToolUse", "PreToolUse"]
    # And the surface says what a plugin *may* contribute, so "provides nothing"
    # and "may not provide anything" stay distinguishable.
    kinds = {entry["kind"]: entry["available"] for entry in view["contribution_kinds"]}
    assert kinds["hooks"] is True
    assert kinds["panels"] is False


def test_contributions_are_read_from_disk_not_from_the_record(workspace: Path) -> None:
    # The files are what the runtime loads. Reporting from the manifest instead
    # could claim a contribution the runtime does not have.
    _install(workspace)
    remove_contributions(workspace, "acme-guard")

    assert installed_contributions(workspace) == {}
