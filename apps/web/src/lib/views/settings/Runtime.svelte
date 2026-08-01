<script lang="ts">
  /**
   * Runtime configuration.
   *
   * Raiker used to ship five runtime modes — development preview, two
   * single-user modes, a multi-user mode and a hosted mode — and this panel
   * was where you picked one. Picking never told anyone anything: what the
   * agent may do is decided by each capability's own gate, its threat-model
   * acknowledgement, its human confirmation and whether a real executor is
   * registered. The mode was a fifth answer that could only say "not yet" to
   * work the other four had already authorised, and choosing wrong left a
   * correctly-configured install refusing to run.
   *
   * There is one runtime now and it does all of it, so this panel states what
   * is running instead of asking. The one runtime-level decision that remains
   * is binary and stays here in the danger zone: whether the runtime accepts
   * new executions at all.
   */
  import { onMount } from "svelte";
  import Icon from "../../components/Icon.svelte";
  import StepUpDialog from "../../components/StepUpDialog.svelte";
  import type { StepUpValues } from "../../components/StepUpDialog.svelte";
  import { api, ApiError } from "../../api";
  import type { ExecutionEnvironmentsView, RuntimeMode } from "../../apiTypes";
  import { explainReasonCode } from "../../reasonCodes";

  let { principal = "—" }: { principal?: string } = $props();
  let mode = $state<RuntimeMode | null>(null);
  let loadError = $state<string | null>(null);
  let notice = $state<{ kind: "ok" | "error"; text: string } | null>(null);
  type Pending = { kind: "enable" } | { kind: "disable" };
  let pending = $state<Pending | null>(null);
  let busy = $state(false);
  let dialogError = $state<string | null>(null);
  let environments = $state<ExecutionEnvironmentsView | null>(null);
  let environmentKind = $state<"ssh" | "daytona">("ssh");
  let environmentName = $state("");
  let host = $state("");
  let remoteUser = $state("");
  let credentialEnv = $state("RAIKER_SSH_IDENTITY_FILE");
  let sandboxId = $state("");
  let maxCost = $state(10);

  // The runtime is on unless the owner switched it off. An unreadable state is
  // never reported as running — the card says it could not be read instead.
  const running = $derived(mode !== null && mode.status === "active");

  async function load() {
    loadError = null;
    try {
      mode = await api.runtimeMode();
      try { environments = await api.executionEnvironments(); } catch { environments = null; }
    } catch (e) {
      mode = null;
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }
  async function saveEnvironment() {
    busy = true; notice = null;
    try {
      const config = environmentKind === "ssh"
        ? { host, user: remoteUser, credential_env: credentialEnv, max_runtime_seconds: 300 }
        : { sandbox_id: sandboxId, api_key_env: credentialEnv, max_cost: maxCost, max_runtime_seconds: 300 };
      await api.configureExecutionEnvironment({ kind: environmentKind, name: environmentName, config, enabled: true });
      notice = { kind: "ok", text: `${environmentKind === "ssh" ? "SSH" : "Daytona"} environment saved. Credential values remain in the named environment variable.` };
      environmentName = ""; host = ""; remoteUser = ""; sandboxId = "";
      await load();
    } catch { notice = { kind: "error", text: "The execution profile could not be saved." }; }
    finally { busy = false; }
  }
  async function selectEnvironment(profileId: string) {
    try { await api.selectExecutionEnvironment(profileId); await load(); }
    catch { notice = { kind: "error", text: "That environment is not ready. Complete its configuration and credential reference first." }; }
  }

  async function confirm(values: StepUpValues) {
    if (!pending) return;
    busy = true;
    dialogError = null;
    try {
      if (pending.kind === "enable") await api.activateRuntimeMode("raiker_runtime", values.reason);
      else await api.disableRuntimeMode(values.reason);
      notice = {
        kind: "ok",
        text: pending.kind === "enable" ? "The agent runtime is accepting work again." : "Agent runtime disabled.",
      };
      pending = null;
      await load();
    } catch (e) {
      const explained = e instanceof ApiError ? explainReasonCode(e.reasonCode) : null;
      dialogError = explained
        ? `${explained.plain} ${explained.remediation ?? ""}`
        : "The change was rejected by the runtime.";
    } finally {
      busy = false;
    }
  }
  onMount(load);
</script>

<header class="section-heading">
  <h2>Runtime configuration</h2>
  <p>Raiker runs one governed runtime. There is nothing to select — every capability is decided by its own permission, not by a mode.</p>
</header>

{#if notice}<p class="notice {notice.kind === 'ok' ? 'notice-ok' : 'notice-danger'}" role="status">{notice.text}</p>{/if}

<section class="settings-card">
  <div class="card-heading">
    <span class="eyebrow">Agent runtime</span>
    <h3>
      Raiker runtime
      {#if mode}<span class="status" class:stopped={!running}>· {running ? "Accepting work" : "Disabled"}</span>{/if}
    </h3>
  </div>
  {#if loadError}
    <p class="error" role="alert">{loadError}</p>
  {:else if mode === null}
    <p class="description" role="status">Loading…</p>
  {:else}
    <p class="description">
      {running
        ? "New executions run under this runtime. What each one may actually do is decided by Permissions, project boundaries, and your approvals."
        : "New executions are refused. Work already running continues to its next safe boundary."}
    </p>
    <dl>
      <div><dt>State</dt><dd>{running ? "Accepting new executions" : "Not accepting new executions"}</dd></div>
      <div><dt>Last changed</dt><dd>{mode.activated_at || "Not recorded"}</dd></div>
      <div><dt>Changed by</dt><dd>{mode.activated_by || "Administrator"}</dd></div>
    </dl>
    <div class="actions">
      <a href="#/activity">View change history</a>
      <a class="btn btn-ghost btn-sm" href="#/capabilities"><Icon name="capabilities" size={15} /> Review permissions</a>
    </div>
  {/if}
</section>

<section class="settings-card environment-settings">
  <div class="card-heading"><span class="eyebrow">Execution targets</span><h3>Local, remote, and cloud environments</h3></div>
  <p class="description">Choose where Chat, Build, and scheduled work execute. Remote commands still require the remote/cloud capability gate and a per-command approval. Profiles store credential references, never credential values.</p>
  {#if environments}
    <div class="environment-grid">
      {#each environments.environments as environment}
        <article class:selected={environment.selected}>
          <div><strong>{environment.name}</strong><span>{environment.kind} · {environment.status.replaceAll("_", " ")}</span></div>
          <button class="btn btn-ghost btn-sm" disabled={!environment.available || environment.selected} onclick={() => void selectEnvironment(environment.profile_id)}>{environment.selected ? "Selected" : "Select"}</button>
        </article>
      {/each}
    </div>
  {/if}
  <details>
    <summary>Add SSH or Daytona profile</summary>
    <form class="environment-form" onsubmit={(event) => { event.preventDefault(); void saveEnvironment(); }}>
      <label>Environment type<select bind:value={environmentKind} onchange={() => credentialEnv = environmentKind === "ssh" ? "RAIKER_SSH_IDENTITY_FILE" : "DAYTONA_API_KEY"}><option value="ssh">SSH remote host</option><option value="daytona">Daytona cloud sandbox</option></select></label>
      <label>Display name<input bind:value={environmentName} required placeholder="Build host" /></label>
      {#if environmentKind === "ssh"}<label>Host<input bind:value={host} required placeholder="build.example.com" /></label><label>Remote user<input bind:value={remoteUser} required placeholder="raiker" /></label>{:else}<label>Sandbox ID<input bind:value={sandboxId} required placeholder="sandbox-id" /></label><label>Maximum run cost (USD)<input type="number" min="0.01" step="0.01" bind:value={maxCost} /></label>{/if}
      <label>Credential environment variable<input bind:value={credentialEnv} required pattern={"[A-Z][A-Z0-9_]{2,127}"} /></label>
      <small>{environmentKind === "ssh" ? "The variable must contain the path to an OpenSSH private key; known-host verification stays strict." : "The variable must contain the Daytona API key; the configured budget is checked before execution."}</small>
      <button class="btn btn-primary" disabled={busy}>Save environment</button>
    </form>
  </details>
</section>

<section class="danger-zone">
  <h3>Danger zone</h3>
  {#if running}
    <h4>Disable agent runtime</h4>
    <p>Prevent Raiker from accepting new executions. Active work continues to its next safe boundary.</p>
    <button class="btn btn-danger" type="button" onclick={() => (pending = { kind: "disable" })}>Disable agent runtime</button>
  {:else}
    <h4>Enable agent runtime</h4>
    <p>Let Raiker accept new executions again. Every capability keeps the permission it already had.</p>
    <button class="btn btn-primary" type="button" onclick={() => (pending = { kind: "enable" })}>Enable agent runtime</button>
  {/if}
</section>

{#if pending}
  <StepUpDialog
    title={pending.kind === "enable" ? "Enable agent runtime" : "Disable agent runtime"}
    {principal}
    requireToken={false}
    requireThreatAck={false}
    {busy}
    error={dialogError}
    onConfirm={confirm}
    onCancel={() => { pending = null; dialogError = null; }}
  />
{/if}

<style>
  .section-heading { margin-bottom: var(--space-4); } .section-heading h2, h3, h4 { margin: 0; } .section-heading p, .description, .danger-zone p { color: var(--text-2); }
  .settings-card, .danger-zone { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-lg); padding: clamp(1.25rem, 3vw, 2rem); }
  .environment-settings { margin-top:var(--space-5); } .environment-grid { display:grid; gap:var(--space-2); margin:var(--space-4) 0; } .environment-grid article { display:flex; align-items:center; justify-content:space-between; gap:var(--space-3); padding:var(--space-3); border:1px solid var(--border); border-radius:var(--r-md); } .environment-grid article.selected { border-color:var(--accent-border); background:var(--accent-soft); } .environment-grid article div { display:grid; gap:.2rem; } .environment-grid article span { color:var(--text-3); font-size:.75rem; text-transform:capitalize; } details { margin-top:var(--space-4); } summary { cursor:pointer; font-weight:650; } .environment-form { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:var(--space-3); margin-top:var(--space-3); } .environment-form label { display:grid; gap:.35rem; color:var(--text-2); font-size:.78rem; } .environment-form input,.environment-form select { min-height:40px; padding:0 .65rem; border:1px solid var(--border); border-radius:var(--r-md); background:var(--sunken); color:var(--text-1); } .environment-form small,.environment-form button { grid-column:1/-1; }
  .status { color: var(--ok); font-size: .85rem; } .status.stopped { color: var(--warn); }
  .eyebrow { color: var(--accent); text-transform: uppercase; letter-spacing: .08em; font-size: .72rem; font-weight: 700; }
  dl { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-3); padding: var(--space-4) 0; border-block: 1px solid var(--border); } dl div { display: grid; gap: .2rem; } dt { color: var(--text-3); font-size: .75rem; } dd { margin: 0; }
  .actions { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin-top: var(--space-5); }
  .danger-zone { margin-top: var(--space-5); border-color: color-mix(in srgb, var(--danger) 40%, var(--border)); } .danger-zone h4 { margin-top: var(--space-4); } .error { color: var(--danger); }
  @media (max-width: 40rem) { dl { grid-template-columns: 1fr; } .actions { align-items: stretch; flex-direction: column; } }
</style>
