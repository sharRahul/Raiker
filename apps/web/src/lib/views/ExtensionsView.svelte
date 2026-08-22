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
    ExtensionView,
    ExtensionsOverview,
    HooksView,
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
          <Icon name="refresh" size={15} /> Refresh
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
                  <span class="facts">
                    <span class="fact" class:on={extension.installed}>installed</span>
                    <span class="fact" class:on={extension.connected}>connected</span>
                    <span class="fact" class:on={extension.enabled}>enabled</span>
                    <span class="fact strong" class:on={extension.usable}>usable</span>
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
                Changing any of these goes through the governed control plane — the capability gate,
                the credential vault, and the approval path. This panel reports state; it never
                grants it.
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
      <h2>Hooks</h2>
      <p class="note">
        A hook runs your own logic at a point in a turn. It can only make an action
        <strong>stricter</strong> — a hook may deny a tool call or turn it into a decision, and can
        never allow one the runtime refused, skip an approval, or reach past the tool broker.
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
        <p class="note">
          Your setting, not a fourth configuration file — a file a project ships cannot re-enable
          itself. Rules stay listed while this is on, so you can see what would run.
        </p>

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
                <span class="hook-scope">{rule.scope}</span>
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
                        no builtin by this name in this build — it will fail every time it matches
                      </span>
                    {:else if !handler.decision_authority}
                      <span class="note">advisory</span>
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
      <section class="card">
        <h2>What fires, and what it can change</h2>
        <p class="note">
          Every event a configuration file may name. A rule written for an event this build does not
          emit parses cleanly and never runs, which is why the list says which is which.
        </p>
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
      </section>

      <section class="card">
        <h2>Built-in handlers</h2>
        <p class="note">
          Raiker's own code, so a builtin always carries decision authority. A rule naming anything
          else parses, matches, and then fails every time.
        </p>
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
      <p class="measure">
        Raiker reads <code>config/managed-hooks.json</code>, <code>config/hooks.json</code> and
        <code>.raiker/hooks.json</code>, in that order of authority. A lower scope can never
        override a higher-scope deny. This page reports what the runtime loaded; it does not edit
        those files, because a surface that rewrote your own configuration would need an authority
        story it does not have yet.
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
            Nothing is installed, and no plugin code runs in this browser. The
            posture above is what a plugin installed today would meet.
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
    <section class="card deferred">
      <h2>Plugin panels are not available yet</h2>
      <p>
        A plugin cannot render its own page here until Raiker has an accepted route, permission, and
        accessibility contract for it. Listing them early would suggest an authority the runtime does
        not enforce, so this tab stays empty on purpose.
      </p>
    </section>
  </div>
{:else}
  <div id="panel-channels" role="tabpanel" aria-labelledby="tab-channels">
    <section class="card deferred">
      <h2>Channels and webhooks are not available yet</h2>
      <p>
        Inbound and outbound delivery needs an accepted contract and threat model before Raiker
        offers controls for it. Until then there is nothing to configure here, and no channel can
        deliver work on your behalf.
      </p>
      <p class="note">This tab exists so the gap is visible rather than silently missing.</p>
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
    gap: 0.3rem;
    padding: var(--space-3);
    border: 1px solid var(--neutral-border);
    border-radius: var(--r-md);
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
  .hooks-switch input {
    width: 1rem;
    height: 1rem;
    accent-color: var(--accent);
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
  .deferred { max-width: 46rem; }
  /* A reading measure for one prose paragraph, without borrowing `deferred`'s
     meaning to get it. */
  .measure { max-width: 46rem; }
  .deferred h2 { margin-top: 0; }
</style>
