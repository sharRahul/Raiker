<script lang="ts">
  import { onMount } from "svelte";
  import GuideLink from "../components/GuideLink.svelte";
  import Icon from "../components/Icon.svelte";
  import NotificationCenter from "../components/NotificationCenter.svelte";
  import { api, ApiError } from "../api";
  import { runtimeBlock } from "../capabilityModel";
  import type {
    CapabilityGate,
    McpAgentAccess,
    McpFinding,
    McpOffer,
    McpServer,
    McpSession,
    McpToolDeclaration,
    Notification,
  } from "../apiTypes";

  // Reviewed server templates the builder can generate. `id` is the backend
  // template key; `label` is the plain-English name shown to the user. Kept in
  // sync with the backend `available_mcp_templates()` (currently one safe
  // starter server that just echoes text back).
  const TEMPLATES = [{ id: "python-stdio-echo", label: "Sample echo server (safe starter)" }];

  function templateLabel(id: string | null): string {
    if (!id) return "None";
    return TEMPLATES.find((t) => t.id === id)?.label ?? id;
  }

  let servers = $state<McpServer[] | null>(null);
  // BUG-221 — servers installed plugins offer. An offer is a description, not a
  // connection: adding one runs the ordinary governed create path, so a plugin
  // goes *through* the trust gate rather than around it.
  let offers = $state<McpOffer[]>([]);
  let gates = $state<CapabilityGate[]>([]);
  let error = $state<string | null>(null);
  let notice = $state<string | null>(null);
  let busy = $state<string | null>(null); // server_id (or "create") currently mutating

  let newName = $state("");
  let newTemplate = $state(TEMPLATES[0].id);
  let renamingId = $state<string | null>(null);
  let renameValue = $state("");
  let sessions = $state<Record<string, McpSession[]>>({});
  let findings = $state<Record<string, McpFinding[]>>({});
  let notifications = $state<Notification[]>([]);
  // B8 — connecting a server and the agent being able to *use* it are two
  // different facts. The page used to report only the first, so a server could
  // read `connected · 2 tool(s)` while every call was withheld by the decision
  // mode. This is the second fact, read from the runtime rather than inferred.
  let agentAccess = $state<McpAgentAccess | null>(null);

  const builderEnabled = $derived(
    gates.find((g) => g.capability === "mcp_builder_runtime")?.runtime_enabled ?? false,
  );
  const connectorEnabled = $derived(
    gates.find((g) => g.capability === "mcp_connector_runtime")?.runtime_enabled ?? false,
  );
  // BUG-11 — say which of the three shut states this is. "Enable it in
  // Capabilities" was wrong whenever the capability was already enabled but
  // below runtime level: following it changed nothing.
  const blocks = $derived(
    [
      runtimeBlock(gates.find((g) => g.capability === "mcp_builder_runtime"), "The MCP builder"),
      runtimeBlock(gates.find((g) => g.capability === "mcp_connector_runtime"), "The MCP connector"),
    ].filter((block) => block.kind !== "none"),
  );

  /**
   * Plain English for the exact runtime reason MCP tools are not reachable.
   *
   * Returns nothing when the connector's own block above already says it. A
   * closed connector gate used to produce two amber notices one under the other,
   * saying the same fact in different words and naming the same page by two
   * different names — which reads as two problems rather than one.
   */
  const connectorBlocked = $derived(
    blocks.some((block) => block.reason.startsWith("The MCP connector")),
  );
  const accessBlock = $derived.by(() => {
    if (agentAccess === null || agentAccess.callable) return null;
    if (agentAccess.reason_code === "mcp_gate_disabled") {
      if (connectorBlocked) return null;
      return {
        text: "Raiker cannot call any MCP tool: the MCP connector capability is not enabled at runtime level.",
        action: "Enable it in",
      };
    }
    if (agentAccess.reason_code === "mcp_denied_by_decision_mode") {
      return {
        text: "MCP tool calls are set to Deny, so a connected server stays a monitoring entry.",
        action: "Change the decision mode in",
      };
    }
    return {
      text:
        `Connected MCP tools are withheld from every turn: the MCP decision mode is ` +
        `“${agentAccess.decision_mode}”, which holds a tool call for a decision that a running turn ` +
        "cannot wait for. Set it to Always allow (or Let Raiker decide with a low-risk floor) to let " +
        "the agent call them.",
      action: "Change the decision mode in",
    };
  });

  /**
   * One line for what a tool takes. Required names first, optional after the
   * separator, so the shape reads without a legend.
   *
   * The three ways a tool can have no declared arguments are three different
   * facts and are worded as three, because "no arguments" for a tool that takes
   * two is the kind of quiet wrongness this whole surface exists to avoid.
   */
  function declaredArguments(s: McpServer, tool: string): string {
    const d: McpToolDeclaration | undefined = s.tool_declarations.find((e) => e.name === tool);
    if (!d) return "Run Test to read what this takes";
    if (!d.has_schema) {
      if (d.schema_reason === "too_large") return "Declaration too large to carry";
      if (d.schema_reason === "not_an_object_schema") return "Declaration not usable";
      return "No arguments declared";
    }
    const required = d.required.filter((name) => d.arguments.includes(name));
    const optional = d.arguments.filter((name) => !d.required.includes(name));
    if (!required.length && !optional.length) return "Takes no arguments";
    const parts: string[] = [];
    if (required.length) parts.push(required.join(", "));
    if (optional.length) parts.push(`optional: ${optional.join(", ")}`);
    return parts.join(" · ");
  }

  function reason(e: unknown): string {
    if (e instanceof ApiError) {
      if (e.reasonCode === "disabled_by_capability_gate")
        return "The MCP capability is disabled. Enable it in Permissions to continue.";
      return e.reasonCode ?? `Request failed (${e.status})`;
    }
    return "Request failed";
  }

  async function load() {
    error = null;
    try {
      const [list, gateList, access, offered] = await Promise.all([
        api.mcpServers(),
        api.capabilityGates(),
        api.mcpAgentAccess().catch(() => null),
        // An empty offer list is the normal case, so a failure here must not
        // take the page down with it.
        api.mcpOffers().catch(() => [] as McpOffer[]),
      ]);
      servers = list;
      gates = gateList;
      agentAccess = access;
      offers = offered;
      if (list.length) {
        const [details, notes] = await Promise.all([
          Promise.all(list.map(async (server) => ({
            serverId: server.server_id,
            sessions: await api.mcpSessions(server.server_id),
            findings: await api.mcpFindings(server.server_id),
          }))),
          api.notifications(),
        ]);
        sessions = Object.fromEntries(details.map((detail) => [detail.serverId, detail.sessions]));
        findings = Object.fromEntries(details.map((detail) => [detail.serverId, detail.findings]));
        notifications = notes;
      } else {
        sessions = {};
        findings = {};
        notifications = [];
      }
    } catch (e) {
      error = reason(e);
    }
  }

  async function create(event: Event) {
    event.preventDefault();
    if (!newName.trim()) return;
    busy = "create";
    error = null;
    notice = null;
    try {
      await api.createMcpServer(newName.trim(), newTemplate);
      notice = `Created “${newName.trim()}”.`;
      newName = "";
      await load();
    } catch (e) {
      error = reason(e);
    } finally {
      busy = null;
    }
  }

  async function addOffer(offer: McpOffer) {
    busy = `offer:${offer.plugin_id}/${offer.name}`;
    error = null;
    notice = null;
    try {
      if (offer.transport === "http") {
        await api.createRemoteMcpServer(
          offer.name,
          offer.endpoint_url ?? "",
          offer.auth_ref ?? null,
        );
      } else {
        await api.createMcpServer(offer.name, offer.template ?? "");
      }
      notice = `Added “${offer.name}”. Nothing is connected yet — test the connection below.`;
      await load();
    } catch (e) {
      error = reason(e);
    } finally {
      busy = null;
    }
  }

  async function test(server: McpServer) {
    busy = server.server_id;
    error = null;
    notice = null;
    try {
      const result = await api.connectMcpServer(server.server_id);
      notice = `${server.name}: connected · ${result.tools.length} tool(s).`;
      await load();
    } catch (e) {
      error = `${server.name}: ${reason(e)}`;
    } finally {
      busy = null;
    }
  }

  function startRename(server: McpServer) {
    renamingId = server.server_id;
    renameValue = server.name;
  }

  async function commitRename(server: McpServer) {
    if (!renameValue.trim() || renameValue.trim() === server.name) {
      renamingId = null;
      return;
    }
    busy = server.server_id;
    error = null;
    try {
      await api.renameMcpServer(server.server_id, renameValue.trim());
      renamingId = null;
      await load();
    } catch (e) {
      error = reason(e);
    } finally {
      busy = null;
    }
  }

  async function remove(server: McpServer) {
    if (!confirm(`Delete “${server.name}”? This removes its profile and generated server file.`))
      return;
    busy = server.server_id;
    error = null;
    notice = null;
    try {
      await api.deleteMcpServer(server.server_id);
      notice = `Deleted “${server.name}”.`;
      await load();
    } catch (e) {
      error = reason(e);
    } finally {
      busy = null;
    }
  }

  async function contain(server: McpServer) {
    busy = server.server_id;
    error = null;
    notice = null;
    try {
      const result = server.monitor_state === "active"
        ? await api.pauseMcpServer(server.server_id)
        : await api.resumeMcpServer(server.server_id);
      notice = `${server.name}: ${result.monitor_state === "active" ? "resumed" : "stopped"}.`;
      await load();
    } catch (e) {
      error = `${server.name}: ${reason(e)}`;
    } finally {
      busy = null;
    }
  }

  function statusLabel(s: McpServer): string {
    if (s.monitor_state === "paused") return "Paused";
    if (s.monitor_state === "killed") return "Stopped";
    if (s.status === "connected") return "Connected";
    if (s.status === "error") return "Error";
    return "Created";
  }

  onMount(() => {
    void load();
    const timer = window.setInterval(load, 10_000);
    return () => window.clearInterval(timer);
  });
</script>

<!-- The tab strip above already says "MCP servers", and the panel is named by
     it, so a heading here said the page's own name a second time and a
     paragraph explained it a third. What an MCP server is belongs in the guide;
     this page opens with its own state. -->
<div class="header">
  <GuideLink section="extensions-and-mcp" label="How MCP servers work" />
  <button class="icon" aria-label="Refresh servers" onclick={load}><Icon name="refresh" size="md" /></button>
</div>

{#each blocks as block (block.reason)}
  <div class="notice notice-warn" role="status">
    <Icon name="warning" size="md" />
    <span>
      {block.reason}
      {#if block.action}{block.action}{/if}
      {#if block.href}<a href={block.href}>{block.linkLabel}</a>{/if}
    </span>
  </div>
{/each}

{#if accessBlock}
  <div class="notice notice-warn" role="status">
    <Icon name="warning" size="md" />
    <span>
      {accessBlock.text}
      {accessBlock.action}
      <!-- The route is `#/capabilities`; the page is called Permissions
           everywhere an owner sees it, and so is this link. -->
      <a href="#/capabilities">Permissions</a>.
    </span>
  </div>
{:else if agentAccess?.callable && agentAccess.projected_tools > 0}
  <div class="notice notice-ok" role="status">
    <Icon name="check" size="sm" />
    <span>
      {agentAccess.projected_tools}
      {agentAccess.projected_tools === 1 ? "tool is" : "tools are"} available to Raiker in Chat and Build
      as <code>mcp__server__tool</code>. Every call is still policy-reviewed, monitored, and audited.
    </span>
  </div>
{/if}

{#if error}<div class="notice notice-danger" role="alert">{error}</div>{/if}
{#if notice}<div class="notice notice-ok"><Icon name="check" size="sm" /> {notice}</div>{/if}
<NotificationCenter {notifications} />

<form class="create" onsubmit={create}>
  <div class="field">
    <label class="field-label" for="mcp-name">Server name</label>
    <input id="mcp-name" class="input" bind:value={newName} placeholder="e.g. My notes helper" autocomplete="off" disabled={!builderEnabled} />
  </div>
  <div class="field">
    <label class="field-label" for="mcp-template">Template</label>
    <select id="mcp-template" class="select" bind:value={newTemplate} disabled={!builderEnabled}>
      {#each TEMPLATES as t (t.id)}<option value={t.id}>{t.label}</option>{/each}
    </select>
  </div>
  <!-- Creating a server needs the builder capability; keep the control disabled
       while it is off rather than firing a request that can only 403 (FIX-04). -->
  <button class="btn btn-primary" type="submit" disabled={busy === "create" || !newName.trim() || !builderEnabled} title={builderEnabled ? undefined : "Enable the MCP builder capability to create a server."}>
    {busy === "create" ? "Creating…" : "Create server"}
  </button>
</form>

{#if offers.length > 0}
  <section class="offers" aria-labelledby="mcp-offers-heading">
    <h3 id="mcp-offers-heading">Offered by your plugins</h3>
    <p class="offers-lead">
      A plugin can describe a server it works with. Nothing here is connected or reachable —
      adding one runs the same governed create path as filling in the form above.
    </p>
    <ul class="offer-list">
      {#each offers as offer (offer.plugin_id + "/" + offer.name)}
        <li>
          <div class="offer-copy">
            <strong>{offer.name}</strong>
            <span class="offer-meta">
              {offer.transport === "http" ? "Remote (HTTPS)" : "Local (stdio)"} · from plugin
              <code>{offer.plugin_id}</code>
            </span>
            {#if offer.description}<span class="offer-meta">{offer.description}</span>{/if}
            {#if offer.transport === "http" && offer.endpoint_url}
              <span class="offer-meta mono">{offer.endpoint_url}</span>
            {/if}
            {#if offer.auth_ref}
              <span class="offer-meta">
                Reads its token from <code>{offer.auth_ref}</code>. The token is never stored here.
              </span>
            {/if}
          </div>
          {#if offer.already_added}
            <span class="offer-added">Added</span>
          {:else}
            <button
              class="btn btn-sm"
              type="button"
              onclick={() => addOffer(offer)}
              disabled={busy === `offer:${offer.plugin_id}/${offer.name}`}
            >{busy === `offer:${offer.plugin_id}/${offer.name}` ? "Adding…" : "Add server"}</button>
          {/if}
        </li>
      {/each}
    </ul>
  </section>
{/if}

{#if !servers}
  <p class="loading">Loading MCP servers…</p>
{:else if servers.length === 0}
  <!-- An empty state that ignores an offer sitting directly above it reads as a
       contradiction. When a plugin has offered one, that is the shortest route. -->
  <div class="empty">
    {offers.length > 0
      ? "No MCP servers yet. Add one your plugins offer above, or create one from a template."
      : "No MCP servers yet. Create one from a template above."}
  </div>
{:else}
  <ul class="list">
    {#each servers as s (s.server_id)}
      <li class="card">
        <div class="top">
          <div class="name-block">
            {#if renamingId === s.server_id}
              <input
                class="input rename"
                bind:value={renameValue}
                onkeydown={(e) => e.key === "Enter" && commitRename(s)}
                aria-label="New server name"
              />
              <button class="btn btn-sm btn-primary" onclick={() => commitRename(s)} disabled={busy === s.server_id}>Save</button>
              <button class="btn btn-sm" onclick={() => (renamingId = null)}>Cancel</button>
            {:else}
              <span class="name">{s.name}</span>
              <span class="status" class:connected={s.status === "connected" && s.monitor_state === "active"} class:danger={s.status === "error" || s.monitor_state !== "active"}>
                <i></i>{statusLabel(s)}
              </span>
            {/if}
          </div>
          {#if renamingId !== s.server_id}
            <div class="actions">
              <button class="btn btn-sm" onclick={() => test(s)} disabled={busy === s.server_id || !connectorEnabled}>
                {busy === s.server_id ? "Testing…" : "Test"}
              </button>
              <button class="btn btn-sm" class:btn-danger={s.monitor_state === "active"} onclick={() => contain(s)} disabled={busy === s.server_id}>
                {s.monitor_state === "active" ? "Stop" : "Resume"}
              </button>
              <button class="btn btn-sm" onclick={() => startRename(s)} disabled={busy === s.server_id}>Rename</button>
              <button class="btn btn-sm btn-danger" onclick={() => remove(s)} disabled={busy === s.server_id}>Delete</button>
            </div>
          {/if}
        </div>
        {#if s.monitor_state !== "active"}
          <div class="notice notice-warn monitor-banner">{s.monitor_state === "killed" ? "Stopped" : "Paused"}: {s.paused_reason ?? "Owner control"}</div>
        {/if}
        <dl class="meta">
          <div><dt>{s.transport === "http" ? "Endpoint" : "Command"}</dt><dd><code>{s.transport === "http" ? s.endpoint_url : s.command.join(" ")}</code></dd></div>
          <div><dt>{s.transport === "http" ? "Token reference" : "Template"}</dt><dd>{s.transport === "http" ? s.auth_ref ?? "None" : templateLabel(s.template)}</dd></div>
          <div><dt>Last connected</dt><dd>{s.last_connected_at ?? "Never"}</dd></div>
          <!-- BUG-234 — which revision of the Model Context Protocol this
               server agreed to. Nothing said it before, so "why will this
               server not connect" had no answer on the page. -->
          <div>
            <dt>Protocol</dt>
            <dd>{s.protocol_version ?? "Not negotiated yet"}</dd>
          </div>
        </dl>
        <div class="tools">
          <span class="tools-label">Tools ({s.tool_count})</span>
          {#if s.tools.length}
            <!-- The one thing the card could not previously say: whether the
                 agent can actually call these. -->
            {#if s.status === "connected" && s.monitor_state === "active"}
              <span class="reach" class:ok={agentAccess?.callable === true}>
                {agentAccess?.callable === true
                  ? "Callable by Raiker"
                  : "Not callable yet — see above"}
              </span>
            {/if}
          {:else}
            <span class="muted">Run Test to discover this server's tools.</span>
          {/if}
        </div>
        <!-- BUG-234 — Raiker speaks the current revision and uses one part of
             it. A server offering more used to be connected with none of that
             said anywhere, which is the one thing this surface must not do. -->
        {#if s.unsupported_features.length}
          <ul class="unsupported">
            {#each s.unsupported_features as f (f.feature)}
              <li><span class="feature">{f.feature}</span> {f.note}</li>
            {/each}
          </ul>
        {/if}
        <!-- Backlog #16 (MCP half) — the name and what it takes, on one line
             each. This replaced a row of name chips: the chips said what was
             here and could not say what any of it took, so a server whose tools
             declare their arguments looked identical to one whose tools do not. -->
        {#if s.tools.length}
          <dl class="declared">
            {#each s.tools as tool (tool)}
              <div>
                <dt>{tool}</dt>
                <dd>{declaredArguments(s, tool)}</dd>
              </div>
            {/each}
          </dl>
        {/if}
        <div class="monitor">
          <span class="tools-label">Recent sessions</span>
          {#if sessions[s.server_id]?.length}
            {#each sessions[s.server_id] as session (session.session_row_id)}
              <span class="chip">{session.operation} · {session.tool_calls} tool calls · {session.outcome}</span>
            {/each}
          {:else}<span class="muted">No monitored sessions yet.</span>{/if}
          {#if findings[s.server_id]?.length}
            <span class="tools-label">Open findings</span>
            {#each findings[s.server_id].filter((finding) => finding.state === "open") as finding (finding.finding_id)}
              <span class="finding">{finding.severity}: {finding.summary}</span>
            {/each}
          {/if}
        </div>
      </li>
    {/each}
  </ul>
{/if}

<style>
  .header { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-4); }
  .icon { display: grid; place-items: center; border: 0; background: transparent; color: var(--text-2); padding: 0.45rem; cursor: pointer; }
  .notice { display: flex; align-items: center; gap: 0.5rem; margin-bottom: var(--space-3); }
  .notice a { color: var(--accent); font-weight: 600; }
  .create { display: flex; align-items: flex-end; gap: var(--space-3); flex-wrap: wrap; padding: var(--space-4); border: 1px solid var(--border); border-radius: var(--r-sm); background: var(--surface); margin-bottom: var(--space-4); }
  .field { display: flex; flex-direction: column; gap: 0.35rem; }
  .field-label { font-size: 0.75rem; font-weight: 600; color: var(--text-2); }
  .input { min-width: 16rem; }
  .rename { min-width: 12rem; }
  .list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--space-3); }
  .card { border: 1px solid var(--border); border-radius: var(--r-sm); background: var(--surface); padding: var(--space-4); }
  .top { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); flex-wrap: wrap; }
  .name-block { display: flex; align-items: center; gap: 0.7rem; }
  .name { font-weight: 700; font-size: 1rem; }
  .status { display: flex; align-items: center; gap: 0.4rem; color: var(--text-3); font-size: 0.73rem; font-weight: 600; }
  .status i { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
  .status.connected { color: var(--ok); }
  .status.danger { color: var(--danger); }
  .actions { display: flex; gap: 0.45rem; flex-wrap: wrap; }
  .meta { display: flex; flex-wrap: wrap; gap: var(--space-4); margin: var(--space-3) 0 0; }
  .meta div { display: flex; flex-direction: column; gap: 0.15rem; }
  .meta dt { font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-3); }
  .meta dd { margin: 0; font-size: 0.82rem; color: var(--text-2); }
  .meta code { font-family: var(--font-mono); font-size: 0.78rem; color: var(--text-1); background: var(--sunken); padding: 0.1rem 0.4rem; border-radius: 4px; }
  .tools { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; margin-top: var(--space-3); padding-top: var(--space-3); border-top: 1px solid var(--border); }
  .monitor { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; margin-top: var(--space-3); padding-top: var(--space-3); border-top: 1px solid var(--border); }
  .monitor-banner { margin: var(--space-3) 0 0; }
  .finding { font-size: .75rem; font-weight: 600; padding: .2rem .6rem; border-radius: 999px; background: var(--danger-soft); color: var(--danger); border: 1px solid var(--danger-border); }
  .unsupported { margin: var(--space-2) 0 0; padding: 0; list-style: none; display: grid; gap: 0.2rem; }
  .unsupported li { font-size: 0.76rem; color: var(--text-3); }
  .unsupported .feature { font-family: var(--font-mono, monospace); color: var(--text-2); }
  .declared { margin: var(--space-2) 0 0; display: grid; gap: 0.25rem; }
  .declared div { display: flex; gap: 0.5rem; flex-wrap: wrap; font-size: 0.78rem; }
  .declared dt { font-family: var(--font-mono, monospace); color: var(--text-2); }
  .declared dd { margin: 0; color: var(--text-3); }
  .tools-label { font-size: 0.72rem; font-weight: 600; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.05em; }
  .chip { font-size: 0.75rem; font-weight: 600; padding: 0.2rem 0.6rem; border-radius: 999px; background: var(--accent-soft); color: var(--accent); border: 1px solid var(--accent-border); }
  .muted { color: var(--text-3); font-size: var(--text-sm); }
  .reach { font-size: .72rem; font-weight: 600; padding: .2rem .6rem; border-radius: 999px; background: var(--warn-soft, var(--sunken)); color: var(--warn); border: 1px solid var(--border); }
  .reach.ok { background: var(--ok-soft, var(--sunken)); color: var(--ok); }
  .notice code { font-family: var(--font-mono); font-size: 0.78rem; background: var(--sunken); padding: 0.05rem 0.35rem; border-radius: 4px; }
  .loading, .empty { padding: 2.5rem; text-align: center; color: var(--text-3); }
  .empty { border: 1px dashed var(--border); border-radius: var(--r-sm); }
  @media (max-width: 640px) {
    .header { align-items: flex-start; }
    .create { flex-direction: column; align-items: stretch; }
    .input { min-width: 0; }
    .top { align-items: flex-start; }
  }

  /* Offers are a *proposal* list, not a server list: visually quieter than the
     real servers below, and never carrying a connection state of their own. */
  .offers {
    margin: var(--space-4) 0 0;
    padding: var(--space-3);
    border: 1px dashed var(--border);
    border-radius: var(--r-md);
    background: var(--sunken);
  }
  .offers h3 { margin: 0 0 0.2rem; font-size: 0.95rem; }
  .offers-lead { margin: 0; color: var(--text-2); font-size: 0.84rem; max-width: 60ch; }
  .offer-list { list-style: none; margin: var(--space-3) 0 0; padding: 0; display: grid; gap: var(--space-2); }
  .offer-list > li {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-3);
    flex-wrap: wrap;
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: var(--surface);
  }
  .offer-copy { display: grid; gap: 0.15rem; min-width: 0; }
  .offer-meta { color: var(--text-2); font-size: 0.8rem; overflow-wrap: anywhere; }
  .offer-added { color: var(--text-3); font-size: 0.8rem; font-weight: 650; align-self: center; }
  @media (max-width: 40rem) {
    .offer-list > li { flex-direction: column; align-items: stretch; }
  }
</style>
