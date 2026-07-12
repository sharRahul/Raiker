<script lang="ts">
  import { onMount } from "svelte";
  import Icon from "../components/Icon.svelte";
  import { api, ApiError } from "../api";
  import type { ConnectionsView, ConnectorView } from "../apiTypes";

  type Category = "All" | "Developer" | "Productivity" | "Communication";
  type Operation = { method: string; path: string; operationId: string };

  const categories: Category[] = ["All", "Developer", "Productivity", "Communication"];
  const descriptions: Record<string, string> = {
    github: "Search and read issues and pull requests from your repositories.",
    gmail: "Find messages and threads in your connected Gmail account.",
    gcal: "Read calendars and event details while planning your work.",
    slack: "Read channel information and recent conversation history.",
  };
  const categoryById: Record<string, Category> = {
    github: "Developer",
    gmail: "Productivity",
    gcal: "Productivity",
    slack: "Communication",
  };

  let view = $state<ConnectionsView | null>(null);
  let loadError = $state<string | null>(null);
  let query = $state("");
  let category = $state<Category>("All");
  let installedOnly = $state(false);
  let selected = $state<ConnectorView | null>(null);
  let saving = $state(false);
  let actionError = $state<string | null>(null);
  let showManifest = $state(false);
  let manifestText = $state("");
  const manifestPlaceholder = '{ "openapi": "3.0.0", "paths": { ... } }';
  let manifestError = $state<string | null>(null);
  let operations = $state<Operation[]>([]);

  const filtered = $derived(
    (view?.connectors ?? []).filter((c) => {
      const text = `${c.display_name} ${descriptions[c.connector_id] ?? ""}`.toLowerCase();
      return (
        text.includes(query.trim().toLowerCase()) &&
        (category === "All" || categoryById[c.connector_id] === category) &&
        (!installedOnly || c.capability_enabled)
      );
    }),
  );

  async function load() {
    loadError = null;
    try {
      view = await api.connections();
      if (selected) selected = view.connectors.find((c) => c.connector_id === selected?.connector_id) ?? null;
    } catch (e) {
      view = null;
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }

  function usable(c: ConnectorView): boolean {
    return c.capability_enabled && c.decision_mode === "allow" && c.credential_configured && c.egress_allowed;
  }

  function status(c: ConnectorView): string {
    if (usable(c)) return "Active";
    if (c.capability_enabled) return "Setup required";
    return "Not enabled";
  }

  async function setEnabled(c: ConnectorView, enabled: boolean) {
    saving = true;
    actionError = null;
    try {
      if (enabled) {
        await api.setCapabilityDecisionMode(c.capability, "allow", "Enabled from Connectors");
      } else {
        await api.setCapabilityDecisionMode(c.capability, "deny", "Disabled from Connectors");
      }
      await load();
    } catch (e) {
      actionError = e instanceof ApiError && e.reasonCode ? e.reasonCode : "The runtime refused this change.";
    } finally {
      saving = false;
    }
  }

  function inspectManifest() {
    manifestError = null;
    operations = [];
    try {
      const doc = JSON.parse(manifestText) as Record<string, unknown>;
      const version = typeof doc.openapi === "string" ? doc.openapi : typeof doc.swagger === "string" ? doc.swagger : null;
      if (!version) throw new Error("missing_version");
      const paths = doc.paths;
      if (!paths || typeof paths !== "object" || Array.isArray(paths)) throw new Error("missing_paths");
      const found: Operation[] = [];
      for (const [path, item] of Object.entries(paths)) {
        if (!item || typeof item !== "object" || Array.isArray(item)) continue;
        for (const [method, operation] of Object.entries(item)) {
          if (!["get", "post", "put", "patch", "delete"].includes(method) || !operation || typeof operation !== "object") continue;
          const id = (operation as Record<string, unknown>).operationId;
          found.push({ method: method.toUpperCase(), path, operationId: typeof id === "string" ? id : `${method}_${path.replace(/[^a-z0-9]+/gi, "_")}` });
        }
      }
      if (!found.length) throw new Error("no_operations");
      operations = found;
    } catch {
      manifestError = "Enter a valid JSON OpenAPI 3.x or Swagger 2.0 document with at least one operation.";
    }
  }

  onMount(load);
</script>

<div class="store-head">
  <div>
    <h2>Connectors</h2>
    <p>Bring trusted services into Raiker conversations.</p>
  </div>
  <button class="btn" type="button" onclick={() => (showManifest = true)}><Icon name="file" size={15} /> Import manifest</button>
</div>

<div class="search-row">
  <label class="search-box">
    <Icon name="search" size={17} />
    <span class="sr-only">Search connectors</span>
    <input bind:value={query} placeholder="Search connectors" />
  </label>
  <label class="installed-filter"><input type="checkbox" bind:checked={installedOnly} /> Enabled</label>
  <button class="icon-btn" type="button" onclick={load} aria-label="Refresh connectors"><Icon name="refresh" size={17} /></button>
</div>

<div class="tabs" role="tablist" aria-label="Connector categories">
  {#each categories as item (item)}
    <button type="button" role="tab" aria-selected={category === item} class:active={category === item} onclick={() => (category = item)}>{item}</button>
  {/each}
</div>

{#if loadError}
  <p class="error" role="alert">{loadError}</p>
{:else if view === null}
  <p class="loading">Loading connectors...</p>
{:else}
  {#if !view.connector_egress_allowlist_configured}
    <div class="notice notice-warn" role="status"><Icon name="warning" size={17} /> Network access is closed until the owner configures the connector egress allowlist.</div>
  {/if}
  <div class="catalog">
    {#each filtered as c (c.connector_id)}
      <article class="connector-card">
        <button class="card-main" type="button" onclick={() => (selected = c)} aria-label={`Open ${c.display_name}`}>
          <span class="logo logo-{c.connector_id}">{c.display_name.slice(0, 1)}</span>
          <span class="card-copy">
            <span class="name-row"><strong>{c.display_name.replace(" (read-only)", "")}</strong><span class="category">{categoryById[c.connector_id]}</span></span>
            <span>{descriptions[c.connector_id]}</span>
          </span>
        </button>
        <div class="card-foot">
          <span class:active-status={usable(c)} class="state"><span class="dot"></span>{status(c)}</span>
          <button class="btn btn-sm" class:btn-primary={!c.capability_enabled} type="button" onclick={() => (selected = c)}>{c.capability_enabled ? "Manage" : "Set up"}</button>
        </div>
      </article>
    {:else}
      <div class="empty"><Icon name="search" size={22} /><strong>No connectors found</strong><span>Try another search or category.</span></div>
    {/each}
  </div>
{/if}

{#if selected}
  <div class="overlay" role="presentation" onclick={(e) => e.currentTarget === e.target && (selected = null)}>
    <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="connector-title" tabindex="-1">
      <button class="close" type="button" aria-label="Close" onclick={() => (selected = null)}><Icon name="x" size={18} /></button>
      <div class="detail-title"><span class="logo logo-{selected.connector_id}">{selected.display_name.slice(0, 1)}</span><div><h2 id="connector-title">{selected.display_name.replace(" (read-only)", "")}</h2><p>{descriptions[selected.connector_id]}</p></div></div>
      <div class="session-state"><span class:active-status={usable(selected)} class="state"><span class="dot"></span>{status(selected)}</span><span>Session access: {usable(selected) ? "available to chat" : "inactive"}</span></div>
      <div class="detail-section"><h3>Authentication</h3><p>{selected.credential_configured ? "Account credential is configured." : `Set ${selected.credential_env} in the Raiker server environment, then refresh.`}</p><div class="check-line"><Icon name={selected.credential_configured ? "check" : "lock"} size={15} /><span>{selected.credential_configured ? "Account linked" : "API key or OAuth token required"}</span></div></div>
      <div class="detail-section"><h3>Access</h3><p>{selected.actions.map((a) => a.replaceAll("_", " ")).join(" · ")}</p><div class="check-line"><Icon name={selected.egress_allowed ? "check" : "lock"} size={15} /><span>{selected.egress_allowed ? `${selected.egress_host} allowed` : `${selected.egress_host} blocked by egress policy`}</span></div></div>
      {#if actionError}<p class="error" role="alert">{actionError}</p>{/if}
      <div class="dialog-actions"><span class="governed"><Icon name="shield" size={15} /> Governed by capability policy</span><button class="btn" class:btn-danger={selected.decision_mode === "allow"} class:btn-primary={selected.decision_mode !== "allow"} disabled={saving || !selected.capability_enabled} type="button" onclick={() => setEnabled(selected!, selected!.decision_mode !== "allow")}>{saving ? "Saving..." : selected.decision_mode === "allow" ? "Disable for chat" : "Enable for chat"}</button></div>
      {#if !selected.capability_enabled}<p class="gate-note">Turn on <code>{selected.capability}</code> in Capabilities before enabling this connector.</p>{/if}
    </div>
  </div>
{/if}

{#if showManifest}
  <div class="overlay" role="presentation" onclick={(e) => e.currentTarget === e.target && (showManifest = false)}>
    <div class="dialog manifest-dialog" role="dialog" aria-modal="true" aria-labelledby="manifest-title" tabindex="-1">
      <button class="close" type="button" aria-label="Close" onclick={() => (showManifest = false)}><Icon name="x" size={18} /></button>
      <h2 id="manifest-title">Import an OpenAPI manifest</h2>
      <p class="dialog-lead">Inspect a manifest and review every discovered endpoint before creating a governed connector.</p>
      <label class="field-label" for="manifest">Manifest JSON</label><textarea id="manifest" class="textarea manifest-input" bind:value={manifestText} placeholder={manifestPlaceholder}></textarea>
      {#if manifestError}<p class="error" role="alert">{manifestError}</p>{/if}
      {#if operations.length}
        <div class="operations"><h3>{operations.length} discovered operation{operations.length === 1 ? "" : "s"}</h3>{#each operations as operation (`${operation.method}:${operation.path}`)}<div class="operation"><code class="method">{operation.method}</code><code>{operation.path}</code><span>{operation.operationId}</span></div>{/each}</div>
        <div class="notice"><Icon name="shield" size={16} /> Discovery does not grant network access or execute endpoints. A real executor, host allowlist, authentication, and capability approval are still required.</div>
      {/if}
      <div class="dialog-actions"><span></span><button class="btn btn-primary" type="button" onclick={inspectManifest}>Inspect manifest</button></div>
    </div>
  </div>
{/if}

<style>
  .store-head,.search-row,.card-foot,.dialog-actions,.session-state,.name-row{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3)}
  .store-head{margin-bottom:var(--space-4)} .store-head h2{font-size:1.25rem;margin:0}.store-head p{color:var(--text-2);margin:.2rem 0 0}
  .search-row{justify-content:flex-start}.search-box{width:min(34rem,100%);display:flex;align-items:center;gap:.55rem;border:1px solid var(--border-strong);background:var(--surface);border-radius:var(--r-sm);padding:.5rem .7rem}.search-box input{border:0;outline:0;background:transparent;color:var(--text-1);font:inherit;width:100%}.installed-filter{display:flex;gap:.4rem;color:var(--text-2);font-size:.84rem}.icon-btn,.close{display:grid;place-items:center;border:0;background:transparent;color:var(--text-2);cursor:pointer;padding:.45rem;border-radius:var(--r-sm)}.icon-btn:hover,.close:hover{background:var(--sunken);color:var(--text-1)}
  .tabs{display:flex;gap:1.25rem;border-bottom:1px solid var(--border);margin:var(--space-4) 0}.tabs button{border:0;border-bottom:2px solid transparent;background:transparent;color:var(--text-2);font:inherit;font-size:.84rem;font-weight:600;padding:.55rem .1rem;cursor:pointer}.tabs button.active{color:var(--text-1);border-color:var(--accent)}
  .catalog{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:var(--space-3)}.connector-card{border:1px solid var(--border);background:var(--surface);border-radius:var(--r-sm);overflow:hidden}.card-main{width:100%;display:flex;gap:.85rem;text-align:left;border:0;background:transparent;color:inherit;padding:var(--space-4);cursor:pointer}.card-main:hover{background:var(--sunken)}.card-copy{display:flex;min-width:0;flex-direction:column;gap:.35rem;color:var(--text-2);font-size:.83rem}.card-copy strong{color:var(--text-1);font-size:.95rem}.name-row{justify-content:flex-start}.category{color:var(--text-3);font-size:.68rem;text-transform:uppercase}.logo{display:grid;place-items:center;flex:0 0 42px;height:42px;border-radius:8px;background:var(--neutral-soft);border:1px solid var(--neutral-border);font-size:1.1rem;font-weight:800}.logo-github{background:var(--neutral-soft)}.logo-gmail{color:var(--danger);background:var(--danger-soft)}.logo-gcal{color:var(--info);background:var(--info-soft)}.logo-slack{color:var(--accent);background:var(--accent-soft)}.card-foot{border-top:1px solid var(--border);padding:.65rem var(--space-4)}
  .state{display:inline-flex;align-items:center;gap:.4rem;color:var(--text-3);font-size:.77rem;font-weight:600}.dot{width:7px;height:7px;border-radius:50%;background:currentColor}.active-status{color:var(--ok)}.empty{grid-column:1/-1;display:flex;flex-direction:column;align-items:center;gap:.3rem;color:var(--text-3);padding:3rem}.empty strong{color:var(--text-1)}
  .overlay{position:fixed;inset:0;z-index:100;background:var(--overlay);display:grid;place-items:center;padding:var(--space-4)}.dialog{position:relative;width:min(570px,100%);max-height:90vh;overflow:auto;background:var(--raised);border:1px solid var(--border-strong);border-radius:var(--r-sm);box-shadow:var(--shadow-2);padding:var(--space-5)}.close{position:absolute;right:.7rem;top:.7rem}.detail-title{display:flex;gap:var(--space-3);padding-right:2rem}.detail-title h2{margin:0}.detail-title p,.dialog-lead{color:var(--text-2);margin:.2rem 0 0}.session-state{margin:var(--space-5) 0;padding:.75rem;background:var(--sunken);border-radius:var(--r-sm);font-size:.82rem;color:var(--text-2)}.detail-section{padding:var(--space-3) 0;border-top:1px solid var(--border)}.detail-section h3{margin-bottom:.3rem}.detail-section p{color:var(--text-2);font-size:.84rem}.check-line,.governed{display:flex;align-items:center;gap:.45rem;color:var(--text-2);font-size:.8rem}.dialog-actions{margin-top:var(--space-4);padding-top:var(--space-3);border-top:1px solid var(--border)}.gate-note{color:var(--text-3);font-size:.76rem;text-align:right;margin:.5rem 0 0}.manifest-input{min-height:180px;font-family:var(--font-mono);font-size:.78rem}.operations{margin:var(--space-3) 0;max-height:180px;overflow:auto;border:1px solid var(--border);border-radius:var(--r-sm)}.operations h3{padding:.7rem;margin:0}.operation{display:grid;grid-template-columns:52px minmax(120px,1fr) minmax(100px,1fr);gap:.6rem;padding:.55rem .7rem;border-top:1px solid var(--border);font-size:.76rem}.operation span{overflow:hidden;text-overflow:ellipsis}.method{color:var(--accent);font-weight:700}.error{color:var(--danger)}.notice{margin-bottom:var(--space-3)}
  @media(max-width:640px){.store-head{align-items:flex-start}.search-row{flex-wrap:wrap}.search-box{order:-1;flex-basis:100%}.tabs{overflow-x:auto}.catalog{grid-template-columns:1fr}.dialog-actions{align-items:flex-end}.governed{max-width:180px}.operation{grid-template-columns:48px 1fr}.operation span{grid-column:2}}
</style>
