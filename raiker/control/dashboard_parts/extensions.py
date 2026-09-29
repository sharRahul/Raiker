# mypy: disable-error-code="misc"
"""MCP servers, hooks, plugins and channels (GCR-43).

One part of :class:`raiker.control.dashboard.DashboardService`, which inherits it. Every method
is typed against the whole store (``self: DashboardService``), so a call into another
part is checked exactly as it was when every method lived in one class. mypy
reports that self-type as ``misc`` on a mixin, which is the one code this file
turns off.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from raiker.control.dtos import ControlResult
from raiker.control.views.extensions import (
    McpServerView,
    _declaration_summaries,
    _env_requirements,
    _handler_target,
)
from raiker.hooks.handlers.http import egress_granted
from raiker.runtime.executors.tier4_plugins import plugin_code_runtime
from raiker.tools.mcp_schema import unsupported_feature_notes

if TYPE_CHECKING:
    from raiker.control.dashboard import DashboardService


class ExtensionService:

    def _dispatch_session_end_hook(self: DashboardService, session_id: str, reason: str) -> None:
        """`SessionEnd` for the one thing that really ends a web conversation.

        The event was in the config schema from the start and had no call site,
        because "what ends a session" has no obvious answer on the web: a browser
        tab closing is not a decision, and a conversation left idle is not over.
        Archiving or deleting it is a decision the owner made, and it is the only
        point at which the conversation stops being somewhere work continues —
        so that is the boundary (BUG-223).

        Dispatched *before* a delete and *after* an archive, for the same reason
        in both cases: a handler should be able to read the transcript it is
        being told about. Observation only — a handler cannot refuse either.
        """
        from raiker.hooks.contracts import HookInput
        from raiker.hooks.factory import dispatcher_for_workspace

        try:
            dispatcher = dispatcher_for_workspace(self.store)
            if not dispatcher.is_active():
                return
            dispatcher.dispatch(
                HookInput(
                    event_name="SessionEnd",
                    tool_name=None,
                    tool_input={},
                    context={"session_id": session_id, "reason": reason},
                    session_id=session_id,
                ),
                session_id=session_id,
                turn_id=None,
            )
        except Exception:  # noqa: BLE001 — a hook never blocks archiving or deleting
            return

    def list_mcp_servers(self: DashboardService, principal_id: str) -> list[McpServerView]:
        """Owner-scoped, read-only list of the caller's local MCP server
        profiles. Building or connecting a server is a governed runtime action
        (through the authority/executor path), never a plain REST mutation, so
        this surface is read-only by design."""
        return [
            McpServerView(
                server_id=str(row["server_id"]),
                name=str(row["name"]),
                command=tuple(str(part) for part in row.get("command", [])),
                template=row.get("template"),
                transport=str(row.get("transport", "stdio")),
                status=str(row.get("status", "created")),
                created_at=str(row.get("created_at", "")),
                last_connected_at=row.get("last_connected_at"),
                tools=tuple(str(t) for t in row.get("tools", [])),
                tool_count=int(row.get("tool_count", 0) or 0),
                tool_declarations=_declaration_summaries(row.get("tool_schemas")),
                unsupported_features=tuple(
                    unsupported_feature_notes(row.get("server_features"))
                ),
                endpoint_url=row.get("endpoint_url"),
                auth_ref=row.get("auth_ref"),
                monitor_state=str(row.get("monitor_state") or "active"),
                paused_reason=row.get("paused_reason"),
                paused_at=row.get("paused_at"),
                protocol_version=row.get("protocol_version"),
            )
            for row in self.store.list_mcp_servers(principal_id)
        ]

    def list_mcp_offers(self: DashboardService, principal_id: str) -> list[dict[str, Any]]:
        """MCP servers installed plugins *offer*, and whether each is already added.

        An offer is inert (BUG-221). It is a description of a server, read from
        the file the plugin wrote, and nothing about it is connected, stored as a
        server profile, or reachable. Adding one is the owner's action and runs
        the same governed create path as typing it in — which is the whole reason
        a plugin may offer one at all: it goes *through* the trust gate rather
        than around it.

        ``already_added`` is resolved against the owner's own servers by name, so
        an offer the owner has taken up reads as taken up rather than as a button
        that would fail with ``mcp_name_taken``.
        """
        from raiker.plugins.contributions import contributed_mcp_servers

        taken = {str(row.get("name")) for row in self.store.list_mcp_servers(principal_id)}
        return [
            {**offer, "plugin_id": plugin_id, "already_added": offer["name"] in taken}
            for plugin_id, offer in contributed_mcp_servers(self.workspace_root)
        ]

    def create_mcp_server(
        self: DashboardService, acting_principal_id: str | None, name: str, template: str
    ) -> ControlResult:
        """Governed build of a local stdio MCP server (delegates to the
        control service so the capability gate / policy / audit path applies)."""
        return self.control.create_mcp_server(acting_principal_id, name, template)

    def create_remote_mcp_server(
        self: DashboardService, acting_principal_id: str | None, name: str, endpoint_url: str, auth_ref: str | None
    ) -> ControlResult:
        """Add an owner-scoped remote (HTTP) MCP connection (delegates)."""
        return self.control.create_remote_mcp_server(
            acting_principal_id, name, endpoint_url, auth_ref
        )

    def connect_mcp_server(self: DashboardService, acting_principal_id: str | None, server_id: str) -> ControlResult:
        """Governed test-connect of a stored MCP server (delegates)."""
        return self.control.connect_mcp_server(acting_principal_id, server_id)

    def rename_mcp_server(
        self: DashboardService, acting_principal_id: str | None, server_id: str, name: str
    ) -> ControlResult:
        """Owner-scoped, human-only rename of one MCP server profile."""
        return self.control.rename_mcp_server(acting_principal_id, server_id, name)

    def delete_mcp_server(self: DashboardService, acting_principal_id: str | None, server_id: str) -> ControlResult:
        """Owner-scoped, human-only delete of one MCP server profile."""
        return self.control.delete_mcp_server(acting_principal_id, server_id)

    def pause_mcp_server(
        self: DashboardService, acting_principal_id: str | None, server_id: str, reason: str | None = None
    ) -> ControlResult:
        """Owner-scoped, human-only one-call stop of a connection (delegates)."""
        return self.control.pause_mcp_server(acting_principal_id, server_id, reason)

    def resume_mcp_server(self: DashboardService, acting_principal_id: str | None, server_id: str) -> ControlResult:
        """Owner-scoped, human-only resume of a paused/killed connection."""
        return self.control.resume_mcp_server(acting_principal_id, server_id)

    def kill_mcp_server(
        self: DashboardService, acting_principal_id: str | None, server_id: str, reason: str | None = None
    ) -> ControlResult:
        """Owner-scoped, human-only instant kill switch (delegates)."""
        return self.control.kill_mcp_server(acting_principal_id, server_id, reason)

    #: Event types the dispatcher writes, newest-first, for the hooks surface.
    _HOOK_EVENT_TYPES = (
        "hook_matched",
        "hook_executed",
        "hook_decision",
        "hook_timeout",
        "hook_failed",
    )

    def list_hooks(self: DashboardService, principal_id: str | None = None) -> dict[str, Any]:
        """What hooks are configured, whether they can fire, and what they did.

        Hooks were the one extension surface with a real, enforcing backend and no
        way to see it: they were configured by editing JSON on disk and observed
        only by reading the audit log by hand. Three things have to be true of
        this view for it to be worth more than that file:

        1. **A file Raiker could not read is visible.** A malformed hooks config
           contributes no rules by design; saying nothing about it would leave the
           owner believing a guard is in place that is not.
        2. **A rule that can never fire says so.** `HOOK_EVENTS` is what the schema
           accepts; `DISPATCHED_HOOK_EVENTS` is what this build emits, and a rule
           on the difference is configured but dead.
        3. **A rule that cannot change an outcome says so.** Only `PreToolUse` and
           `PreCompact` decisions are honoured, and only from a handler holding
           decision authority. Everything else observes.

        Read-only. Nothing here edits a hook: the config files are the owner's own
        text, and a surface that rewrote them would need its own authority story.
        """
        from raiker.hooks.contracts import (
            DECIDING_HOOK_EVENTS,
            DISPATCHED_HOOK_EVENTS,
            HOOK_EVENT_SUMMARIES,
            HOOK_EVENTS,
            HOOK_SCOPES,
            HookHandler,
        )
        from raiker.hooks.handlers.builtin import BUILTIN_HANDLERS
        from raiker.hooks.owner_switch import hooks_disabled
        from raiker.hooks.registry import HooksRegistry

        registry = HooksRegistry.load(self.workspace_root)
        rules: list[dict[str, Any]] = []
        for index, rule in enumerate(
            sorted(registry.rules, key=lambda r: (HOOK_SCOPES.index(r.scope), r.event, r.matcher))
        ):
            source = rule.source
            dispatched = rule.event in DISPATCHED_HOOK_EVENTS
            deciding = rule.event in DECIDING_HOOK_EVENTS

            # A builtin naming a handler this build does not have raises at
            # dispatch time and is recorded as `hook_failed`. The config parses,
            # the rule matches, and nothing happens — so it is the same class of
            # dead rule as an event that is never emitted, and is reported the
            # same way rather than being left to look enforcing.
            # BUG-226 — the same is true of an `http` handler whose destination
            # the owner's egress grant does not cover: the rule parses, matches,
            # and refuses at dispatch. Read live rather than at parse time,
            # because the grant is revocable *without* editing any hooks file —
            # that is the whole point of it being one variable rather than a
            # field per rule.
            def _available(handler: HookHandler) -> bool:
                if handler.type == "builtin":
                    return (handler.builtin or "") in BUILTIN_HANDLERS
                if handler.type == "http":
                    return egress_granted(handler.url)
                return True

            authoritative = any(
                (handler.decision_authority or handler.type == "builtin") and _available(handler)
                for handler in rule.handlers
            )
            rules.append(
                {
                    # Stable within one read, which is all a list key needs; hook
                    # rules have no identity of their own in the config format.
                    "rule_id": f"{rule.scope}:{rule.event}:{index}",
                    "event": rule.event,
                    "event_summary": HOOK_EVENT_SUMMARIES.get(rule.event, ""),
                    "matcher": rule.matcher,
                    "if_guard": rule.if_guard,
                    "scope": rule.scope,
                    "source": source,
                    "dispatched": dispatched,
                    # A rule can only change an outcome when the event is one the
                    # runtime asks about *and* a handler on it holds authority.
                    "can_decide": dispatched and deciding and authoritative,
                    "handlers": [
                        {
                            "id": handler.id,
                            "type": handler.type,
                            "target": _handler_target(handler),
                            "timeout_ms": handler.timeout_ms,
                            # A builtin is Raiker's own code and always carries
                            # authority; a command carries it only when the owner
                            # said so in the config.
                            "decision_authority": (
                                handler.decision_authority or handler.type == "builtin"
                            )
                            and _available(handler),
                            # False for a builtin this build does not ship, and
                            # for an `http` destination the egress grant does not
                            # cover. A command's program is resolved at dispatch
                            # time inside the workspace, so it is not checked here.
                            "available": _available(handler),
                            # BUG-226 — why an unavailable handler is unavailable,
                            # so the page can say "add this host to the grant"
                            # rather than only "this will not run".
                            "unavailable_reason": (
                                ""
                                if _available(handler)
                                else (
                                    "egress_not_granted"
                                    if handler.type == "http"
                                    else "builtin_not_in_this_build"
                                )
                            ),
                        }
                        for handler in rule.handlers
                    ],
                }
            )

        activity: list[dict[str, Any]] = []
        counts: dict[str, int] = {}
        for event_type in self._HOOK_EVENT_TYPES:
            rows = self.store.list_event_index(event_type=event_type, limit=50)
            counts[event_type] = len(rows)
            for row in rows:
                activity.append(
                    {
                        "event_id": str(row["event_id"]),
                        "event_type": event_type,
                        "session_id": str(row.get("session_id", "")),
                        "timestamp": str(row.get("timestamp", "")),
                        "summary": row.get("summary"),
                    }
                )
        activity.sort(key=lambda entry: entry["timestamp"], reverse=True)

        # BUG-222 — off is a state to display, not a reason to hide what would
        # otherwise run: the rules stay listed and the page says they are off.
        disabled = (
            hooks_disabled(self.workspace_root, principal_id) if principal_id is not None else False
        )
        return {
            "active": not disabled and not registry.is_empty(),
            "disabled": disabled,
            "rule_count": len(rules),
            "rules": rules,
            "sources": [entry.to_dict() for entry in registry.sources],
            "failed_sources": [entry.to_dict() for entry in registry.failed_sources()],
            "events": [
                {
                    "event": event,
                    "summary": HOOK_EVENT_SUMMARIES.get(event, ""),
                    "dispatched": event in DISPATCHED_HOOK_EVENTS,
                    "can_decide": event in DECIDING_HOOK_EVENTS,
                }
                for event in sorted(HOOK_EVENTS)
            ],
            "builtins": sorted(BUILTIN_HANDLERS),
            "activity": activity[:40],
            "activity_counts": counts,
        }

    def list_plugins(self: DashboardService) -> dict[str, Any]:
        """Installed plugin records, what each one provides, and the signing posture.

        A plugin's signature is reported at the level it actually earned —
        ``verified``, ``present_only`` or ``unsigned`` — rather than as a boolean
        that reads the same whether an author was checked or not (BUG-79).

        Each record also carries what the plugin *provides*, read from the
        contribution files on disk rather than from the manifest that described
        them (BUG-221). The files are what the runtime loads, so this cannot
        report a contribution the runtime does not have — or miss one it does,
        which is the failure that would matter.
        """
        from raiker.plugins.contributions import installed_contributions
        from raiker.plugins.verify import (
            LEVEL_PRESENT_ONLY,
            LEVEL_UNSIGNED,
            LEVEL_VERIFIED,
            signature_verification,
            signing_posture,
        )

        posture = signing_posture()
        contributions = installed_contributions(self.workspace_root)
        plugins: list[dict[str, Any]] = []
        for row in self.store.list_plugin_install_records():
            signature = str(row.get("signature") or "")
            manifest = {
                "id": row.get("plugin_id"),
                "version": row.get("version"),
                "supply_chain": {
                    "checksum": row.get("checksum"),
                    "signature": signature or None,
                },
            }
            verification = signature_verification(manifest)
            # The stored record cannot be re-signed after the fact, so an install
            # made while a key was configured is reported at the level it earned
            # then; without a key today the honest answer is the weaker one.
            level = (
                LEVEL_VERIFIED
                if verification.level == LEVEL_VERIFIED
                else (LEVEL_PRESENT_ONLY if signature else LEVEL_UNSIGNED)
            )
            plugins.append(
                {
                    "record_id": row.get("record_id"),
                    "plugin_id": row.get("plugin_id"),
                    "version": row.get("version"),
                    "trust_level": row.get("trust_level"),
                    "status": row.get("status"),
                    "source_url": row.get("source_url"),
                    "installed_at": row.get("installed_at"),
                    "installed_by": row.get("installed_by"),
                    "checksum_present": bool(row.get("checksum")),
                    # BUG-308 — where this plugin's own code would run here.
                    "code_runtime": plugin_code_runtime(str(row.get("plugin_id") or "")),
                    "signature": {**verification.to_dict(), "level": level},
                    # A revoked plugin's files are deleted with the revocation, so
                    # an empty contribution here is the same answer the runtime
                    # would give: it provides nothing.
                    "contributions": contributions.get(
                        str(row.get("plugin_id") or ""),
                        {
                            "hooks": 0,
                            "events": [],
                            "skills": 0,
                            "skill_names": [],
                            "mcp_servers": 0,
                            "mcp_server_names": [],
                            "error": None,
                        },
                    ),
                }
            )
        return {
            "plugins": plugins,
            "signing": posture,
            # What a plugin is allowed to contribute on this build, so the tab can
            # say what the surface *is* rather than only what is installed.
            "contribution_kinds": [
                {
                    "kind": "hooks",
                    "available": True,
                    "summary": (
                        "Hook rules at plugin scope — below managed, user, project "
                        "and local, so they can make an action stricter and never "
                        "override a deny you set."
                    ),
                },
                {
                    "kind": "skills",
                    "available": True,
                    "summary": (
                        "Instruction text validated by the same reader an upload "
                        "goes through. It arrives switched off and credited to the "
                        "plugin, so offering a skill and running with one stay two "
                        "separate decisions."
                    ),
                },
                {
                    "kind": "mcp_servers",
                    "available": True,
                    "summary": (
                        "A plugin may offer a server; it cannot add one. Nothing "
                        "is connected or stored until you add it, and adding it "
                        "runs the same governed create path as typing it in "
                        "yourself."
                    ),
                },
                {
                    "kind": "panels",
                    "available": False,
                    "summary": "Needs a route, permission and accessibility contract that does not exist.",
                },
            ],
        }

    def list_channels(self: DashboardService, principal_id: str) -> dict[str, Any]:
        """Every connector profile, what it needs, and what is actually true today.

        The Channels tab said channels did not exist. The outbound executor, the
        inbound receiver, the capability gate and the egress boundary were all
        built; what was missing was any way for the owner to pair a connector, so
        `list_channel_pairings` stayed empty and both executors refused. The
        transport was unreachable because there was no surface, not because there
        was no transport — and the tab could not tell the difference.

        This reports each of the separate facts rather than collapsing them into
        one "ready" flag, because they have different remedies:

        * **Linked** — is there a pairing at all.
        * **Enabled** — is that pairing switched on. Linked is not enabled.
        * **Senders** — how many are allowlisted, for a profile that requires it.
          Enabled is not trusted.
        * **The capability gate** — `external_channel_runtime`, which the owner
          sets in Permissions and which no channel control here can widen.
        * **Egress** — whether `RAIKER_CHANNEL_EGRESS_ALLOWLIST` names any host.
          It defaults to empty and is fail-closed, so a channel that is linked,
          enabled and trusted still delivers nothing until the owner allowlists
          the destination.
        * **Inbound** — whether `RAIKER_CHANNEL_INBOUND_SECRET` is set. Without
          it the receiver refuses every message, which is the right default and a
          confusing one to meet without being told.

        Never returns a secret, a host, or a sender identifier — a count and a
        boolean answer every question this page asks.
        """
        import json as _json

        from raiker.api.routes_channels import channel_inbound_limit
        from raiker.channels.registry import ConnectorRegistry
        from raiker.runtime.executors.sandbox import channel_egress_allowlist

        try:
            profiles = ConnectorRegistry.load().profiles
        except Exception:  # noqa: BLE001 - an unreadable registry is a reported state
            return {
                "profiles": [],
                "error": "connector_registry_unavailable",
                "outbound": {},
                "inbound": {},
            }
        pairings = {str(row.get("connector_id")): row for row in self.store.list_channel_pairings()}
        gate = self.control.get_capability_gate("external_channel_runtime", principal_id)
        allowlist = channel_egress_allowlist()
        rows: list[dict[str, Any]] = []
        for profile in profiles:
            pairing = pairings.get(profile.connector_id)
            senders: list[str] = []
            if pairing is not None:
                try:
                    senders = list(_json.loads(pairing.get("sender_allowlist_json") or "[]"))
                except (ValueError, TypeError):
                    senders = []
            rows.append(
                {
                    "connector_id": profile.connector_id,
                    "channel_type": profile.channel_type,
                    "display_name": profile.display_name,
                    "transport": profile.transport,
                    "auth_method": profile.auth_method,
                    "default_state": profile.default_state,
                    "requires_pairing": profile.requires_pairing,
                    "requires_sender_allowlist": profile.requires_sender_allowlist,
                    "requires_network": profile.requires_network,
                    "linked": pairing is not None,
                    "enabled": bool(pairing.get("enabled")) if pairing else False,
                    "pairing_id": pairing.get("pairing_id") if pairing else None,
                    "display_label": pairing.get("display_name") if pairing else None,
                    "sender_count": len(senders),
                    # The identifiers themselves are the owner's contact list and
                    # never leave the store; the count answers the page's question.
                    "senders": senders,
                    "routing_mode": str(pairing.get("routing_mode") or "record_only") if pairing else "record_only",
                    "target_session_id": pairing.get("target_session_id") if pairing else None,
                    "owner_sender_id": pairing.get("owner_sender_id") if pairing else None,
                    "approval_relay_enabled": bool(pairing.get("approval_relay_enabled")) if pairing else False,
                    "supports_side_questions": bool(profile.raw.get("supports_side_questions")),
                    "supports_interrupts": bool(profile.raw.get("supports_interrupts")),
                    "supports_approvals": bool(profile.raw.get("supports_approvals")),
                    # What this transport needs from the owner's environment,
                    # declared on the profile rather than known only to the
                    # guide, so the setup surface can read it instead of the
                    # owner hunting through prose. `present` is a boolean:
                    # Raiker takes variable names and never values, and that
                    # holds on the way out too.
                    "env_requirements": _env_requirements(profile.raw),
                }
            )
        return {
            "profiles": rows,
            "error": None,
            "outbound": {
                "capability": "external_channel_runtime",
                "gate_state": gate.state if gate is not None else "unknown",
                "runtime_enabled": bool(gate.runtime_enabled) if gate is not None else False,
                "egress_configured": bool(allowlist),
                "egress_host_count": len(allowlist),
                # The webhook profile declares `signed_http_callback`. Without a
                # secret the executor still delivers — the owner controls both
                # ends of a webhook they configured — but the receiver cannot
                # tell a Raiker delivery from anything else that reaches the URL,
                # so the state is reported rather than assumed.
                "signing_configured": bool(
                    os.environ.get("RAIKER_CHANNEL_OUTBOUND_SECRET", "").strip()
                ),
            },
            "inbound": {
                "secret_configured": bool(
                    os.environ.get("RAIKER_CHANNEL_INBOUND_SECRET", "").strip()
                ),
                # Allowlisting says *who* may speak; the budget says how often.
                # They are different questions, and an allowlisted sender was
                # unbounded until one had an answer.
                "rate_limit_per_minute": channel_inbound_limit(),
                # Stated rather than implied: an inbound message is untrusted
                # content from a sender who is not the owner, it is quarantined,
                # and its instructions are inert. That is the accepted contract,
                # and the receiver enforces it on every message.
                "quarantined": True,
                "instructions_inert": True,
            },
        }

    def pair_channel(
        self: DashboardService,
        acting_principal_id: str | None,
        connector_id: str,
        display_name: str,
        sender_allowlist: list[str] | None = None,
    ) -> ControlResult:
        return self.control.pair_channel(
            acting_principal_id, connector_id, display_name, sender_allowlist
        )

    def set_channel_enabled(
        self: DashboardService, acting_principal_id: str | None, pairing_id: str, enabled: bool
    ) -> ControlResult:
        return self.control.set_channel_enabled(acting_principal_id, pairing_id, enabled)

    def set_channel_senders(
        self: DashboardService, acting_principal_id: str | None, pairing_id: str, senders: list[str]
    ) -> ControlResult:
        return self.control.set_channel_senders(acting_principal_id, pairing_id, senders)

    def set_channel_routing(
        self: DashboardService, acting_principal_id: str | None, pairing_id: str, **settings: Any
    ) -> ControlResult:
        return self.control.set_channel_routing(acting_principal_id, pairing_id, **settings)

    def unpair_channel(self: DashboardService, acting_principal_id: str | None, pairing_id: str) -> ControlResult:
        return self.control.unpair_channel(acting_principal_id, pairing_id)

    def deliver_channel_test(
        self: DashboardService, acting_principal_id: str | None, connector_id: str, url: str, text: str
    ) -> ControlResult:
        return self.control.deliver_channel_test(acting_principal_id, connector_id, url, text)
