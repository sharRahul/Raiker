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
  import type { RuntimeMode } from "../../apiTypes";
  import { explainReasonCode } from "../../reasonCodes";

  let { principal = "—" }: { principal?: string } = $props();
  let mode = $state<RuntimeMode | null>(null);
  let loadError = $state<string | null>(null);
  let notice = $state<{ kind: "ok" | "error"; text: string } | null>(null);
  type Pending = { kind: "enable" } | { kind: "disable" };
  let pending = $state<Pending | null>(null);
  let busy = $state(false);
  let dialogError = $state<string | null>(null);

  // The runtime is on unless the owner switched it off. An unreadable state is
  // never reported as running — the card says it could not be read instead.
  const running = $derived(mode !== null && mode.status === "active");

  async function load() {
    loadError = null;
    try {
      mode = await api.runtimeMode();
    } catch (e) {
      mode = null;
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
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
  .status { color: var(--ok); font-size: .85rem; } .status.stopped { color: var(--warn); }
  .eyebrow { color: var(--accent); text-transform: uppercase; letter-spacing: .08em; font-size: .72rem; font-weight: 700; }
  dl { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-3); padding: var(--space-4) 0; border-block: 1px solid var(--border); } dl div { display: grid; gap: .2rem; } dt { color: var(--text-3); font-size: .75rem; } dd { margin: 0; }
  .actions { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin-top: var(--space-5); }
  .danger-zone { margin-top: var(--space-5); border-color: color-mix(in srgb, var(--danger) 40%, var(--border)); } .danger-zone h4 { margin-top: var(--space-4); } .error { color: var(--danger); }
  @media (max-width: 40rem) { dl { grid-template-columns: 1fr; } .actions { align-items: stretch; flex-direction: column; } }
</style>
