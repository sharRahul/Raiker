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
    MAX_CONTRIBUTED_SKILLS,
    MCP_CONTRIBUTION_PERMISSION,
    SKILL_CONTRIBUTION_PERMISSION,
    PluginContributionError,
    contribution_summary,
    install_contributions,
    installed_contributions,
    plugin_hooks_path,
    plugin_skills_dir,
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

    assert summary == {
        "hooks": 0,
        "events": [],
        "skills": 0,
        "skill_names": [],
        "mcp_servers": 0,
        "mcp_server_names": [],
        "refused": [],
    }


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


# ── Skills: the second contribution kind, held to the same bar ───────────────
#
# A skill runs nothing, which is why it came second and not first. What it does
# do is put instruction text into the owner's turns, so "harmless" is the wrong
# frame: the five properties below are the ones that make it safe to offer.

SKILLS_BLOCK = [
    {
        "name": "acme-review",
        "description": "Review a change against Acme's internal checklist.",
        "body": "Check the changelog, then the tests, then the migration.",
    },
    {
        "name": "acme-release",
        "document": (
            "---\nname: acme-release\ndescription: Cut an Acme release.\n---\n\nTag, then ship.\n"
        ),
    },
]


def _skill_manifest(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "acme-skills",
        "name": "Acme Skills",
        "version": "2.0.0",
        "trust_level": "local_dev",
        "permissions": [SKILL_CONTRIBUTION_PERMISSION],
        "contributes": {"skills": SKILLS_BLOCK},
    }
    base.update(overrides)
    from raiker.plugins.verify import plugin_checksum

    base["supply_chain"] = {"checksum": plugin_checksum(base), "signature": "sig-acme"}
    return base


def _owner(workspace: Path) -> str:
    from raiker.cli.principal_resolver import resolve_local_principal

    principal, _ = resolve_local_principal(workspace, None)
    assert principal is not None
    return principal.principal_id


def test_a_plugin_that_did_not_ask_contributes_no_skills(workspace: Path) -> None:
    manifest = _skill_manifest(permissions=["memory:read"])

    summary = _install(workspace, manifest)

    assert summary["skills"] == 0
    assert summary["refused"] == [
        f"skills_contribution_requires_permission:{SKILL_CONTRIBUTION_PERMISSION}"
    ]
    assert not plugin_skills_dir(workspace, "acme-skills").exists()


def test_asking_for_a_skill_is_read_before_the_install(workspace: Path) -> None:
    plan = plan_plugin_registration(_skill_manifest()).to_dict()

    # `skill:contribute` is outside SAFE_READ_ONLY on purpose: asking for it puts
    # the plugin in front of the owner rather than through on the read-only path.
    assert plan["status"] == "pending_approval"
    assert plan["contributions"]["skills"] == 2
    assert plan["contributions"]["skill_names"] == ["acme-review", "acme-release"]
    assert plan["execution_enabled"] is False


def test_a_contributed_skill_arrives_switched_off(workspace: Path) -> None:
    from raiker.skills.service import SkillsService

    _install(workspace, _skill_manifest())
    principal_id = _owner(workspace)

    skills = {skill.name: skill for skill in SkillsService(workspace).list_skills(principal_id)}

    assert skills["acme-review"].source == "plugin"
    assert skills["acme-review"].source_ref == "acme-skills"
    # Installing the plugin was consent to *offer* the skill, not to run with it.
    assert skills["acme-review"].active is False
    assert skills["acme-release"].active is False
    active = dict(SkillsService(workspace).active_skill_documents(principal_id))
    assert "acme-review" not in active
    assert "acme-release" not in active


def test_the_owners_on_off_choice_survives_a_refresh(workspace: Path) -> None:
    from raiker.skills.service import SkillsService

    _install(workspace, _skill_manifest())
    service = SkillsService(workspace)
    principal_id = _owner(workspace)
    review = next(s for s in service.list_skills(principal_id) if s.name == "acme-review")
    assert service.set_active(principal_id, review.skill_id, True).ok

    # Re-installing the same plugin must not silently switch a skill the owner
    # turned on back off — or, worse, turn one on that they turned off.
    _install(workspace, _skill_manifest())
    names = dict(service.active_skill_documents(principal_id))

    assert "acme-review" in names
    assert "acme-release" not in names


def test_revoking_the_plugin_removes_its_skills_from_the_runtime(workspace: Path) -> None:
    from raiker.skills.service import SkillsService

    _install(workspace, _skill_manifest())
    service = SkillsService(workspace)
    principal_id = _owner(workspace)
    review = next(s for s in service.list_skills(principal_id) if s.name == "acme-review")
    assert service.set_active(principal_id, review.skill_id, True).ok

    remove_contributions(workspace, "acme-skills")

    # The runtime reads through the same sync, so an active row cannot outlive
    # the file that authorised it.
    assert "acme-review" not in dict(service.active_skill_documents(principal_id))
    assert [s.name for s in service.list_skills(principal_id) if s.source == "plugin"] == []


def test_a_plugin_skill_never_overwrites_one_the_owner_installed(workspace: Path) -> None:
    from raiker.skills.service import SkillsService

    service = SkillsService(workspace)
    principal_id = _owner(workspace)
    assert service.build_skill(principal_id, "acme-review", "Mine, not theirs.", "Body.").ok

    _install(workspace, _skill_manifest())
    mine = next(s for s in service.list_skills(principal_id) if s.name == "acme-review")

    assert mine.source == "built"
    assert mine.description == "Mine, not theirs."


def test_a_plugin_skill_is_not_the_owners_to_rename_or_delete(workspace: Path) -> None:
    from raiker.skills.service import SkillsService

    _install(workspace, _skill_manifest())
    service = SkillsService(workspace)
    principal_id = _owner(workspace)
    review = next(s for s in service.list_skills(principal_id) if s.name == "acme-review")

    # Both would be undone by the next sync, so both say so rather than pretending.
    assert service.rename(principal_id, review.skill_id, "mine").reason_code == (
        "skill_provided_by_plugin"
    )
    assert service.delete(principal_id, review.skill_id).reason_code == "skill_provided_by_plugin"


def test_one_malformed_skill_does_not_take_the_others_with_it(workspace: Path) -> None:
    manifest = _skill_manifest(
        contributes={"skills": [SKILLS_BLOCK[0], {"name": "NoDescription", "body": "x"}]}
    )

    summary = _install(workspace, manifest)

    assert summary["skills"] == 1
    assert summary["skill_names"] == ["acme-review"]
    assert summary["refused"] == ["invalid_skill_contribution:1:skill_missing_description"]


def test_broken_hooks_do_not_cost_a_plugin_its_valid_skills(workspace: Path) -> None:
    manifest = _skill_manifest(
        permissions=[SKILL_CONTRIBUTION_PERMISSION, HOOK_CONTRIBUTION_PERMISSION],
        contributes={
            "skills": SKILLS_BLOCK,
            "hooks": {"PreToolUse": [{"matcher": "shell", "handlers": [{"type": "nonsense"}]}]},
        },
    )

    summary = _install(workspace, manifest)

    assert summary["hooks"] == 0
    assert summary["skills"] == 2
    assert any(reason.startswith("invalid_hooks_contribution") for reason in summary["refused"])


def test_the_plugins_tab_reports_contributed_skills(workspace: Path) -> None:
    from raiker.plugins.registry import record_plugin_install
    from raiker.storage.sqlite import SQLiteStore

    _install(workspace, _skill_manifest())
    record_plugin_install(
        store=SQLiteStore(workspace),
        plugin_id="acme-skills",
        version="2.0.0",
        trust_level="local_dev",
        permissions_json=json.dumps([SKILL_CONTRIBUTION_PERMISSION]),
    )

    view = DashboardService(workspace).list_plugins()

    contributions = view["plugins"][0]["contributions"]
    assert contributions["skills"] == 2
    assert contributions["skill_names"] == ["acme-release", "acme-review"]
    kinds = {entry["kind"]: entry["available"] for entry in view["contribution_kinds"]}
    assert kinds["skills"] is True


def test_a_manifest_cannot_flood_the_skill_list(workspace: Path) -> None:
    many = [
        {"name": f"skill-{index}", "description": "d", "body": "b"}
        for index in range(MAX_CONTRIBUTED_SKILLS + 1)
    ]

    summary = _install(workspace, _skill_manifest(contributes={"skills": many}))

    assert summary["skills"] == 0
    assert summary["refused"] == [f"too_many_skills:{MAX_CONTRIBUTED_SKILLS + 1}>{MAX_CONTRIBUTED_SKILLS}"]


# ── MCP servers: offered, never connected ────────────────────────────────────
#
# The third contribution kind is the one where "goes through the gate rather than
# around it" is the whole design. A plugin may *describe* a server. It cannot add
# one, connect one, or reach one — the owner adds it through the same governed
# create path they would use to type it in themselves.

MCP_BLOCK = [
    {
        "name": "acme-docs",
        "transport": "http",
        "endpoint_url": "https://mcp.acme.example/v1",
        "auth_ref": "ACME_MCP_TOKEN",
        "description": "Acme's internal documentation index.",
    }
]


def _mcp_manifest(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "acme-mcp",
        "name": "Acme MCP",
        "version": "1.0.0",
        "trust_level": "local_dev",
        "permissions": [MCP_CONTRIBUTION_PERMISSION],
        "contributes": {"mcp_servers": MCP_BLOCK},
    }
    base.update(overrides)
    from raiker.plugins.verify import plugin_checksum

    base["supply_chain"] = {"checksum": plugin_checksum(base), "signature": "sig-acme"}
    return base


def test_a_plugin_that_did_not_ask_offers_no_mcp_server(workspace: Path) -> None:
    summary = _install(workspace, _mcp_manifest(permissions=["memory:read"]))

    assert summary["mcp_servers"] == 0
    assert summary["refused"] == [
        f"mcp_contribution_requires_permission:{MCP_CONTRIBUTION_PERMISSION}"
    ]


def test_an_offered_server_is_not_a_server(workspace: Path) -> None:
    _install(workspace, _mcp_manifest())
    principal_id = _owner(workspace)
    service = DashboardService(workspace)

    # The offer is readable…
    offers = service.list_mcp_offers(principal_id)
    assert [offer["name"] for offer in offers] == ["acme-docs"]
    assert offers[0]["plugin_id"] == "acme-mcp"
    assert offers[0]["already_added"] is False
    # …and nothing was added, connected or made reachable by the install.
    assert service.list_mcp_servers(principal_id) == []


def test_an_offer_the_owner_took_up_reads_as_taken_up(workspace: Path) -> None:
    _install(workspace, _mcp_manifest())
    principal_id = _owner(workspace)
    service = DashboardService(workspace)
    # Added through the ordinary governed create path — the same one the owner
    # would use by hand, which is the point of an offer being only a description.
    assert service.create_remote_mcp_server(
        principal_id, "acme-docs", "https://mcp.acme.example/v1", "ACME_MCP_TOKEN"
    ).ok

    assert service.list_mcp_offers(principal_id)[0]["already_added"] is True


def test_an_offer_cannot_carry_a_credential_or_a_plaintext_endpoint(workspace: Path) -> None:
    for endpoint in (
        "http://mcp.acme.example/v1",
        "https://user:token@mcp.acme.example/v1",
    ):
        summary = _install(
            workspace,
            _mcp_manifest(
                contributes={"mcp_servers": [{**MCP_BLOCK[0], "endpoint_url": endpoint}]}
            ),
        )
        assert summary["mcp_servers"] == 0
        assert summary["refused"] == ["invalid_mcp_contribution:0:invalid_endpoint"]


def test_an_offer_names_an_environment_variable_never_a_token(workspace: Path) -> None:
    summary = _install(
        workspace,
        _mcp_manifest(
            contributes={"mcp_servers": [{**MCP_BLOCK[0], "auth_ref": "sk-live-not-a-var-name"}]}
        ),
    )

    assert summary["mcp_servers"] == 0
    assert summary["refused"] == ["invalid_mcp_contribution:0:invalid_auth_ref"]


def test_revoking_the_plugin_withdraws_its_offers(workspace: Path) -> None:
    _install(workspace, _mcp_manifest())
    principal_id = _owner(workspace)

    remove_contributions(workspace, "acme-mcp")

    assert DashboardService(workspace).list_mcp_offers(principal_id) == []


def test_a_hand_edited_offer_file_cannot_smuggle_in_an_endpoint(workspace: Path) -> None:
    from raiker.plugins.contributions import plugin_mcp_path

    _install(workspace, _mcp_manifest())
    path = plugin_mcp_path(workspace, "acme-mcp")
    path.write_text(
        json.dumps({"servers": [{**MCP_BLOCK[0], "endpoint_url": "http://evil.example"}]}),
        encoding="utf-8",
    )

    # Offers are re-validated on read, so editing the file after the install
    # cannot produce an offer the write path would have refused.
    assert DashboardService(workspace).list_mcp_offers(_owner(workspace)) == []


def test_the_plugins_tab_reports_offered_servers(workspace: Path) -> None:
    from raiker.plugins.registry import record_plugin_install
    from raiker.storage.sqlite import SQLiteStore

    _install(workspace, _mcp_manifest())
    record_plugin_install(
        store=SQLiteStore(workspace),
        plugin_id="acme-mcp",
        version="1.0.0",
        trust_level="local_dev",
        permissions_json=json.dumps([MCP_CONTRIBUTION_PERMISSION]),
    )

    view = DashboardService(workspace).list_plugins()

    assert view["plugins"][0]["contributions"]["mcp_servers"] == 1
    assert view["plugins"][0]["contributions"]["mcp_server_names"] == ["acme-docs"]
    kinds = {entry["kind"]: entry["available"] for entry in view["contribution_kinds"]}
    assert kinds["mcp_servers"] is True
    # Panels are still the one kind with no authority story, and still say so.
    assert kinds["panels"] is False
