<script lang="ts">
  import { onMount } from "svelte";
  import Icon from "../components/Icon.svelte";
  import { api, ApiError } from "../api";
  import type { ConnectorStoreView, StoreConnector } from "../apiTypes";

  let view = $state<ConnectorStoreView | null>(null);
  let error = $state<string | null>(null);
  let query = $state("");
  let category = $state("All");
  let installedOnly = $state(false);
  let selected = $state<StoreConnector | null>(null);
  let busy = $state(false);
  let secret = $state("");
  let showManifest = $state(false);
  let manifestConnectorId = $state("");
  let manifestText = $state("");
  let manifestResult = $state<string | null>(null);
  let mcpConnector = $state<StoreConnector | null>(null);
  let mcpTransport = $state<"local" | "remote">("local");
  let mcpName = $state("");
  let endpointUrl = $state("");
  let authRef = $state("");
  let mcpResult = $state<string | null>(null);

  const categories = $derived(["All", ...new Set((view?.connectors ?? []).map((c) => c.category))]);
  const filtered = $derived(
    (view?.connectors ?? []).filter((c) =>
      `${c.display_name} ${c.description}`.toLowerCase().includes(query.toLowerCase()) &&
      (category === "All" || c.category === category) &&
      (!installedOnly || c.installed),
    ),
  );

  function reason(e: unknown): string {
    return e instanceof ApiError ? e.reasonCode ?? `Request failed (${e.status})` : "Request failed";
  }

  async function load() {
    error = null;
    try {
      view = await api.connectorStore();
      if (selected) selected = view.connectors.find((c) => c.connector_id === selected?.connector_id) ?? null;
    } catch (e) {
      error = reason(e);
    }
  }

  async function install(c: StoreConnector) {
    busy = true; error = null;
    try { await api.installConnector(c.connector_id); await load(); }
    catch (e) { error = reason(e); }
    finally { busy = false; }
  }

  async function authenticate(c: StoreConnector) {
    busy = true; error = null;
    try {
      await api.setConnectorCredentials(c.connector_id, c.auth_type === "oauth2" ? { access_token: secret } : { api_key: secret });
      secret = ""; await load();
    } catch (e) { error = reason(e); }
    finally { busy = false; }
  }

  async function toggle(c: StoreConnector) {
    busy = true; error = null;
    try { await api.setConnectorEnabled(c.connector_id, !c.enabled); await load(); }
    catch (e) { error = reason(e); }
    finally { busy = false; }
  }

  async function uninstall(c: StoreConnector) {
    busy = true; error = null;
    try { await api.uninstallConnector(c.connector_id); selected = null; await load(); }
    catch (e) { error = reason(e); }
    finally { busy = false; }
  }

  function openMcp(c: StoreConnector) {
    mcpConnector = c;
    mcpTransport = "local";
    mcpName = `${c.display_name} MCP`;
    endpointUrl = "";
    authRef = "";
    mcpResult = null;
  }

  async function connectViaMcp() {
    if (!mcpConnector || !mcpName.trim() || (mcpTransport === "remote" && !endpointUrl.trim())) return;
    busy = true; error = null; mcpResult = null;
    try {
      const created = mcpTransport === "local"
        ? await api.createMcpServer(mcpName.trim(), "python-stdio-echo")
        : await api.createRemoteMcpServer(mcpName.trim(), endpointUrl.trim(), authRef.trim() || null);
      if (!created.server_id) throw new Error("MCP connection was not created");
      const connected = await api.connectMcpServer(created.server_id);
      mcpResult = `${mcpName.trim()}: connected · ${connected.tools.length} tool(s).`;
    } catch (e) { error = reason(e); }
    finally { busy = false; }
  }

  async function registerManifest() {
    manifestResult = null;
    try {
      const manifest = JSON.parse(manifestText) as Record<string, unknown>;
      const result = await api.registerConnectorManifest(manifestConnectorId, manifest);
      manifestResult = `${result.operations?.length ?? 0} operations registered`;
    } catch (e) { manifestResult = reason(e); }
  }

  function lifecycle(c: StoreConnector): string {
    if (c.activity_status === "processing") return "Invoking";
    if (!c.installed) return "Available";
    if (c.auth_status === "reauth_required") return "Requires re-authentication";
    if (!c.enabled) return c.auth_status === "connected" ? "Disabled" : "Authentication required";
    return "Connected";
  }

  onMount(load);
</script>

<div class="header"><div><h2>Connector Store</h2><p>Connect services and use their approved actions in chat.</p></div><button class="btn" onclick={() => (showManifest = true)}><Icon name="file" size={15}/> Import manifest</button></div>
<div class="controls"><label class="search"><Icon name="search" size={17}/><span class="sr-only">Search connectors</span><input bind:value={query} placeholder="Search connectors"/></label><label><input type="checkbox" bind:checked={installedOnly}/> Installed</label><button class="icon" aria-label="Refresh connectors" onclick={load}><Icon name="refresh" size={17}/></button></div>
<div class="tabs" role="tablist" aria-label="Connector categories">{#each categories as item (item)}<button role="tab" aria-selected={category === item} class:active={category === item} onclick={() => (category = item)}>{item}</button>{/each}</div>

{#if error}<div class="notice notice-danger" role="alert">{error}</div>{/if}
{#if view && !view.vault_configured}<div class="notice notice-warn"><Icon name="lock" size={16}/> Configure <code>RAIKER_CONNECTOR_VAULT_KEY</code> before linking accounts. Credentials fail closed without it.</div>{/if}
{#if !view}<p class="loading">Loading connectors...</p>{:else}<div class="grid">{#each filtered as c (c.connector_id)}<article><button class="summary" aria-label={`Open ${c.display_name}`} onclick={() => (selected = c)}><span class="logo">{c.display_name[0]}</span><span><span class="title">{c.display_name}<small>{c.category}</small></span><span class="description">{c.description}</span></span></button><footer><span class:connected={lifecycle(c) === "Connected"} class:warning={c.auth_status === "reauth_required"} class="status"><i></i>{lifecycle(c)}</span><span class="footer-actions"><button class="btn btn-sm" onclick={() => openMcp(c)} disabled={busy} aria-label={`Connect ${c.display_name} via MCP`}>Connect via MCP</button><button class="btn btn-sm" class:btn-primary={!c.installed} onclick={() => c.installed ? (selected = c) : install(c)} disabled={busy}>{c.installed ? "Manage" : "Install"}</button></span></footer></article>{:else}<div class="empty">No connectors match this filter.</div>{/each}</div>{/if}

{#if selected}<div class="overlay" role="presentation" onclick={(e) => e.target === e.currentTarget && (selected = null)}><div class="dialog" role="dialog" aria-modal="true" aria-labelledby="detail-title" tabindex="-1"><button class="close" aria-label="Close" onclick={() => (selected = null)}><Icon name="x" size={18}/></button><div class="detail-head"><span class="logo">{selected.display_name[0]}</span><div><h2 id="detail-title">{selected.display_name}</h2><p>{selected.description}</p></div></div><div class="state"><strong>{lifecycle(selected)}</strong><span>{selected.enabled ? "Available in the current session" : "Not available in the current session"}</span></div>{#if !selected.installed}<p>Install this connector to configure authentication and register its manifest.</p><button class="btn btn-primary" onclick={() => install(selected!)} disabled={busy}>Install</button>{:else}<section><h3>Authentication</h3><p>{selected.auth_type === "oauth2" ? "OAuth 2.0 access and refresh credentials are encrypted for this profile." : "The API key is encrypted for this profile."}</p>{#if selected.auth_status !== "connected"}<label class="field-label" for="credential">{selected.auth_type === "oauth2" ? "OAuth access token" : "API key"}</label><input id="credential" class="input credential" type="password" bind:value={secret} autocomplete="off"/><button class="btn btn-primary" onclick={() => authenticate(selected!)} disabled={busy || !secret}>Connect</button>{:else}<div class="notice notice-ok"><Icon name="check" size={15}/> Account connected</div>{/if}</section><section><h3>Session access</h3><p>Writes always stop for explicit confirmation before any request is sent.</p><button class="btn" class:btn-danger={selected.enabled} onclick={() => toggle(selected!)} disabled={busy || selected.auth_status !== "connected"}>{selected.enabled ? "Disable for session" : "Enable for session"}</button></section><div class="danger-zone"><button class="btn btn-danger" onclick={() => uninstall(selected!)} disabled={busy}>Uninstall and remove credentials</button></div>{/if}</div></div>{/if}

{#if mcpConnector}<div class="overlay" role="presentation" onclick={(e) => e.target === e.currentTarget && (mcpConnector = null)}><div class="dialog" role="dialog" aria-modal="true" aria-labelledby="mcp-title" tabindex="-1"><button class="close" aria-label="Close" onclick={() => (mcpConnector = null)}><Icon name="x" size={18}/></button><h2 id="mcp-title">Connect {mcpConnector.display_name} via MCP</h2><p>Add a monitored local starter or a remote MCP server. Raiker stores only a token environment-variable name, never its value.</p><label class="field-label" for="mcp-name">Connection name</label><input id="mcp-name" class="input wide" bind:value={mcpName}/><label><input type="radio" name="mcp-transport" bind:group={mcpTransport} value="local"/> Local starter server</label><label><input type="radio" name="mcp-transport" bind:group={mcpTransport} value="remote"/> Remote MCP server</label>{#if mcpTransport === "remote"}<label class="field-label" for="mcp-endpoint">MCP endpoint URL</label><input id="mcp-endpoint" class="input wide" type="url" bind:value={endpointUrl} placeholder="https://mcp.example.com"/><label class="field-label" for="mcp-token-ref">Token environment variable</label><input id="mcp-token-ref" class="input wide" bind:value={authRef} placeholder="MY_MCP_TOKEN" autocomplete="off"/>{/if}{#if mcpResult}<div class="notice notice-ok">{mcpResult}</div>{/if}<div class="actions"><button class="btn btn-primary" onclick={connectViaMcp} disabled={busy || !mcpName.trim() || (mcpTransport === "remote" && !endpointUrl.trim())}>{busy ? "Connecting..." : "Connect via MCP"}</button></div></div></div>{/if}

{#if showManifest}<div class="overlay" role="presentation" onclick={(e) => e.target === e.currentTarget && (showManifest = false)}><div class="dialog" role="dialog" aria-modal="true" aria-labelledby="manifest-title" tabindex="-1"><button class="close" aria-label="Close" onclick={() => (showManifest = false)}><Icon name="x" size={18}/></button><h2 id="manifest-title">Register connector manifest</h2><p>OpenAPI 2/3 and ai-plugin.json metadata are validated and compiled server-side.</p><label class="field-label" for="connector-id">Connector</label><select id="connector-id" class="select wide" bind:value={manifestConnectorId}><option value="">Select connector</option>{#each view?.connectors ?? [] as c (c.connector_id)}<option value={c.connector_id}>{c.display_name}</option>{/each}</select><label class="field-label" for="manifest-json">Manifest JSON</label><textarea id="manifest-json" class="textarea manifest" bind:value={manifestText}></textarea>{#if manifestResult}<div class="notice">{manifestResult}</div>{/if}<div class="actions"><button class="btn btn-primary" onclick={registerManifest} disabled={!manifestConnectorId || !manifestText}>Validate and register</button></div></div></div>{/if}

<style>
  .header,.controls,footer,.title,.state,.actions,.footer-actions{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3)}.header{margin-bottom:var(--space-4)}.header h2{font-size:1.25rem;margin:0}.header p,.detail-head p,.dialog>p,section p{color:var(--text-2);margin:.2rem 0 0}.controls{justify-content:flex-start}.search{display:flex;align-items:center;gap:.5rem;width:min(34rem,100%);padding:.5rem .7rem;border:1px solid var(--border-strong);border-radius:var(--r-sm);background:var(--surface)}.search input{width:100%;border:0;outline:0;color:var(--text-1);background:transparent;font:inherit}.controls>label{font-size:.82rem;color:var(--text-2)}.icon,.close{display:grid;place-items:center;border:0;background:transparent;color:var(--text-2);padding:.45rem;cursor:pointer}.tabs{display:flex;gap:1.1rem;overflow:auto;border-bottom:1px solid var(--border);margin:var(--space-4) 0}.tabs button{white-space:nowrap;border:0;border-bottom:2px solid transparent;background:transparent;color:var(--text-2);font:inherit;font-size:.8rem;font-weight:600;padding:.55rem 0;cursor:pointer}.tabs button.active{color:var(--text-1);border-color:var(--accent)}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:var(--space-3)}article{border:1px solid var(--border);border-radius:var(--r-sm);background:var(--surface);overflow:hidden}.summary{display:flex;gap:.8rem;width:100%;min-height:112px;padding:var(--space-4);text-align:left;border:0;background:transparent;color:inherit;cursor:pointer}.summary:hover{background:var(--sunken)}.logo{display:grid;place-items:center;flex:0 0 42px;height:42px;border:1px solid var(--accent-border);border-radius:8px;color:var(--accent);background:var(--accent-soft);font-size:1.05rem;font-weight:800}.title{justify-content:flex-start;font-weight:700}.title small{color:var(--text-3);font-size:.65rem;text-transform:uppercase}.description{display:block;margin-top:.35rem;color:var(--text-2);font-size:.8rem}footer{padding:.65rem var(--space-4);border-top:1px solid var(--border)}.status{display:flex;align-items:center;gap:.4rem;color:var(--text-3);font-size:.73rem;font-weight:600}.status i{width:7px;height:7px;border-radius:50%;background:currentColor}.status.connected{color:var(--ok)}.status.warning{color:var(--warn)}.overlay{position:fixed;inset:0;z-index:100;display:grid;place-items:center;padding:var(--space-4);background:var(--overlay)}.dialog{position:relative;width:min(570px,100%);max-height:90vh;overflow:auto;padding:var(--space-5);border:1px solid var(--border-strong);border-radius:var(--r-sm);background:var(--raised);box-shadow:var(--shadow-2)}.close{position:absolute;right:.6rem;top:.6rem}.detail-head{display:flex;gap:var(--space-3);padding-right:2rem}.detail-head h2{margin:0}.state{margin:var(--space-5) 0;padding:.75rem;background:var(--sunken);border-radius:var(--r-sm);font-size:.8rem}.state span{color:var(--text-2)}section{padding:var(--space-4) 0;border-top:1px solid var(--border)}.credential,.wide{width:100%;margin-bottom:.65rem}.danger-zone{margin-top:var(--space-3);padding-top:var(--space-3);border-top:1px solid var(--danger-border)}.manifest{min-height:220px;font-family:var(--font-mono);font-size:.76rem}.actions{justify-content:flex-end;margin-top:var(--space-3)}.empty{grid-column:1/-1;padding:3rem;text-align:center;color:var(--text-3)}.notice{margin-bottom:var(--space-3)}
  @media(max-width:640px){.header{align-items:flex-start}.controls{flex-wrap:wrap}.search{flex-basis:100%}.grid{grid-template-columns:1fr}.state{align-items:flex-start;flex-direction:column}}
</style>
