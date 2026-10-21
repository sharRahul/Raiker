<script lang="ts">
  /**
   * QUI-L07 — Connections › Services.
   *
   * The page lists only what is connected: services you installed and GitHub
   * once an account is signed in. Everything that *could* be connected is the
   * catalogue in **Add connection**, so the page no longer repeats every
   * service as a status row and again as an install card.
   *
   * Each row opens its detail beside the list (QUI-L02): the four readiness
   * facts the server reports, what the service may do, its credential, and
   * session access. Nothing here grants anything; a connection stores a
   * credential and the capability gates in Permissions still decide.
   */
  import { onMount } from "svelte";
  import Icon from "../components/Icon.svelte";
  import PageState from "../components/PageState.svelte";
  import ListDetail from "../components/ListDetail.svelte";
  import AddDialog from "../components/AddDialog.svelte";
  import type { AddOption } from "../addDialog";
  import LifecycleTrack from "../components/LifecycleTrack.svelte";
  import GuideLink from "../components/GuideLink.svelte";
  import GitHubConnection from "./settings/GitHubConnection.svelte";
  import { api, ApiError } from "../api";
  import { endpointRefusal, networkClassLabel } from "../mcpEndpoint";
  import { relativeTime } from "../format";
  import {
    connectionBlockedCopy,
    connectionStatus,
    connectionSteps,
  } from "../connectionPresentation";
  import type {
    ApprovalView,
    ConnectorStoreView,
    ExtensionView,
    StoreConnector,
  } from "../apiTypes";

  const GITHUB_ID = "github-account";

  interface ServiceRow {
    id: string;
    name: string;
    category: string;
    status: string;
    connector: StoreConnector | null;
  }

  let view = $state<ConnectorStoreView | null>(null);
  let extensions = $state<ExtensionView[]>([]);
  let approvals = $state<ApprovalView[]>([]);
  let githubConnected = $state(false);
  let error = $state<string | null>(null);
  let busy = $state(false);
  let secret = $state("");
  let selectedId = $state<string | null>(null);
  let adding = $state(false);
  let chosen = $state<string | null>(null);
  let showManifest = $state(false);
  let manifestConnectorId = $state("");
  let manifestText = $state("");
  let manifestResult = $state<string | null>(null);
  let mcpOpen = $state(false);
  let mcpTransport = $state<"local" | "remote">("local");
  let mcpName = $state("");
  let endpointUrl = $state("");
  let authRef = $state("");
  let mcpResult = $state<string | null>(null);

  const services = $derived<ServiceRow[]>([
    ...(githubConnected
      ? [{ id: GITHUB_ID, name: "GitHub", category: "Code", status: "Signed in", connector: null }]
      : []),
    ...(view?.connectors ?? [])
      .filter((connector) => connector.installed)
      .map((connector) => ({
        id: connector.connector_id,
        name: connector.display_name,
        category: connector.category,
        status: connectionStatus(connector),
        connector,
      })),
  ]);

  const catalogue = $derived<AddOption[]>([
    ...(githubConnected
      ? []
      : [
          {
            id: GITHUB_ID,
            name: "GitHub",
            category: "Code",
            description: "Sign in so Build can push branches and open pull requests.",
          },
        ]),
    ...(view?.connectors ?? [])
      .filter((connector) => !connector.installed)
      .map((connector) => ({
        id: connector.connector_id,
        name: connector.display_name,
        category: connector.category,
        description: connector.description,
      })),
  ]);

  function connectorById(id: string | null): StoreConnector | null {
    return (view?.connectors ?? []).find((connector) => connector.connector_id === id) ?? null;
  }

  function extensionFor(connector: StoreConnector): ExtensionView | null {
    return extensions.find((row) => row.extension_id === `connector:${connector.connector_id}`) ?? null;
  }

  function pendingFor(extension: ExtensionView | null): number {
    if (extension?.capability == null) return 0;
    return approvals.filter((approval) => approval.capability === extension.capability).length;
  }

  function reason(e: unknown): string {
    if (!(e instanceof ApiError)) return "The request did not reach Raiker. Nothing was changed. Try again.";
    // RR-MCP-02 — a refused endpoint is explained in words an owner can act on,
    // not shown as its reason code.
    return endpointRefusal(e.reasonCode) ?? e.reasonCode ?? `The request was refused (HTTP ${e.status}). Nothing was changed.`;
  }

  async function load() {
    error = null;
    try {
      view = await api.connectorStore();
    } catch (e) {
      error = reason(e);
    }
    try {
      extensions = (await api.extensions()).extensions;
    } catch {
      extensions = [];
    }
    try {
      approvals = await api.approvals();
    } catch {
      approvals = [];
    }
    try {
      const github = await api.github();
      githubConnected = github.states.connected_account || github.states.credential_available;
    } catch {
      githubConnected = false;
    }
  }

  async function act(action: () => Promise<unknown>) {
    busy = true;
    error = null;
    try {
      await action();
      await load();
      return true;
    } catch (e) {
      error = reason(e);
      return false;
    } finally {
      busy = false;
    }
  }

  async function install(connector: StoreConnector) {
    await act(() => api.installConnector(connector.connector_id));
  }

  async function authenticate(connector: StoreConnector) {
    const done = await act(() =>
      api.setConnectorCredentials(
        connector.connector_id,
        connector.auth_type === "oauth2" ? { access_token: secret } : { api_key: secret },
      ),
    );
    if (done) secret = "";
  }

  async function finishAdding(connector: StoreConnector) {
    adding = false;
    chosen = null;
    selectedId = connector.connector_id;
  }

  async function toggle(connector: StoreConnector) {
    await act(() => api.setConnectorEnabled(connector.connector_id, !connector.enabled));
  }

  async function uninstall(connector: StoreConnector) {
    if (await act(() => api.uninstallConnector(connector.connector_id))) selectedId = null;
  }

  function openMcp(connector: StoreConnector) {
    mcpOpen = true;
    mcpTransport = "local";
    mcpName = `${connector.display_name} MCP`;
    endpointUrl = "";
    authRef = "";
    mcpResult = null;
  }

  async function connectViaMcp() {
    if (!mcpName.trim() || (mcpTransport === "remote" && !endpointUrl.trim())) return;
    busy = true;
    error = null;
    mcpResult = null;
    try {
      const created =
        mcpTransport === "local"
          ? await api.createMcpServer(mcpName.trim(), "python-stdio-echo")
          : await api.createRemoteMcpServer(mcpName.trim(), endpointUrl.trim(), authRef.trim() || null);
      if (!created.server_id) throw new Error("MCP connection was not created");
      const connected = await api.connectMcpServer(created.server_id);
      mcpResult = `${mcpName.trim()}: connected · ${connected.tools.length} tool(s). It is listed under Advanced › MCP servers.`;
    } catch (e) {
      error = reason(e);
    } finally {
      busy = false;
    }
  }

  async function registerManifest() {
    manifestResult = null;
    try {
      const manifest = JSON.parse(manifestText) as Record<string, unknown>;
      const result = await api.registerConnectorManifest(manifestConnectorId, manifest);
      manifestResult = `${result.operations?.length ?? 0} operations registered`;
    } catch (e) {
      manifestResult = e instanceof SyntaxError ? "That is not valid JSON. Nothing was registered." : reason(e);
    }
  }

  function closeAdd() {
    adding = false;
    chosen = null;
    mcpOpen = false;
    secret = "";
    void load();
  }

  onMount(load);
</script>

<div class="services-head">
  <GuideLink route="connections" />
  <div class="head-actions">
    {#if services.length > 0}
      <button type="button" class="btn btn-ghost btn-sm" onclick={() => (showManifest = true)}>
        <Icon name="file" size="sm" /> Import manifest
      </button>
    {/if}
    <button type="button" class="btn btn-primary" onclick={() => (adding = true)}>
      <Icon name="plus" size="sm" /> Add connection
    </button>
  </div>
</div>

{#if error}<div class="notice notice-danger" role="alert">{error}</div>{/if}
{#if view && !view.vault_configured}
  <!-- The one readiness fact that stops a connection, shown only when true. -->
  <div class="attention-row" role="status">
    <Icon name="lock" size="sm" />
    <span>Linking an account needs the vault key. Credentials fail closed until it is set.</span>
    <a class="btn btn-sm" href="#/settings?tab=security">Set up</a>
  </div>
{/if}

{#if view === null && error === null}
  <PageState state="loading" title="Loading connections…" />
{:else if view !== null}
  <ListDetail
    items={services}
    key={(row) => row.id}
    label="Connected services"
    matches={(row, query) => `${row.name} ${row.category}`.toLowerCase().includes(query)}
    searchLabel="Search connections"
    storageKey="connections-services"
    bind:selectedId
  >
    {#snippet row(service)}
      <span class="logo" aria-hidden="true">{service.name[0]}</span>
      <span class="row-copy">
        <span class="row-name">{service.name}</span>
        <span class="row-status">{service.status}</span>
      </span>
    {/snippet}
    {#snippet empty()}
      <div class="empty-services">
        <p>Nothing is connected yet. Connect a service so Raiker can read or act on it, always under your permissions.</p>
        <button type="button" class="btn btn-primary" onclick={() => (adding = true)}>
          <Icon name="plus" size="sm" /> Add connection
        </button>
      </div>
    {/snippet}
    {#snippet detail(service)}
      {#if service.connector === null}
        <GitHubConnection />
      {:else}
        {@const connector = service.connector}
        {@const extension = extensionFor(connector)}
        {@const pending = pendingFor(extension)}
        <div class="detail">
          <header class="detail-head">
            <span class="logo" aria-hidden="true">{connector.display_name[0]}</span>
            <div>
              <h2>{connector.display_name}</h2>
              <p>{connector.description}</p>
            </div>
          </header>

          {#if extension !== null}
            <LifecycleTrack steps={connectionSteps(extension)} blockedReason={extension.blocked_reason} />
            <p class="reason" class:blocked={extension.blocked_reason !== null}>
              {connectionBlockedCopy(extension)}
            </p>
          {/if}
          {#if pending > 0}
            <p class="pending-approval" role="status">
              {pending === 1 ? "One call is" : `${pending} calls are`}
              waiting on your decision before this connection can act.
              <a href="#/approvals">Review the decision queue</a>
            </p>
          {/if}

          <section>
            <h3>Account</h3>
            {#if connector.auth_status !== "connected"}
              <p>
                {connector.auth_type === "oauth2"
                  ? "Paste an OAuth access token. It is encrypted for this profile and never shown again."
                  : "Paste an API key. It is encrypted for this profile and never shown again."}
              </p>
              <label class="field-label" for="credential">
                {connector.auth_type === "oauth2" ? "OAuth access token" : "API key"}
              </label>
              <input id="credential" class="input credential" type="password" bind:value={secret} autocomplete="off" />
              <button class="btn btn-primary" onclick={() => authenticate(connector)} disabled={busy || !secret}>
                Connect
              </button>
            {:else}
              <p><Icon name="check" size="sm" /> Account connected. The credential is stored; its value is never shown.</p>
            {/if}
          </section>

          <section>
            <h3>What it can do</h3>
            {#if connector.operations.length > 0}
              <ul class="operations">
                {#each connector.operations as operation (operation.operation_id)}
                  <li>
                    <span class:write={operation.requires_confirmation} class="method">{operation.method}</span>
                    <span class="operation-copy">
                      <strong>{operation.description || operation.operation_id}</strong>
                      <small>{operation.path}</small>
                    </span>
                    {#if operation.requires_confirmation}<span class="pill">Asks first</span>{/if}
                  </li>
                {/each}
              </ul>
            {:else}
              <p>No operations are registered yet. Import its manifest to add them.</p>
            {/if}
          </section>

          <section>
            <h3>This session</h3>
            <p>
              {connector.enabled ? "Available in this session." : "Not available in this session."}
              Reads follow your permissions; a write shows its request and asks before it is sent.
            </p>
            <button
              class="btn"
              onclick={() => toggle(connector)}
              disabled={busy || connector.auth_status !== "connected"}
            >{connector.enabled ? "Turn off for this session" : "Turn on for this session"}</button>
          </section>

          {#if extension !== null}
            <details class="technical">
              <summary>Technical details</summary>
              <dl class="property-list">
                {#if extension.capability}<dt>Capability</dt><dd class="mono">{extension.capability}</dd>{/if}
                {#if extension.gate_state}<dt>Gate state</dt><dd>{extension.gate_state}</dd>{/if}
                {#if extension.decision_mode}<dt>Decision mode</dt><dd>{extension.decision_mode}</dd>{/if}
                {#if extension.egress_host}
                  <dt>Host</dt>
                  <dd><span class="mono">{extension.egress_host}</span></dd>
                {/if}
                {#if extension.last_activity_at}
                  <dt>Last activity</dt>
                  <dd title={extension.last_activity_at}>{relativeTime(extension.last_activity_at)}</dd>
                {/if}
              </dl>
            </details>
          {/if}

          <div class="danger-zone">
            <button class="btn btn-danger" onclick={() => uninstall(connector)} disabled={busy}>
              Disconnect and remove its credential
            </button>
          </div>
        </div>
      {/if}
    {/snippet}
  </ListDetail>
{/if}

{#if adding}
  <AddDialog
    title="Add connection"
    options={catalogue}
    bind:chosen
    searchLabel="Search services"
    onclose={closeAdd}
  >
    {#snippet steps(option)}
      {#if option.id === GITHUB_ID}
        <GitHubConnection />
      {:else}
        {@const connector = connectorById(option.id)}
        {#if connector !== null}
          <p>{connector.description}</p>
          <p class="note">Talks to <span class="mono">{connector.host}</span>. Connecting stores a credential and grants nothing until Permissions allows it.</p>
          {#if error}<div class="notice notice-danger" role="alert">{error}</div>{/if}
          {#if !connector.installed}
            <div class="step-actions">
              <button class="btn btn-primary" onclick={() => install(connector)} disabled={busy}>
                {busy ? "Adding…" : `Add ${connector.display_name}`}
              </button>
              <button class="btn btn-ghost" onclick={() => openMcp(connector)} disabled={busy}>
                Connect through an MCP server instead
              </button>
            </div>
          {:else if connector.auth_status !== "connected"}
            <label class="field-label" for="add-credential">
              {connector.auth_type === "oauth2" ? "OAuth access token" : "API key"}
            </label>
            <input id="add-credential" class="input credential" type="password" bind:value={secret} autocomplete="off" />
            <div class="step-actions">
              <button class="btn btn-primary" onclick={() => authenticate(connector)} disabled={busy || !secret}>
                Connect
              </button>
              <button class="btn btn-ghost" onclick={() => finishAdding(connector)}>Later</button>
            </div>
          {:else}
            <div class="notice notice-ok"><Icon name="check" size="sm" /> {connector.display_name} is connected.</div>
            <div class="step-actions">
              <button class="btn btn-primary" onclick={() => finishAdding(connector)}>Done</button>
            </div>
          {/if}

          {#if mcpOpen}
            <section class="mcp-steps" aria-label="Connect through an MCP server">
              <h3>Connect through an MCP server</h3>
              <p class="note">Raiker stores only a token's environment-variable name, never its value.</p>
              <label class="field-label" for="mcp-name">Connection name</label>
              <input id="mcp-name" class="input credential" bind:value={mcpName} />
              <label><input type="radio" name="mcp-transport" bind:group={mcpTransport} value="local" /> Local starter server</label>
              <label><input type="radio" name="mcp-transport" bind:group={mcpTransport} value="remote" /> Remote MCP server</label>
              {#if mcpTransport === "remote"}
                <label class="field-label" for="mcp-endpoint">MCP endpoint URL</label>
                <input id="mcp-endpoint" class="input credential" type="url" bind:value={endpointUrl} placeholder="https://mcp.example.com" />
                {#if endpointUrl.trim()}<p class="note">{networkClassLabel(endpointUrl)}.</p>{/if}
                <label class="field-label" for="mcp-token-ref">Token environment variable</label>
                <input id="mcp-token-ref" class="input credential" bind:value={authRef} placeholder="MY_MCP_TOKEN" autocomplete="off" />
              {/if}
              {#if mcpResult}<div class="notice notice-ok">{mcpResult}</div>{/if}
              <div class="step-actions">
                <button
                  class="btn btn-primary"
                  onclick={connectViaMcp}
                  disabled={busy || !mcpName.trim() || (mcpTransport === "remote" && !endpointUrl.trim())}
                >{busy ? "Connecting…" : "Connect through MCP"}</button>
              </div>
            </section>
          {/if}
        {/if}
      {/if}
    {/snippet}
  </AddDialog>
{/if}

{#if showManifest}
  <div class="overlay" role="presentation" onclick={(e) => e.target === e.currentTarget && (showManifest = false)}>
    <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="manifest-title" tabindex="-1">
      <button class="close" aria-label="Close" onclick={() => (showManifest = false)}><Icon name="x" size="md" /></button>
      <h2 id="manifest-title">Import a connection manifest</h2>
      <p>OpenAPI 2/3 and ai-plugin.json metadata are checked and compiled by Raiker before anything is registered.</p>
      <label class="field-label" for="connector-id">Connection</label>
      <select id="connector-id" class="select wide" bind:value={manifestConnectorId}>
        <option value="">Choose a connection</option>
        {#each services.filter((row) => row.connector !== null) as row (row.id)}
          <option value={row.id}>{row.name}</option>
        {/each}
      </select>
      <label class="field-label" for="manifest-json">Manifest JSON</label>
      <textarea id="manifest-json" class="textarea manifest" bind:value={manifestText}></textarea>
      {#if manifestResult}<div class="notice">{manifestResult}</div>{/if}
      <div class="step-actions">
        <button class="btn btn-primary" onclick={registerManifest} disabled={!manifestConnectorId || !manifestText}>
          Check and register
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .services-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
  }
  .head-actions,
  .step-actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
  }
  .attention-row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-3);
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--warn-border, var(--border));
    border-radius: var(--r-sm);
    background: var(--sunken);
    color: var(--text-1);
    font-size: var(--text-sm);
  }
  .attention-row span {
    flex: 1;
  }
  .logo {
    display: grid;
    place-items: center;
    flex: 0 0 36px;
    height: 36px;
    border: 1px solid var(--accent-border);
    border-radius: 8px;
    color: var(--accent);
    background: var(--accent-soft);
    font-weight: 800;
  }
  .row-copy {
    display: grid;
    min-width: 0;
  }
  .row-name {
    font-weight: 650;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .row-status {
    color: var(--text-3);
    font-size: var(--text-sm);
  }
  .empty-services {
    display: grid;
    justify-items: start;
    gap: var(--space-3);
    padding: var(--space-4) 0;
    color: var(--text-2);
  }
  .empty-services p {
    margin: 0;
    max-width: 34rem;
  }
  .detail {
    display: grid;
    gap: var(--space-3);
  }
  .detail-head {
    display: flex;
    gap: var(--space-3);
  }
  .detail-head h2 {
    margin: 0;
  }
  .detail-head p,
  section p {
    margin: 0.2rem 0 0;
    color: var(--text-2);
  }
  section {
    padding-top: var(--space-3);
    border-top: 1px solid var(--border);
  }
  section h3 {
    margin: 0 0 var(--space-2);
    font-size: var(--text-sm);
  }
  .reason {
    margin: 0;
    color: var(--text-2);
    font-size: var(--text-sm);
  }
  .reason.blocked {
    color: var(--text-1);
  }
  .pending-approval {
    margin: 0;
    font-size: var(--text-sm);
  }
  .credential,
  .wide {
    width: 100%;
    margin-bottom: 0.65rem;
  }
  .operations {
    list-style: none;
    margin: 0.5rem 0 0;
    padding: 0;
    display: grid;
    gap: 0.45rem;
  }
  .operations li {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: 0.65rem;
    padding: 0.55rem;
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
  }
  .method {
    min-width: 3rem;
    color: var(--ok);
    font: 700 var(--text-2xs) var(--font-mono);
  }
  .method.write {
    color: var(--warn);
  }
  .operation-copy strong,
  .operation-copy small {
    display: block;
  }
  .operation-copy small {
    margin-top: 0.15rem;
    color: var(--text-3);
    font: var(--text-2xs) var(--font-mono);
  }
  .technical summary {
    cursor: pointer;
    color: var(--text-2);
    font-size: var(--text-sm);
  }
  .danger-zone {
    padding-top: var(--space-3);
    border-top: 1px solid var(--danger-border);
  }
  .mcp-steps {
    display: grid;
    gap: var(--space-2);
  }
  .note {
    margin: 0;
    color: var(--text-2);
    font-size: var(--text-sm);
  }
  .overlay {
    position: fixed;
    inset: 0;
    z-index: var(--z-scrim);
    display: grid;
    place-items: center;
    padding: var(--space-4);
    background: var(--overlay);
  }
  .dialog {
    position: relative;
    width: min(640px, 100%);
    max-height: 90vh;
    overflow: auto;
    padding: var(--space-5);
    border: 1px solid var(--border-strong);
    border-radius: var(--r-lg);
    background: var(--raised);
    box-shadow: var(--shadow-2);
  }
  .dialog > p {
    color: var(--text-2);
  }
  .close {
    position: absolute;
    right: 0.6rem;
    top: 0.6rem;
    display: grid;
    place-items: center;
    border: 0;
    background: transparent;
    color: var(--text-2);
    padding: 0.45rem;
    cursor: pointer;
  }
  .manifest {
    width: 100%;
    min-height: 200px;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
  }
</style>
