<script lang="ts">
  import { onMount } from "svelte";
  import Icon from "../components/Icon.svelte";
  import { api, ApiError } from "../api";
  import type { CapabilityGate, McpServer } from "../apiTypes";

  // Reviewed server templates the builder can generate. Kept in sync with the
  // backend `available_mcp_templates()` (currently a single safe echo template).
  const TEMPLATES = [{ id: "python-stdio-echo", label: "Python stdio · echo (safe demo)" }];

  let servers = $state<McpServer[] | null>(null);
  let gates = $state<CapabilityGate[]>([]);
  let error = $state<string | null>(null);
  let notice = $state<string | null>(null);
  let busy = $state<string | null>(null); // server_id (or "create") currently mutating

  let newName = $state("");
  let newTemplate = $state(TEMPLATES[0].id);
  let renamingId = $state<string | null>(null);
  let renameValue = $state("");

  const builderEnabled = $derived(
    gates.find((g) => g.capability === "mcp_builder_runtime")?.runtime_enabled ?? false,
  );
  const connectorEnabled = $derived(
    gates.find((g) => g.capability === "mcp_connector_runtime")?.runtime_enabled ?? false,
  );

  function reason(e: unknown): string {
    if (e instanceof ApiError) {
      if (e.reasonCode === "disabled_by_capability_gate")
        return "The MCP capability is disabled. Enable it in Capabilities to continue.";
      return e.reasonCode ?? `Request failed (${e.status})`;
    }
    return "Request failed";
  }

  async function load() {
    error = null;
    try {
      const [list, gateList] = await Promise.all([api.mcpServers(), api.capabilityGates()]);
      servers = list;
      gates = gateList;
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

  function statusLabel(s: McpServer): string {
    if (s.status === "connected") return "Connected";
    if (s.status === "error") return "Error";
    return "Created";
  }

  onMount(load);
</script>

<div class="header">
  <div>
    <h2>MCP Servers</h2>
    <p>Build, test, and manage governed local stdio MCP servers for this workspace.</p>
  </div>
  <button class="icon" aria-label="Refresh servers" onclick={load}><Icon name="refresh" size={17} /></button>
</div>

{#if !builderEnabled || !connectorEnabled}
  <div class="notice notice-warn" role="status">
    <Icon name="warning" size={16} />
    <span>
      The MCP {!builderEnabled && !connectorEnabled ? "builder and connector capabilities are" : !builderEnabled ? "builder capability is" : "connector capability is"} disabled.
      Enable {!builderEnabled && !connectorEnabled ? "them" : "it"} in <a href="#/capabilities">Capabilities</a> to create or test servers.
    </span>
  </div>
{/if}

{#if error}<div class="notice notice-danger" role="alert">{error}</div>{/if}
{#if notice}<div class="notice notice-ok"><Icon name="check" size={15} /> {notice}</div>{/if}

<form class="create" onsubmit={create}>
  <div class="field">
    <label class="field-label" for="mcp-name">Server name</label>
    <input id="mcp-name" class="input" bind:value={newName} placeholder="my-tools" autocomplete="off" />
  </div>
  <div class="field">
    <label class="field-label" for="mcp-template">Template</label>
    <select id="mcp-template" class="select" bind:value={newTemplate}>
      {#each TEMPLATES as t (t.id)}<option value={t.id}>{t.label}</option>{/each}
    </select>
  </div>
  <button class="btn btn-primary" type="submit" disabled={busy === "create" || !newName.trim()}>
    {busy === "create" ? "Creating…" : "Create server"}
  </button>
</form>

{#if !servers}
  <p class="loading">Loading MCP servers…</p>
{:else if servers.length === 0}
  <div class="empty">No MCP servers yet. Create one from a template above.</div>
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
              <span class="status" class:connected={s.status === "connected"} class:danger={s.status === "error"}>
                <i></i>{statusLabel(s)}
              </span>
            {/if}
          </div>
          {#if renamingId !== s.server_id}
            <div class="actions">
              <button class="btn btn-sm" onclick={() => test(s)} disabled={busy === s.server_id || !connectorEnabled}>
                {busy === s.server_id ? "Testing…" : "Test"}
              </button>
              <button class="btn btn-sm" onclick={() => startRename(s)} disabled={busy === s.server_id}>Rename</button>
              <button class="btn btn-sm btn-danger" onclick={() => remove(s)} disabled={busy === s.server_id}>Delete</button>
            </div>
          {/if}
        </div>
        <dl class="meta">
          <div><dt>Command</dt><dd><code>{s.command.join(" ")}</code></dd></div>
          <div><dt>Template</dt><dd>{s.template ?? "—"}</dd></div>
          <div><dt>Last connected</dt><dd>{s.last_connected_at ?? "Never"}</dd></div>
        </dl>
        <div class="tools">
          <span class="tools-label">Tools ({s.tool_count})</span>
          {#if s.tools.length}
            {#each s.tools as tool (tool)}<span class="chip">{tool}</span>{/each}
          {:else}
            <span class="muted">Run Test to discover this server's tools.</span>
          {/if}
        </div>
      </li>
    {/each}
  </ul>
{/if}

<style>
  .header { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-4); }
  .header h2 { font-size: 1.25rem; margin: 0; }
  .header p { color: var(--text-2); margin: 0.2rem 0 0; }
  .icon { display: grid; place-items: center; border: 0; background: transparent; color: var(--text-2); padding: 0.45rem; cursor: pointer; }
  .notice { display: flex; align-items: center; gap: 0.5rem; margin-bottom: var(--space-3); }
  .notice a { color: var(--accent); font-weight: 600; }
  .create { display: flex; align-items: flex-end; gap: var(--space-3); flex-wrap: wrap; padding: var(--space-4); border: 1px solid var(--border); border-radius: var(--r-sm); background: var(--surface); margin-bottom: var(--space-4); }
  .field { display: flex; flex-direction: column; gap: 0.35rem; }
  .field-label { font-size: 0.75rem; font-weight: 600; color: var(--text-2); }
  .input, .select { padding: 0.5rem 0.65rem; border: 1px solid var(--border-strong); border-radius: var(--r-sm); background: var(--surface); color: var(--text-1); font: inherit; }
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
  .tools-label { font-size: 0.72rem; font-weight: 600; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.05em; }
  .chip { font-size: 0.75rem; font-weight: 600; padding: 0.2rem 0.6rem; border-radius: 999px; background: var(--accent-soft); color: var(--accent); border: 1px solid var(--accent-border); }
  .muted { color: var(--text-3); font-size: 0.8rem; }
  .loading, .empty { padding: 2.5rem; text-align: center; color: var(--text-3); }
  .empty { border: 1px dashed var(--border); border-radius: var(--r-sm); }
  @media (max-width: 640px) {
    .header { align-items: flex-start; }
    .create { flex-direction: column; align-items: stretch; }
    .input { min-width: 0; }
    .top { align-items: flex-start; }
  }
</style>
