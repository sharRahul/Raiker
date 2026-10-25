<script lang="ts">
  /**
   * QUI-L07 — Connections: what Raiker is connected to.
   *
   * Three tabs. **Services** lists the services that are connected and adds
   * new ones in a dialog; **Channels** does the same for messaging channels;
   * **Advanced** is MCP servers, skills, hooks and plugins as one segmented
   * list. Each mounts the existing governed views unchanged — this is layout,
   * not a second mutation path.
   */
  import { onMount, untrack } from "svelte";
  import ConnectionsView from "./ConnectionsView.svelte";
  import McpView from "./McpView.svelte";
  import SkillsView from "./SkillsView.svelte";
  import TabStrip from "../components/TabStrip.svelte";
  import GuideLink from "../components/GuideLink.svelte";
  import LazyRoute from "../components/LazyRoute.svelte";
  import { api, ApiError } from "../api";
  import type { HooksView, PluginContributions, PluginsView } from "../apiTypes";
  import { relativeTime } from "../format";
  import { ADVANCED_KINDS, HUB_TABS, advancedKindFromHash, type AdvancedKind } from "../nav";

  let { tab = "services", kind: initialKind = undefined }: { tab?: string; kind?: AdvancedKind } =
    $props();

  // BUG-79 — reads the installed records and this workspace's own signing
  // posture, so `verified` and `present only` never look identical.
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

  const tabs = HUB_TABS.connections.map((id) => ({
    id,
    label: { services: "Services", channels: "Channels", advanced: "Advanced" }[id] as string,
  }));

  const KIND_NAMES: Record<AdvancedKind, string> = {
    mcp: "MCP servers",
    skills: "Skills",
    hooks: "Hooks",
    plugins: "Plugins",
  };

  // The prop names the first segment shown; the owner's choice wins after.
  let kind = $state<AdvancedKind>(
    untrack(() => initialKind) ??
      (typeof window === "undefined" ? "mcp" : advancedKindFromHash(window.location.hash)),
  );

  function selectTab(next: string) {
    window.location.hash = `#/connections?tab=${encodeURIComponent(next)}`;
  }

  function selectKind(next: AdvancedKind) {
    kind = next;
    history.replaceState(history.state, "", `#/connections?tab=advanced&kind=${next}`);
  }

  onMount(() => {
    const read = () => (kind = advancedKindFromHash(window.location.hash));
    window.addEventListener("hashchange", read);
    void loadPlugins();
    void loadHooks();
    return () => window.removeEventListener("hashchange", read);
  });
</script>

<TabStrip {tabs} selected={tab} onselect={selectTab} label="Connection categories" />

{#if tab === "services"}
  <div id="panel-services" role="tabpanel" aria-labelledby="tab-services">
    <ConnectionsView />
  </div>
{:else if tab === "channels"}
  <div id="panel-channels" role="tabpanel" aria-labelledby="tab-channels">
    <LazyRoute route="messaging" />
  </div>
{:else if tab === "advanced"}
  <div id="panel-advanced" role="tabpanel" aria-labelledby="tab-advanced">
    <div class="advanced-head">
      <!-- One segmented list instead of four tabs: these are the technical
           ways Raiker reaches tools, and an owner opens them rarely. -->
      <div class="segmented" role="group" aria-label="Advanced connections">
        {#each ADVANCED_KINDS as id (id)}
          <button
            type="button"
            class="segment"
            aria-pressed={kind === id}
            onclick={() => selectKind(id)}>{KIND_NAMES[id]}</button
          >
        {/each}
      </div>
      <GuideLink section="extensions-and-mcp" label="How these are governed" />
    </div>
    {#if kind === "mcp"}
      <McpView />
    {:else if kind === "skills"}
      <SkillsView />
    {:else if kind === "hooks"}
  <div id="panel-hooks" role="tabpanel" aria-labelledby="tab-hooks">
    <section class="card">
      <!-- The tab strip already says "Hooks", and what a hook *is* was five
           lines read once and in the way on every later visit. The one claim
           that must stay on the page is the one an owner would otherwise have to
           take on trust: a hook can only ever make an action stricter. -->
      <h2 class="sr-only">Hooks</h2>
      <p class="note">
        A hook can only make an action <strong>stricter</strong> — never allow one Raiker
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

      <!-- REM-EXT-01 — operator reference, kept and moved out of the reading
           order. What a handler *may be* is the same four clauses on every
           visit; what an owner opens this tab for is whether their rule ran.
           Collapsed with the counts in the summary, so the page still answers
           "how many builtins does this build ship" without the list. -->
      <section class="card">
        <details class="events">
          <summary>
            <h2 class="events-h">What a handler may be</h2>
            <span class="note">4 types · {hooks.builtins.length} built in</span>
          </summary>
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
          <h3 class="events-h">Built-in handlers this build ships</h3>
          <ul class="event-list">
            {#each hooks.builtins as builtin (builtin)}
              <li><strong>{builtin}</strong></li>
            {/each}
          </ul>
        </details>
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
    {:else if kind === "plugins"}
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
                      <a href="#/connections?tab=advanced&kind=hooks">See the rules in Hooks →</a>
                    </span>
                  {/if}
                  {#if contributedSkills(plugin.contributions) > 0}
                    <span class="note">
                      Its skills install switched off.
                      <a href="#/connections?tab=advanced&kind=skills">Turn them on in Skills →</a>
                    </span>
                  {/if}
                  {#if offeredServers(plugin.contributions) > 0}
                    <span class="note">
                      An offered server is inert until you add it.
                      <a href="#/connections?tab=advanced&kind=mcp">Review it in MCP servers →</a>
                    </span>
                  {/if}
                  <span class="note">{plugin.signature.explanation}</span>
                  {#if plugin.signature.remediation}
                    <span class="note">{plugin.signature.remediation}</span>
                  {/if}
                  {#if plugin.code_runtime}
                    <!-- BUG-308 — never a claim of containment this machine
                         cannot keep: where its own code would run, here. -->
                    <span class="note" data-testid="plugin-code-runtime">
                      <strong>Code:</strong> {plugin.code_runtime.summary}
                    </span>
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
      <!-- REM-EXT-01 — the contribution catalogue is reference, not state. It
           says the same four things about every plugin and about none, and it
           sat below the inventory as a full card of equal weight. Collapsed,
           with the count that is the actual question in the summary. -->
      <section class="card">
        <details class="events">
          <summary>
            <h2 class="events-h">What a plugin may contribute</h2>
            <span class="note">
              {(plugins.contribution_kinds ?? []).filter((kind) => kind.available).length} of
              {(plugins.contribution_kinds ?? []).length} kinds available
            </span>
          </summary>
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
        </details>
      </section>
    {/if}
  </div>
    {/if}
  </div>
{/if}


<style>
  .advanced-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
  }


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
       content, so one unbreakable string — an `http` handler's URL — would
       push the card past a 390px window. */
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
    font-size: var(--text-sm);
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
    font-size: var(--text-2xs);
    font-weight: 750;
    color: var(--text-3);
  }
  /* A plugin rule carries the plugin's name where the other rules carry a scope
     word. It is provenance, not a rank, so it is set apart rather than styled
     like the four owner scopes it sits below — and it keeps its own casing,
     because uppercasing someone's plugin id renames it on screen. Written with
     both classes so it outranks `.hook-scope` regardless of source order. */
  .hook-scope.hook-scope-plugin {
    font-size: var(--text-xs);
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
    font-size: var(--text-2xs);
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
  .events-h { font-size: var(--text-md); font-weight: 600; margin: 0; display: inline; }
  .handler-type {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
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
    font-size: var(--text-xs);
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

  .note { color: var(--text-3); font-size: var(--text-sm); margin: 0; }


  /* A connector row: identity and state on one line, the controls under it, and
     the form under those — so the row reads the same whether it is 1440px wide
     or 340px, and nothing has to reflow into a different order. */
</style>
