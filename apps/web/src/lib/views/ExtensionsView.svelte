<script lang="ts">
  /**
   * Extensions hub — one destination for connectors, MCP servers, and the
   * surfaces that are not available yet.
   *
   * The hub's own tab is Overview: it reads the server's lifecycle aggregate and
   * shows the four facts per extension, so nothing appears available from
   * metadata alone. The Connectors and MCP tabs mount the existing governed
   * views unchanged — this consolidates navigation, it does not re-implement or
   * loosen any mutation path.
   */
  import { onMount } from "svelte";
  import ConnectionsView from "./ConnectionsView.svelte";
  import McpView from "./McpView.svelte";
  import SkillsView from "./SkillsView.svelte";
  import LifecycleTrack from "../components/LifecycleTrack.svelte";
  import PageState from "../components/PageState.svelte";
  import SidePanel from "../components/SidePanel.svelte";
  import StatTile from "../components/StatTile.svelte";
  import TabStrip from "../components/TabStrip.svelte";
  import Icon from "../components/Icon.svelte";
  import GuideLink from "../components/GuideLink.svelte";
  import { api, ApiError } from "../api";
  import type {
    ApprovalView,
    ChannelProfile,
    ChannelsView,
    ExtensionView,
    ExtensionsOverview,
    HooksView,
    PluginContributions,
    PluginsView,
  } from "../apiTypes";
  import { relativeTime } from "../format";
  import { HUB_TABS } from "../nav";

  let { tab = "connectors" }: { tab?: string } = $props();

  let overview = $state<ExtensionsOverview | null>(null);
  // BUG-79 — a manifest signature used to be a presence marker with nothing on
  // screen to say so. This reads the installed records and this workspace's own
  // signing posture, so `verified` and `present only` never look identical.
  let plugins = $state<PluginsView | null>(null);
  let pluginsError = $state<string | null>(null);
  // Hooks had a real enforcing backend and no surface at all: they were written
  // into JSON on disk and observed only by reading the audit log by hand. This
  // reads what the runtime actually loaded, which is the only version of the
  // answer worth showing — including a config file it could not parse.
  let hooks = $state<HooksView | null>(null);
  let hooksError = $state<string | null>(null);

  let hooksBusy = $state(false);

  async function loadHooks() {
    try {
      hooks = await api.hooks();
      hooksError = null;
    } catch (error) {
      hooks = null;
      hooksError = error instanceof ApiError ? error.message : "Hook configuration is unavailable.";
    }
  }

  /**
   * BUG-222 — the owner's off switch.
   *
   * `config/hooks.json` travels with a repository, so cloning a project can
   * bring rules that run commands on this machine. Editing someone else's
   * checked-in file is not a refusal, so this is an owner setting rather than a
   * fourth config file — and it is the one control on this page that writes
   * anything, which is why it goes through the ordinary settings route.
   */
  async function setHooksDisabled(disabled: boolean) {
    if (hooksBusy) return;
    hooksBusy = true;
    try {
      const current = await api.settings();
      const next = { ...current.settings, hooks: { disabled } };
      await api.putSettings(next);
      await loadHooks();
      hooksError = null;
    } catch (error) {
      hooksError =
        error instanceof ApiError ? error.message : "That setting could not be saved.";
    } finally {
      hooksBusy = false;
    }
  }

  // BUG-225 — the outbound executor, the inbound receiver, the capability gate
  // and the egress boundary were all built, and there was no way for the owner
  // to pair a connector. So `list_channel_pairings` stayed empty, both executors
  // refused, and this tab reported that channels did not exist. The transport was
  // unreachable because there was no surface — which is a different problem, with
  // a different fix.
  let channels = $state<ChannelsView | null>(null);
  let channelsError = $state<string | null>(null);
  let channelBusy = $state<string | null>(null);
  let channelNotice = $state<string | null>(null);
  let pairingFor = $state<string | null>(null);
  let pairSenders = $state("");
  let testFor = $state<string | null>(null);
  let testUrl = $state("");
  let routingFor = $state<string | null>(null);
  let routeMode = $state<"record_only" | "new_turn" | "side_question" | "interrupt">("record_only");
  let routeTarget = $state("");
  let routeOwner = $state("");
  let routeRelay = $state(false);

  const CHANNEL_REASONS: Record<string, string> = {
    disabled_by_capability_gate:
      "The external channel capability is turned off. Turn it on in Permissions to deliver anything.",
    channel_already_paired: "That connector is already paired.",
    sender_allowlist_required:
      "This channel accepts inbound messages, so it needs at least one allowlisted sender before it can be paired.",
    channel_not_paired_or_disabled: "Pair the connector and switch it on first.",
    unknown_channel_pairing: "That pairing is no longer there.",
    not_authorized_human: "Only you can change a channel pairing.",
    channel_owner_not_allowlisted: "Choose an owner sender from this channel's allowlist.",
    channel_owner_sender_required: "This route needs an explicit owner sender.",
    channel_target_session_required: "Side questions and interrupts need a target conversation.",
    channel_target_session_unknown: "That conversation is unavailable to this account.",
  };

  function channelReason(error: unknown): string {
    if (!(error instanceof ApiError)) return "That request failed.";
    const code = error.reasonCode ?? "";
    if (CHANNEL_REASONS[code]) return CHANNEL_REASONS[code];
    if (code.startsWith("egress_denied"))
      return "That host is not on the channel egress allowlist, so delivery was refused before it left this machine.";
    if (code.startsWith("http_error"))
      return `The destination answered with an error (${code.split(":")[1] ?? "unknown"}).`;
    if (code.startsWith("fetch_failed"))
      return "The destination could not be reached.";
    if (code.startsWith("unknown_connector")) return "That connector is not in the registry.";
    return code || "That request failed.";
  }

  async function loadChannels() {
    try {
      channels = await api.channels();
      channelsError = null;
    } catch (error) {
      channels = null;
      channelsError =
        error instanceof ApiError ? error.message : "Channel profiles are unavailable.";
    }
  }

  async function runChannelAction(key: string, action: () => Promise<unknown>, done: string) {
    if (channelBusy) return;
    channelBusy = key;
    channelsError = null;
    channelNotice = null;
    try {
      await action();
      channelNotice = done;
      await loadChannels();
    } catch (error) {
      channelsError = channelReason(error);
    } finally {
      channelBusy = null;
    }
  }

  function pair(profile: ChannelProfile) {
    const senders = pairSenders
      .split(/[\n,]/)
      .map((entry) => entry.trim())
      .filter(Boolean);
    void runChannelAction(
      `pair:${profile.connector_id}`,
      () => api.pairChannel(profile.connector_id, profile.display_name, senders),
      // Said at the moment it happens, because "paired" is the step most likely
      // to be read as "working".
      `Paired ${profile.display_name}. It is switched off until you turn it on.`,
    ).then(() => {
      pairingFor = null;
      pairSenders = "";
    });
  }

  function sendTest(profile: ChannelProfile) {
    const url = testUrl.trim();
    if (!url) return;
    void runChannelAction(
      `test:${profile.connector_id}`,
      () => api.deliverChannelTest(profile.connector_id, url, "Raiker test delivery."),
      "Delivered. The destination accepted it.",
    );
  }

  function openRouting(profile: ChannelProfile) {
    routingFor = routingFor === profile.connector_id ? null : profile.connector_id;
    routeMode = profile.routing_mode ?? "record_only";
    routeTarget = profile.target_session_id ?? "";
    routeOwner = profile.owner_sender_id ?? "";
    routeRelay = profile.approval_relay_enabled ?? false;
  }

  function routeLabel(mode: ChannelProfile["routing_mode"]): string {
    if (mode === "new_turn") return "New turn";
    if (mode === "side_question") return "Side question";
    if (mode === "interrupt") return "Interrupt";
    return "Record only";
  }

  function saveRouting(profile: ChannelProfile) {
    void runChannelAction(
      `routing:${profile.connector_id}`,
      () => api.setChannelRouting(profile.pairing_id ?? "", {
        routing_mode: routeMode,
        target_session_id: routeTarget.trim() || null,
        owner_sender_id: routeOwner.trim() || null,
        approval_relay_enabled: routeRelay,
      }),
      routeMode === "record_only"
        ? `${profile.display_name} records inbound messages without starting work.`
        : `${profile.display_name} now routes ${routeMode.replace("_", " ")}.`,
    ).then(() => (routingFor = null));
  }

  async function loadPlugins() {
    try {
      plugins = await api.plugins();
      pluginsError = null;
    } catch (error) {
      plugins = null;
      pluginsError =
        error instanceof ApiError ? error.message : "Plugin records are unavailable.";
    }
  }
  let loadError = $state<string | null>(null);
  let selected = $state<ExtensionView | null>(null);
  let filter = $state<"all" | "usable" | "blocked">("all");

  // Reverse approval link: a connector call waiting on a decision should say so
  // here, not only in the queue. Matched on capability, which is what the
  // approval is actually raised against.
  let approvals = $state<ApprovalView[]>([]);
  const pendingForSelected = $derived(
    selected?.capability == null
      ? []
      : approvals.filter((approval) => approval.capability === selected?.capability),
  );

  // `.raiker/plugins/<id>/hooks.json` → `<id>`. Two plugins load at the same
  // scope, so "plugin" alone no longer identifies which one wrote a rule.
  function pluginName(source: string | null): string {
    const parts = (source ?? "").split("/");
    return parts.length >= 3 ? parts[2] : "plugin";
  }

  // Read through a helper rather than field-by-field in the markup: this page
  // renders a payload the server owns, and a template that dereferences a field
  // the server has not sent yet takes the whole tab down rather than one line.
  const contributedEvents = (c: PluginContributions | undefined) => c?.events ?? [];

  function provides(contributions: PluginContributions | undefined): string {
    if (!contributions || contributions.error) {
      return "What it provides could not be read, so nothing is loaded from it.";
    }
    const parts: string[] = [];
    if (contributions.hooks > 0) {
      const rules = `${contributions.hooks} hook ${contributions.hooks === 1 ? "rule" : "rules"}`;
      parts.push(`${rules} on ${contributions.events.join(", ")}`);
    }
    const skills = contributions.skills ?? 0;
    if (skills > 0) {
      const names = (contributions.skill_names ?? []).join(", ");
      parts.push(`${skills} ${skills === 1 ? "skill" : "skills"}${names ? ` (${names})` : ""}`);
    }
    const servers = contributions.mcp_servers ?? 0;
    if (servers > 0) {
      const names = (contributions.mcp_server_names ?? []).join(", ");
      parts.push(
        `${servers} offered MCP ${servers === 1 ? "server" : "servers"}${names ? ` (${names})` : ""}`,
      );
    }
    if (parts.length === 0) {
      return "Provides nothing — no hook rules, no skills and no MCP servers are loaded from it.";
    }
    return `Provides ${parts.join(" and ")}.`;
  }

  // A contributed skill installs switched off, so the row has to say where to go
  // and that nothing is running yet — otherwise "provides 2 skills" reads as two
  // skills already in every turn.
  const contributedSkills = (c: PluginContributions | undefined) => c?.skills ?? 0;
  const offeredServers = (c: PluginContributions | undefined) => c?.mcp_servers ?? 0;

  const KIND_LABELS: Record<string, string> = {
    hooks: "Hooks",
    skills: "Skills",
    mcp_servers: "MCP servers",
    panels: "Panels",
  };
  const kindLabel = (kind: string) => KIND_LABELS[kind] ?? kind;

  const tabs = HUB_TABS.extensions.map((id) => ({
    id,
    label: {
      connectors: "Connectors",
      mcp: "MCP servers",
      skills: "Skills",
      hooks: "Hooks",
      plugins: "Plugins",
      channels: "Channels",
    }[id] as string,
  }));

  const visible = $derived(
    (overview?.extensions ?? []).filter((extension) =>
      filter === "all"
        ? true
        : filter === "usable"
          ? extension.usable
          : !extension.usable,
    ),
  );

  function selectTab(next: string) {
    window.location.hash = `#/extensions?tab=${encodeURIComponent(next)}`;
  }

  function blockedCopy(extension: ExtensionView): string {
    switch (extension.blocked_reason) {
      case "not_installed":
        return "Not installed yet. Install it on the Connectors tab.";
      case "reauthentication_required":
        return "The stored credential expired. Reconnect the account to continue.";
      case "account_not_connected":
        return "Installed, but no account credential is stored for it.";
      case "not_enabled_for_session":
        return "Connected, but not enabled for this session.";
      case "capability_gate_closed":
        return "Its capability gate is turned off, so the runtime refuses every call. Turn it on in Permissions.";
      // BUG-11 — enabled is not the same as enabled at runtime level, and the
      // two need different actions from the owner.
      case "capability_below_runtime_level":
        return "Its capability is enabled, but below runtime level. Set it to “enabled runtime” in Permissions.";
      case "capability_decision_mode_deny":
        return "Its decision mode is set to Deny, so every proposed call is refused. Change the mode in Permissions.";
      case "egress_host_not_allowlisted":
        return "Its host is not on the connector egress allowlist.";
      case "connection_killed":
        return "The connection was killed and will not restart on its own.";
      case "circuit_breaker_paused":
        return "The monitor paused this connection after an anomaly.";
      case "not_connected":
        return "No successful handshake yet, so no tools are available.";
      default:
        return "Ready to use in a governed turn.";
    }
  }

  function steps(extension: ExtensionView) {
    return [
      {
        label: "Installed",
        met: extension.installed,
        note: extension.installed ? "Present in this workspace" : "Not added yet",
      },
      {
        label: "Account connected",
        met: extension.connected,
        note: extension.connected
          ? "A credential is stored in the vault"
          : "No stored credential — the value is never shown here either way",
      },
      {
        label: "Enabled for the session",
        met: extension.enabled,
        note: extension.enabled ? "Turned on for this session" : "Turned off",
      },
      {
        label: "Usable now",
        met: extension.usable,
        note: extension.usable
          ? "The runtime will accept a governed call"
          : "The runtime still refuses calls",
      },
    ];
  }

  async function load() {
    loadError = null;
    try {
      overview = await api.extensions();
      if (selected !== null) {
        selected =
          overview.extensions.find((e) => e.extension_id === selected?.extension_id) ?? null;
      }
    } catch (error) {
      overview = null;
      loadError =
        error instanceof ApiError ? `Unavailable (${error.status})` : "Unavailable";
    }
    try { approvals = await api.approvals(); } catch { approvals = []; }
  }

  onMount(() => {
    void load();
    void loadPlugins();
    void loadHooks();
    void loadChannels();
  });
</script>

<TabStrip {tabs} selected={tab} onselect={selectTab} label="Extension categories" />

{#if tab === "connectors"}
  <div id="panel-connectors" role="tabpanel" aria-labelledby="tab-connectors">
    <section class="overview" aria-labelledby="lifecycle-h">
      <div class="overview-head">
        <div>
          <h2 id="lifecycle-h">Readiness</h2>
  <GuideLink route="extensions" />
        </div>
        <button type="button" class="btn btn-ghost btn-sm" onclick={load}>
          <Icon name="refresh" size="sm" /> Refresh
        </button>
      </div>

      {#if loadError}
        <PageState state="error" title="Couldn't load extension readiness" detail={loadError} />
      {:else if overview === null}
        <PageState state="loading" title="Reading extension readiness…" />
      {:else}
        <div class="tiles">
          <StatTile
            label="Usable now"
            value={overview.counts.usable}
            detail="Every condition confirmed by the server."
            tone={overview.counts.usable > 0 ? "ok" : "neutral"}
          />
          <StatTile
            label="Installed"
            value={overview.counts.installed}
            detail="Present in the workspace, whatever their credential state."
          />
          <StatTile
            label="Connected"
            value={overview.counts.connected}
            detail="An account credential is stored — its value is never shown."
          />
          <StatTile
            label="Credential vault"
            value={overview.vault_configured ? "Configured" : "Not configured"}
            detail={overview.vault_configured
              ? "Credentials can be encrypted at rest."
              : "Linking an account fails closed until the vault key is set."}
            tone={overview.vault_configured ? "ok" : "warn"}
          />
        </div>

        <div class="chip-row filters" role="group" aria-label="Filter extensions">
          {#each [["all", "All"], ["usable", "Usable"], ["blocked", "Blocked"]] as [id, label] (id)}
            <button
              type="button"
              class="chip"
              onclick={() => (filter = id as typeof filter)}
              aria-pressed={filter === id}
            >{label}</button>
          {/each}
        </div>

        <div class="split">
          <ul class="extension-list">
            {#each visible as extension (extension.extension_id)}
              <li>
                <button
                  type="button"
                  class="extension-row"
                  class:selected={selected?.extension_id === extension.extension_id}
                  onclick={() => (selected = extension)}
                  aria-label={`Open ${extension.display_name} details`}
                >
                  <span class="row-main">
                    <span class="name">{extension.display_name}</span>
                    <span class="category">{extension.category}</span>
                  </span>
                  <!--
                    BUG-278 — four pills reading "installed connected enabled
                    usable" said the opposite of the counters above them.

                    They are the same four conditions the side panel's
                    `LifecycleTrack` renders, and met/unmet was carried by colour
                    alone: on a workspace where nothing is installed, twenty-six
                    rows of grey pills read as twenty-six connectors that *are*
                    installed and connected, directly under a card saying
                    "INSTALLED 0 · CONNECTED 0". In greyscale, or to a
                    colour-blind owner, there was no other channel at all.

                    So each pill carries the marker the side panel already uses —
                    `✓` met, `○` not — and says which for a screen reader. Not a
                    new vocabulary: the same one, two components apart, which is
                    what it should have been.
                  -->
                  <span class="facts">
                    {#each [
                      ["installed", extension.installed, false],
                      ["connected", extension.connected, false],
                      ["enabled", extension.enabled, false],
                      ["usable", extension.usable, true],
                    ] as [label, met, strong] (label)}
                      <span class="fact" class:strong class:on={met}>
                        <span class="mark" aria-hidden="true">{met ? "✓" : "○"}</span>{label}
                        <span class="sr-only">: {met ? "yes" : "no"}</span>
                      </span>
                    {/each}
                  </span>
                </button>
              </li>
            {:else}
              <li class="empty-row">No extension matches this filter.</li>
            {/each}
          </ul>

          <SidePanel
            open={selected !== null}
            title={selected?.display_name ?? ""}
            subtitle={selected?.category ?? null}
            onclose={() => (selected = null)}
          >
            {#if selected}
              <p>{selected.detail}</p>
              <LifecycleTrack steps={steps(selected)} blockedReason={selected.blocked_reason} />
              <p class="reason" class:blocked={selected.blocked_reason !== null}>
                {blockedCopy(selected)}
              </p>
              {#if pendingForSelected.length > 0}
                <p class="pending-approval" role="status">
                  {pendingForSelected.length === 1 ? "One call is" : `${pendingForSelected.length} calls are`}
                  waiting on your decision before this connector can act.
                  <a href="#/approvals">Review the decision queue</a>
                </p>
              {/if}
              <dl class="property-list">
                {#if selected.capability}
                  <dt>Capability</dt><dd class="mono">{selected.capability}</dd>
                {/if}
                {#if selected.gate_state}
                  <dt>Gate state</dt><dd>{selected.gate_state}</dd>
                {/if}
                {#if selected.decision_mode}
                  <dt>Decision mode</dt><dd>{selected.decision_mode}</dd>
                {/if}
                {#if selected.egress_host}
                  <dt>Egress host</dt>
                  <dd>
                    <span class="mono">{selected.egress_host}</span>
                    {#if selected.egress_allowed !== null}
                      · {selected.egress_allowed ? "on the allowlist" : "not allowlisted"}
                    {/if}
                  </dd>
                {/if}
                {#if selected.transport}
                  <dt>Transport</dt><dd>{selected.transport}</dd>
                {/if}
                {#if selected.monitor_state}
                  <dt>Monitor</dt><dd>{selected.monitor_state}</dd>
                {/if}
                {#if selected.kind === "mcp_server"}
                  <dt>Tools discovered</dt><dd>{selected.tool_count}</dd>
                {/if}
                {#if selected.last_activity_at}
                  <dt>Last activity</dt>
                  <dd title={selected.last_activity_at}>{relativeTime(selected.last_activity_at)}</dd>
                {/if}
              </dl>
              <p class="note">
                This panel reports state; it never grants it.
                <GuideLink section="extensions-and-mcp" label="How a server is governed" />
              </p>
            {/if}
          </SidePanel>
        </div>
      {/if}
    </section>

    <hr />
    <ConnectionsView />
  </div>
{:else if tab === "mcp"}
  <div id="panel-mcp" role="tabpanel" aria-labelledby="tab-mcp">
    <McpView />
  </div>
{:else if tab === "skills"}
  <div id="panel-skills" role="tabpanel" aria-labelledby="tab-skills">
    <SkillsView />
  </div>
{:else if tab === "hooks"}
  <div id="panel-hooks" role="tabpanel" aria-labelledby="tab-hooks">
    <section class="card">
      <!-- The tab strip already says "Hooks", and what a hook *is* was five
           lines read once and in the way on every later visit. The one claim
           that must stay on the page is the one an owner would otherwise have to
           take on trust: a hook can only ever make an action stricter. -->
      <h2 class="sr-only">Hooks</h2>
      <p class="note">
        A hook can only make an action <strong>stricter</strong> — never allow one the runtime
        refused, skip an approval, or reach past the tool broker.
        <GuideLink section="extensions-and-mcp" label="How hooks work" />
      </p>
      {#if hooks === null}
        <p class="note">{hooksError ?? "Reading hook configuration…"}</p>
      {:else}
        <label class="hooks-switch">
          <input
            type="checkbox"
            checked={hooks.disabled}
            disabled={hooksBusy}
            onchange={(event) => void setHooksDisabled(event.currentTarget.checked)}
          />
          <span>Turn every hook off</span>
        </label>
        <p class="note">Rules stay listed while this is on, so you can see what would run.</p>

        <p class="posture" class:posture-warn={hooks.disabled || hooks.failed_sources.length > 0}>
          {#if hooks.disabled}
            Hooks are turned off. {hooks.rule_count}
            {hooks.rule_count === 1 ? "configured rule is" : "configured rules are"} loaded and
            will not run.
          {:else if hooks.failed_sources.length > 0}
            {hooks.failed_sources.length} configuration
            {hooks.failed_sources.length === 1 ? "file" : "files"} could not be read, so
            {hooks.failed_sources.length === 1 ? "its rules are" : "their rules are"} not loaded.
          {:else if hooks.active}
            {hooks.rule_count} {hooks.rule_count === 1 ? "rule is" : "rules are"} loaded and active.
          {:else}
            No hooks are configured, so the runtime behaves exactly as it does without them.
          {/if}
        </p>

        {#if hooks.failed_sources.length > 0}
          <ul class="hook-errors">
            {#each hooks.failed_sources as source (source.path)}
              <li>
                <code>{source.path}</code>
                <span class="note">{source.error}</span>
              </li>
            {/each}
          </ul>
          <p class="note">
            A file Raiker cannot read contributes no rules rather than being guessed at. Everything
            else keeps working — fix the file and reload this page.
          </p>
        {/if}
      {/if}
    </section>

    {#if hooks !== null && hooks.rules.length > 0}
      <section class="card">
        <h2>Configured rules</h2>
        <ul class="hook-list">
          {#each hooks.rules as rule (rule.rule_id)}
            <li class:hook-dead={!rule.dispatched}>
              <div class="hook-head">
                <strong>{rule.event}</strong>
                <code class="matcher">{rule.matcher}</code>
                {#if rule.if_guard}<code class="matcher">if {rule.if_guard}</code>{/if}
                <span class="hook-scope" class:hook-scope-plugin={rule.scope === "plugin"}>
                  {rule.scope === "plugin" ? pluginName(rule.source) : rule.scope}
                </span>
                {#if rule.can_decide}
                  <span class="hook-tag hook-tag-decides">Can deny or ask</span>
                {:else if rule.dispatched}
                  <span class="hook-tag">Observes only</span>
                {/if}
              </div>
              <span class="note">{rule.event_summary}</span>
              {#if !rule.dispatched}
                <span class="note hook-warn">
                  This build never emits {rule.event}, so this rule is configured but never fires.
                </span>
              {/if}
              <ul class="handler-list">
                {#each rule.handlers as handler (handler.id)}
                  <li>
                    <span class="handler-type">{handler.type}</span>
                    <code>{handler.target}</code>
                    <span class="note">{handler.timeout_ms} ms</span>
                    {#if !handler.available}
                      <span class="note hook-warn">
                        {handler.unavailable_reason === "egress_not_granted"
                          ? "this host is not in RAIKER_HOOK_EGRESS_ALLOWLIST — it will refuse every time it matches"
                          : "no builtin by this name in this build — it will fail every time it matches"}
                      </span>
                    {:else if !handler.decision_authority}
                      <span class="note">
                        {handler.type === "prompt" ? "tool-free model advisory" : "advisory"}
                      </span>
                    {/if}
                  </li>
                {/each}
              </ul>
              {#if rule.source}<span class="note">from <code>{rule.source}</code></span>{/if}
            </li>
          {/each}
        </ul>
      </section>
    {/if}

    {#if hooks !== null}
      <!-- Twenty rows of reference on a page an owner opens to check one rule.
           Collapsed, with the counts in the summary, so the answer to "how many
           can decide" is readable without the list and the list is one press
           away when it is the question. -->
      <section class="card">
        <details class="events">
          <summary>
            <h2 class="events-h">What fires, and what it can change</h2>
            <span class="note">
              {hooks.events.filter((event) => event.dispatched).length} events ·
              {hooks.events.filter((event) => event.can_decide).length} can decide
            </span>
          </summary>
        <ul class="event-list">
          {#each hooks.events as event (event.event)}
            <li class:event-dead={!event.dispatched}>
              <strong>{event.event}</strong>
              <span
                class="hook-tag"
                class:hook-tag-decides={event.can_decide}
                class:hook-tag-dead={!event.dispatched}
              >
                {event.dispatched
                  ? event.can_decide
                    ? "Decides"
                    : "Observes"
                  : "Never fires"}
              </span>
              <span class="note">{event.summary}</span>
            </li>
          {/each}
        </ul>
        </details>
      </section>

      <section class="card">
        <h2>Handler types</h2>
        <!-- One clause each. The paragraph this replaced said the same four
             things in eight lines, and the detail behind each is in the guide. -->
        <ul class="event-list">
          <li><strong>command</strong> <span class="note">a bounded program in your workspace</span></li>
          <li>
            <strong>http</strong>
            <span class="note">
              posts the redacted event to a host in <code>RAIKER_HOOK_EGRESS_ALLOWLIST</code>,
              empty until you set it
            </span>
          </li>
          <li><strong>prompt</strong> <span class="note">one tool-free model call; advisory only</span></li>
          <li><strong>builtin</strong> <span class="note">Raiker's own reviewed logic</span></li>
        </ul>
        <p class="note">MCP tool and agent handlers stay refused. <GuideLink section="extensions-and-mcp" label="Why" /></p>
      </section>

      <section class="card">
        <h2>Built-in handlers</h2>
        <p class="note">Raiker's own code.</p>
        <ul class="event-list">
          {#each hooks.builtins as builtin (builtin)}
            <li><strong>{builtin}</strong></li>
          {/each}
        </ul>
      </section>

      <section class="card">
        <h2>Recent hook activity</h2>
        {#if hooks.activity.length === 0}
          <p class="note">
            No hook has matched, run, decided, timed out or failed in the recorded history.
          </p>
        {:else}
          <ul class="activity-list">
            {#each hooks.activity as entry (entry.event_id)}
              <li>
                <span class="hook-tag">{entry.event_type.replace("hook_", "")}</span>
                <span class="note">{relativeTime(entry.timestamp)}</span>
                {#if entry.summary}<span class="note">{entry.summary}</span>{/if}
              </li>
            {/each}
          </ul>
        {/if}
        <p class="note">
          Every match, run, decision, timeout and failure is in the append-only record.
          <a href="#/observe?tab=activity">Open the audit log →</a>
        </p>
      </section>
    {/if}

    <!-- Not `deferred`: hooks are not a missing feature, they are a working one
         configured somewhere else. The class is for surfaces that do not exist
         yet, and borrowing it here would have said the wrong thing (and rendered
         narrower than every card above it). -->
    <section class="card">
      <h2>Hooks are configured in a file, not here</h2>
      <!-- The paragraph this replaced spent six lines saying what four rows say.
           The rows stay on the page rather than moving to the guide because they
           are the authority order: which file wins, and that a plugin's rules
           sit below every one of yours. -->
      <ul class="event-list">
        <li><code>config/managed-hooks.json</code> <span class="note">managed — nothing below overrides it</span></li>
        <li><code>config/hooks.json</code> <span class="note">project — travels with the repository</span></li>
        <li><code>.raiker/hooks.json</code> <span class="note">local — this machine only</span></li>
        <li><code>.raiker/plugins/</code> <span class="note">plugin — lowest, so it can only make an action stricter</span></li>
      </ul>
      <p class="note">
        <GuideLink section="extensions-and-mcp" label="How hooks are configured" />
      </p>
    </section>
  </div>
{:else if tab === "plugins"}
  <div id="panel-plugins" role="tabpanel" aria-labelledby="tab-plugins">
    <section class="card" data-testid="plugin-signing-posture">
      <h2>Plugin supply chain</h2>
      {#if plugins === null}
        <p class="note">{pluginsError ?? "Reading plugin records…"}</p>
      {:else}
        <p
          class="posture"
          class:posture-warn={!plugins.signing.configured}
        >{plugins.signing.summary}</p>
        {#if plugins.signing.remediation}
          <p class="note">{plugins.signing.remediation}</p>
        {/if}
        {#if plugins.plugins.length === 0}
          <p class="note">
            Nothing is installed, and no plugin code runs in this browser.
          </p>
        {:else}
          <ul class="plugin-list">
            {#each plugins.plugins as plugin (plugin.record_id)}
              <li>
                <div class="plugin-copy">
                  <strong>{plugin.plugin_id}</strong>
                  <span class="note">
                    {plugin.version} · {plugin.trust_level} · {plugin.status}
                  </span>
                  <span class="note">{provides(plugin.contributions)}</span>
                  {#if contributedEvents(plugin.contributions).length > 0}
                    <span class="note">
                      <a href="#/extensions?tab=hooks">See the rules on the Hooks tab →</a>
                    </span>
                  {/if}
                  {#if contributedSkills(plugin.contributions) > 0}
                    <span class="note">
                      Its skills install switched off.
                      <a href="#/extensions?tab=skills">Activate them on the Skills tab →</a>
                    </span>
                  {/if}
                  {#if offeredServers(plugin.contributions) > 0}
                    <span class="note">
                      An offered server is inert until you add it.
                      <a href="#/extensions?tab=mcp">Review it on the MCP servers tab →</a>
                    </span>
                  {/if}
                  <span class="note">{plugin.signature.explanation}</span>
                  {#if plugin.signature.remediation}
                    <span class="note">{plugin.signature.remediation}</span>
                  {/if}
                </div>
                <span
                  class="sig"
                  class:sig-verified={plugin.signature.level === "verified"}
                  class:sig-present={plugin.signature.level === "present_only"}
                  class:sig-unsigned={plugin.signature.level === "unsigned"}
                  title={plugin.signature.reason}
                >{plugin.signature.label}</span>
              </li>
            {/each}
          </ul>
        {/if}
      {/if}
    </section>
    {#if plugins !== null}
      <section class="card">
        <h2>What a plugin may contribute</h2>
        <p class="note">
          A plugin runs no code of its own.
          <GuideLink section="extensions-and-mcp" label="Why a kind can be unavailable" />
        </p>
        <ul class="event-list">
          {#each plugins.contribution_kinds ?? [] as kind (kind.kind)}
            <li class:event-dead={!kind.available}>
              <strong>{kindLabel(kind.kind)}</strong>
              <span class="hook-tag" class:hook-tag-dead={!kind.available}>
                {kind.available ? "Available" : "Not yet"}
              </span>
              <span class="note">{kind.summary}</span>
            </li>
          {/each}
        </ul>
      </section>
    {/if}
  </div>
{:else}
  <div id="panel-channels" role="tabpanel" aria-labelledby="tab-channels">
    {#if channelsError}
      <div class="notice notice-danger" role="alert">{channelsError}</div>
    {/if}
    {#if channelNotice}
      <div class="notice notice-ok" role="status">{channelNotice}</div>
    {/if}

    <section class="card" data-testid="channel-posture">
      <h2>Channels</h2>
      <p>
        A channel message is <strong>untrusted content with a named sender who is not you</strong>.
        It cannot raise a turn's authority.
      </p>
      <p class="note">
        Linked, enabled, trusted, and reachable are separate.
        <GuideLink route="extensions" label="How extension surfaces are governed" />
      </p>
      {#if channels !== null}
        <ul class="event-list">
          <li class:event-dead={!channels.outbound.runtime_enabled}>
            <strong>Outbound</strong>
            <span class="hook-tag" class:hook-tag-dead={!channels.outbound.runtime_enabled}>
              {channels.outbound.runtime_enabled ? "Capability on" : "Capability off"}
            </span>
            <span class="note">
              {channels.outbound.runtime_enabled
                ? "Governed and audited."
                : "Turn on external channel runtime in Permissions."}
            </span>
          </li>
          <li class:event-dead={!channels.outbound.egress_configured}>
            <strong>Egress</strong>
            <span class="hook-tag" class:hook-tag-dead={!channels.outbound.egress_configured}>
              {channels.outbound.egress_configured
                ? `${channels.outbound.egress_host_count} host${channels.outbound.egress_host_count === 1 ? "" : "s"}`
                : "None allowlisted"}
            </span>
            <span class="note">
              Set <code>RAIKER_CHANNEL_EGRESS_ALLOWLIST</code>; empty denies all hosts.
            </span>
          </li>
          <li class:event-dead={!channels.outbound.signing_configured}>
            <strong>Signing</strong>
            <span class="hook-tag" class:hook-tag-dead={!channels.outbound.signing_configured}>
              {channels.outbound.signing_configured ? "Signed" : "Unsigned"}
            </span>
            <span class="note">
              Set <code>RAIKER_CHANNEL_OUTBOUND_SECRET</code> for HMAC-signed delivery.
            </span>
          </li>
          <li class:event-dead={!channels.inbound.secret_configured}>
            <strong>Inbound</strong>
            <span class="hook-tag" class:hook-tag-dead={!channels.inbound.secret_configured}>
              {channels.inbound.secret_configured ? "Secret set" : "Refusing everything"}
            </span>
            <span class="note">
              Set <code>RAIKER_CHANNEL_INBOUND_SECRET</code>; unset refuses every message.
            </span>
          </li>
          <li>
            <strong>Rate limit</strong>
            <span class="hook-tag">
              {channels.inbound.rate_limit_per_minute ?? 60}/min
            </span>
            <span class="note">
              Per sender and channel; refusals are recorded. Override with
              <code>RAIKER_CHANNEL_INBOUND_RATE</code>.
            </span>
          </li>
        </ul>
      {/if}
    </section>

    <section class="card" data-testid="channel-profiles">
      <h2>Connectors</h2>
      {#if channels === null}
        <p class="note">{channelsError ?? "Reading connector profiles…"}</p>
      {:else if channels.error}
        <p class="note">The connector registry could not be read, so nothing is offered here.</p>
      {:else}
        <ul class="hook-list">
          {#each channels.profiles as profile (profile.connector_id)}
            <li>
              <div class="channel-head">
                <strong>{profile.display_label ?? profile.display_name}</strong>
                <span class="hook-tag" class:hook-tag-dead={!profile.linked}>
                  {profile.linked ? (profile.enabled ? "On" : "Linked, off") : "Not linked"}
                </span>
                {#if profile.requires_sender_allowlist && profile.linked}
                  <span class="hook-tag" class:hook-tag-dead={profile.sender_count === 0}>
                    {profile.sender_count} sender{profile.sender_count === 1 ? "" : "s"}
                  </span>
                {/if}
                {#if profile.linked}
                  <span class="hook-tag">{routeLabel(profile.routing_mode)}</span>
                  {#if profile.approval_relay_enabled}<span class="hook-tag">Approval relay</span>{/if}
                {/if}
              </div>
              <span class="note">
                {profile.transport} · {profile.auth_method}{profile.requires_network
                  ? " · needs network"
                  : " · local only"}
              </span>

              {#if profile.linked}
                <div class="channel-actions">
                  <button
                    type="button"
                    class="btn btn-sm"
                    disabled={channelBusy !== null}
                    onclick={() =>
                      void runChannelAction(
                        `enable:${profile.pairing_id}`,
                        () => api.setChannelEnabled(profile.pairing_id ?? "", !profile.enabled),
                        profile.enabled
                          ? `${profile.display_name} is off.`
                          : `${profile.display_name} is on.`,
                      )}
                  >{profile.enabled ? "Turn off" : "Turn on"}</button>
                  <button
                    type="button"
                    class="btn btn-sm"
                    disabled={channelBusy !== null}
                    onclick={() => {
                      testFor = testFor === profile.connector_id ? null : profile.connector_id;
                      testUrl = "";
                    }}
                  >Send a test delivery</button>
                  <button
                    type="button"
                    class="btn btn-sm"
                    disabled={channelBusy !== null}
                    onclick={() => openRouting(profile)}
                    aria-expanded={routingFor === profile.connector_id}
                  >Routing</button>
                  <button
                    type="button"
                    class="btn btn-sm btn-danger"
                    disabled={channelBusy !== null}
                    onclick={() =>
                      void runChannelAction(
                        `unpair:${profile.pairing_id}`,
                        () => api.unpairChannel(profile.pairing_id ?? ""),
                        `${profile.display_name} is unpaired. Nothing can reach it now.`,
                      )}
                  >Unpair</button>
                </div>
                {#if testFor === profile.connector_id}
                  <form
                    class="channel-form"
                    onsubmit={(event) => {
                      event.preventDefault();
                      sendTest(profile);
                    }}
                  >
                    <label class="field-label" for={`test-${profile.connector_id}`}>
                      Destination URL
                    </label>
                    <input
                      id={`test-${profile.connector_id}`}
                      class="input"
                      bind:value={testUrl}
                      placeholder="https://hooks.example.com/…"
                      autocomplete="off"
                    />
                    <button
                      class="btn btn-sm btn-primary"
                      type="submit"
                      disabled={channelBusy !== null || !testUrl.trim()}
                    >{channelBusy === `test:${profile.connector_id}` ? "Sending…" : "Send"}</button>
                    <p class="note">
                      This runs the same governed path a real delivery takes: the capability gate,
                      the decision mode, the egress allowlist and the audit event all apply.
                    </p>
                  </form>
                {/if}
                {#if routingFor === profile.connector_id}
                  <form class="channel-form routing-form" onsubmit={(event) => { event.preventDefault(); saveRouting(profile); }}>
                    <div class="route-grid">
                      <label class="field-label" for={`route-${profile.connector_id}`}>Inbound</label>
                      <select id={`route-${profile.connector_id}`} class="input" bind:value={routeMode}>
                        <option value="record_only">Record only</option>
                        <option value="new_turn">New turn</option>
                        {#if profile.supports_side_questions}<option value="side_question">Side question</option>{/if}
                        {#if profile.supports_interrupts}<option value="interrupt">Interrupt or steer</option>{/if}
                      </select>
                      <label class="field-label" for={`owner-${profile.connector_id}`}>Owner sender</label>
                      <select id={`owner-${profile.connector_id}`} class="input" bind:value={routeOwner}>
                        <option value="">Not bound</option>
                        {#each profile.senders as sender}<option value={sender}>{sender}</option>{/each}
                      </select>
                      {#if routeMode === "side_question" || routeMode === "interrupt"}
                        <label class="field-label" for={`target-${profile.connector_id}`}>Conversation ID</label>
                        <input id={`target-${profile.connector_id}`} class="input" bind:value={routeTarget} placeholder="sess_…" autocomplete="off" />
                      {/if}
                    </div>
                    {#if profile.supports_approvals}
                      <label class="check-row">
                        <input type="checkbox" bind:checked={routeRelay} disabled={!routeOwner} />
                        <span>Allow exact pending approval responses from the bound owner</span>
                      </label>
                    {/if}
                    <div class="channel-actions">
                      <button class="btn btn-sm btn-primary" type="submit" disabled={channelBusy !== null}>Save routing</button>
                      <button class="btn btn-sm" type="button" onclick={() => (routingFor = null)}>Cancel</button>
                    </div>
                    <p class="note">
                      Record only is the default, and messages cannot choose their route. Side
                      questions have no tool budget; approvals require the exact relay and action
                      identity.
                      <GuideLink section="extensions-and-mcp" label="The routing contract" />
                    </p>
                  </form>
                {/if}
              {:else}
                <div class="channel-actions">
                  <button
                    type="button"
                    class="btn btn-sm"
                    disabled={channelBusy !== null}
                    onclick={() => {
                      pairingFor = pairingFor === profile.connector_id ? null : profile.connector_id;
                      pairSenders = "";
                    }}
                  >Pair</button>
                </div>
                {#if pairingFor === profile.connector_id}
                  <form
                    class="channel-form"
                    onsubmit={(event) => {
                      event.preventDefault();
                      pair(profile);
                    }}
                  >
                    {#if profile.requires_sender_allowlist}
                      <label class="field-label" for={`senders-${profile.connector_id}`}>
                        Allowed senders
                      </label>
                      <input
                        id={`senders-${profile.connector_id}`}
                        class="input"
                        bind:value={pairSenders}
                        placeholder="one id per line, or comma-separated"
                        autocomplete="off"
                      />
                    {/if}
                    <button
                      class="btn btn-sm btn-primary"
                      type="submit"
                      disabled={channelBusy !== null}
                    >{channelBusy === `pair:${profile.connector_id}` ? "Pairing…" : "Pair"}</button>
                    <p class="note">
                      Pairing does not switch it on, and it does not trust anyone. Both are separate
                      decisions you make afterwards.
                    </p>
                  </form>
                {/if}
              {/if}
            </li>
          {/each}
        </ul>
      {/if}
    </section>

  </div>
{/if}

<style>
  .hook-list,
  .event-list,
  .activity-list,
  .hook-errors {
    list-style: none;
    margin: var(--space-3) 0 0;
    padding: 0;
    display: grid;
    gap: var(--space-2);
  }
  .hook-list > li,
  .hook-errors > li {
    display: grid;
    /* A grid item's default `min-width: auto` refuses to shrink below its
       content, so one unbreakable string — an `http` handler's URL — pushed the
       whole card four pixels past a 390px window. Found by the width sweep on
       the very rule this round added. */
    min-width: 0;
    gap: 0.3rem;
    padding: var(--space-3);
    border: 1px solid var(--neutral-border);
    border-radius: var(--r-md);
  }
  /* And the string itself wraps, rather than relying on there being room. */
  .handler-list code,
  .hook-list code {
    overflow-wrap: anywhere;
  }
  /* The event catalogue is a reference list, not a set of findings. Ten bordered
     cards for ten one-line facts read as ten things to deal with, and pushed the
     recent-activity section a screen and a half down the page. */
  .event-list {
    gap: 0;
  }
  .event-list > li {
    display: grid;
    grid-template-columns: minmax(9rem, auto) auto minmax(0, 1fr);
    align-items: baseline;
    gap: var(--space-2);
    padding: 0.32rem 0;
    border-bottom: 1px solid var(--border);
  }
  .event-list > li:last-child {
    border-bottom: 0;
  }
  .event-list > li.event-dead strong {
    color: var(--text-3);
  }
  .hook-tag-dead {
    border-style: dashed;
  }
  .hooks-switch {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    margin-top: var(--space-3);
    font-size: 0.86rem;
    font-weight: 650;
    color: var(--text-1);
    cursor: pointer;
  }
  .hooks-switch input:disabled {
    cursor: wait;
  }
  @media (max-width: 47rem) {
    .event-list > li {
      grid-template-columns: minmax(0, 1fr) auto;
    }
    .event-list > li .note {
      grid-column: 1 / -1;
    }
  }
  /* A rule that can never fire is not an error — the file is valid and a later
     build may emit the event — so it is quieted rather than flagged red.
     Quieted by *border*, never by opacity: dimming the subtree took the note
     text and the scope chip below the 4.5:1 contrast floor, which axe caught.
     The rule still has to be readable; it is the emphasis that drops, and the
     warning line inside it says the rest. */
  .hook-list > li.hook-dead {
    border-style: dashed;
    background: var(--sunken);
  }
  .hook-head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
  }
  .hook-scope {
    font-size: 0.68rem;
    font-weight: 750;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-3);
  }
  /* A plugin rule carries the plugin's name where the other rules carry a scope
     word. It is provenance, not a rank, so it is set apart rather than styled
     like the four owner scopes it sits below — and it keeps its own casing,
     because uppercasing someone's plugin id renames it on screen. Written with
     both classes so it outranks `.hook-scope` regardless of source order. */
  .hook-scope.hook-scope-plugin {
    font-size: 0.74rem;
    font-style: italic;
    letter-spacing: 0;
    text-transform: none;
  }
  .hook-tag {
    padding: 0.1rem 0.45rem;
    border: 1px solid var(--neutral-border);
    border-radius: var(--r-pill);
    background: var(--sunken);
    color: var(--text-3);
    font-size: 0.68rem;
    font-weight: 650;
    white-space: nowrap;
  }
  .hook-tag-decides {
    border-color: var(--accent-border);
    background: var(--accent-soft);
    color: var(--accent);
  }
  .hook-warn {
    color: var(--warn);
  }
  .matcher,
  .events summary { cursor: pointer; display: flex; align-items: baseline; gap: 0.5rem; flex-wrap: wrap; }
  .events-h { font-size: 0.95rem; font-weight: 600; margin: 0; display: inline; }
  .handler-type {
    font-family: var(--font-mono);
    font-size: 0.72rem;
  }
  .handler-list {
    list-style: none;
    margin: 0.2rem 0 0;
    padding: 0;
    display: grid;
    gap: 0.25rem;
  }
  .handler-list li {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: var(--space-2);
  }
  .handler-type {
    padding: 0.05rem 0.35rem;
    border-radius: var(--r-sm);
    background: var(--sunken);
    color: var(--text-2);
  }
  .activity-list li {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: var(--space-2);
    padding: 0.3rem 0;
    border-bottom: 1px solid var(--border);
  }
  .activity-list li:last-child {
    border-bottom: 0;
  }
  .plugin-list {
    list-style: none;
    margin: var(--space-3) 0 0;
    padding: 0;
    display: grid;
    gap: var(--space-2);
  }
  .plugin-list li {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    padding: var(--space-3);
    border: 1px solid var(--neutral-border);
    border-radius: var(--r-md);
  }
  .plugin-copy {
    display: grid;
    gap: 0.1rem;
    min-width: 0;
  }
  .posture {
    margin: 0;
  }
  .posture-warn {
    color: var(--warn);
  }
  .sig {
    font-size: 0.72rem;
    font-weight: 750;
    padding: 0.16rem 0.55rem;
    border-radius: var(--r-pill);
    border: 1px solid var(--neutral-border);
    background: var(--neutral-soft);
    color: var(--text-2);
    white-space: nowrap;
  }
  .sig-verified {
    border-color: var(--ok-border, var(--accent-border));
    background: var(--ok-soft, var(--accent-soft));
    color: var(--ok, var(--accent));
  }
  .sig-present {
    border-color: var(--warn-border);
    background: var(--warn-soft);
    color: var(--warn);
  }
  .sig-unsigned {
    border-color: var(--danger-border, var(--warn-border));
    background: var(--danger-soft, var(--warn-soft));
    color: var(--danger, var(--warn));
  }
  .overview { margin-bottom: var(--space-5); }
  .overview-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-3);
  }
  .overview-head h2 { margin: 0 0 0.2rem; }
.tiles {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
    gap: var(--space-3);
    margin-bottom: var(--space-4);
  }
  .filters { margin-bottom: var(--space-3); }
  .split {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 22rem);
    gap: var(--space-4);
    align-items: start;
  }
  @media (max-width: 63.9rem) { .split { grid-template-columns: 1fr; } }
  .extension-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.35rem; }
  .extension-row {
    display: flex;
    width: 100%;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    flex-wrap: wrap;
    text-align: left;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    color: inherit;
    font: inherit;
    padding: var(--space-3) var(--space-4);
    cursor: pointer;
    transition: border-color 120ms var(--ease), background 120ms var(--ease);
  }
  .extension-row:hover { background: var(--sunken); }
  .extension-row.selected {
    border-color: var(--accent-border);
    box-shadow: 0 0 0 1px var(--accent-border);
  }
  .row-main { display: grid; gap: 0.1rem; min-width: 0; }
  .name { font-weight: 650; }
  .category { color: var(--text-3); font-size: 0.75rem; }
  .facts { display: flex; gap: 0.3rem; flex-wrap: wrap; }
  .fact {
    border: 1px solid var(--border);
    border-radius: var(--r-pill);
    color: var(--text-3);
    font-size: 0.68rem;
    font-weight: 650;
    padding: 0.1rem 0.5rem;
    text-transform: lowercase;
  }
  .fact.on { border-color: var(--ok-border); background: var(--ok-soft); color: var(--ok); }
  .fact.strong.on { border-color: var(--accent-border); background: var(--accent-soft); color: var(--accent); }
  /* BUG-278 — the marker is the channel that is not colour. It sits inside the
     pill so the row stays one line at every width the list is used at. */
  .fact .mark { margin-right: 0.28rem; font-weight: 700; }
  .empty-row { color: var(--text-3); padding: var(--space-4); }
  .reason { color: var(--ok); font-weight: 600; margin: 0; }
  .reason.blocked { color: var(--warn); }
  .pending-approval {
    margin: 0;
    padding: 0.4rem 0.6rem;
    border: 1px solid var(--accent-border);
    background: var(--accent-soft);
    border-radius: var(--r-sm);
    font-size: 0.8rem;
  }
  .note { color: var(--text-3); font-size: 0.78rem; margin: 0; }
  hr { border: 0; border-top: 1px solid var(--border); margin: var(--space-5) 0; }

  /* A connector row: identity and state on one line, the controls under it, and
     the form under those — so the row reads the same whether it is 1440px wide
     or 340px, and nothing has to reflow into a different order. */
  .channel-head {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: var(--space-2);
  }
  .channel-actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin-top: var(--space-2);
  }
  .channel-form {
    display: grid;
    gap: var(--space-2);
    margin-top: var(--space-3);
    padding: var(--space-3);
    border: 1px dashed var(--border);
    border-radius: var(--r-sm);
    background: var(--sunken);
  }
  .channel-form .note { margin: 0; max-width: 60ch; }
  .channel-form .btn { justify-self: start; }
</style>
