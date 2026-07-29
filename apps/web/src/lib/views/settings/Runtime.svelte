<script lang="ts">
  import { onMount } from "svelte";
  import StepUpDialog from "../../components/StepUpDialog.svelte";
  import type { StepUpValues } from "../../components/StepUpDialog.svelte";
  import { api, ApiError } from "../../api";
  import type { RuntimeMode } from "../../apiTypes";
  import { humanize } from "../../format";
  import { explainReasonCode } from "../../reasonCodes";

  let { principal = "—" }: { principal?: string } = $props();
  let mode = $state<RuntimeMode | null>(null);
  let modeChoice = $state("");
  let loadError = $state<string | null>(null);
  let notice = $state<{ kind: "ok" | "error"; text: string } | null>(null);
  type Pending = { kind: "activate_mode"; mode_name: string } | { kind: "disable_mode" };
  let pending = $state<Pending | null>(null);
  let busy = $state(false);
  let dialogError = $state<string | null>(null);

  async function load() {
    try {
      mode = await api.runtimeMode();
      if (mode && modeChoice === "") modeChoice = mode.mode_name;
    } catch (e) { loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable"; }
  }
  async function confirm(values: StepUpValues) {
    if (!pending) return;
    busy = true; dialogError = null;
    try {
      if (pending.kind === "activate_mode") await api.activateRuntimeMode(pending.mode_name, values.reason);
      else await api.disableRuntimeMode(values.reason);
      notice = { kind: "ok", text: pending.kind === "activate_mode" ? "Runtime mode changed." : "Agent runtime disabled." };
      pending = null; await load();
    } catch (e) {
      const explained = e instanceof ApiError ? explainReasonCode(e.reasonCode) : null;
      dialogError = explained ? `${explained.plain} ${explained.remediation ?? ""}` : "The change was rejected by the runtime.";
    } finally { busy = false; }
  }
  onMount(load);
</script>

<header class="section-heading"><h2>Runtime configuration</h2><p>Review and change the governed environment used for new agent executions.</p></header>
{#if notice}<p class="notice {notice.kind === 'ok' ? 'notice-ok' : 'notice-danger'}" role="status">{notice.text}</p>{/if}
<section class="settings-card">
  <div class="card-heading"><span class="eyebrow">Current mode</span><h3>{mode ? humanize(mode.mode_name) : "Loading…"} {#if mode}<span class="status">· {mode.status}</span>{/if}</h3></div>
  {#if loadError}<p class="error" role="alert">{loadError}</p>{:else if mode}
    <p class="description">This mode controls which governed capabilities can run. Changes affect new executions; active work is not interrupted.</p>
    <dl><div><dt>System health</dt><dd>Operational</dd></div><div><dt>Last changed</dt><dd>{mode.activated_at || "Not recorded"}</dd></div><div><dt>Changed by</dt><dd>{mode.activated_by || "Administrator"}</dd></div></dl>
    <label><span>New runtime mode</span><select bind:value={modeChoice}>{#each mode.allowed_modes as m (m)}<option value={m}>{humanize(m)}</option>{/each}</select></label>
    <div class="actions"><a href="#/activity">View change history</a><button class="btn btn-primary" type="button" onclick={() => (pending = { kind: "activate_mode", mode_name: modeChoice })} disabled={!modeChoice || modeChoice === mode.mode_name}>Review runtime change</button></div>
  {/if}
</section>
<section class="danger-zone"><h3>Danger zone</h3><h4>Disable agent runtime</h4><p>Prevent Raiker from accepting new executions. Active work continues to its next safe boundary.</p><button class="btn btn-danger" type="button" onclick={() => (pending = { kind: "disable_mode" })}>Disable agent runtime</button></section>

{#if pending}<StepUpDialog title={pending.kind === "activate_mode" ? "Change runtime mode" : "Disable agent runtime"} {principal} requireToken={false} requireThreatAck={false} {busy} error={dialogError} onConfirm={confirm} onCancel={() => { pending = null; dialogError = null; }} />{/if}

<style>
  .section-heading { margin-bottom: var(--space-4); } .section-heading h2, h3, h4 { margin: 0; } .section-heading p, .description, .danger-zone p { color: var(--text-2); }
  .settings-card, .danger-zone { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-lg); padding: clamp(1.25rem, 3vw, 2rem); }
  .status { color: var(--ok); font-size: .85rem; } .eyebrow { color: var(--accent); text-transform: uppercase; letter-spacing: .08em; font-size: .72rem; font-weight: 700; }
  dl { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-3); padding: var(--space-4) 0; border-block: 1px solid var(--border); } dl div { display: grid; gap: .2rem; } dt { color: var(--text-3); font-size: .75rem; } dd { margin: 0; }
  label { display: grid; gap: .4rem; max-width: 34rem; margin-top: var(--space-4); font-weight: 650; } select { min-height: 44px; padding: 0 .8rem; border: 1px solid var(--border-strong); border-radius: var(--r-md); background: var(--surface); color: var(--text-1); }
  .actions { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin-top: var(--space-5); } .danger-zone { margin-top: var(--space-5); border-color: color-mix(in srgb, var(--danger) 40%, var(--border)); } .danger-zone h4 { margin-top: var(--space-4); } .error { color: var(--danger); }
  @media (max-width: 40rem) { dl { grid-template-columns: 1fr; } .actions { align-items: stretch; flex-direction: column; } }
</style>
