<script lang="ts">
  import { onMount } from "svelte";
  import StepUpDialog from "../../components/StepUpDialog.svelte";
  import type { StepUpValues } from "../../components/StepUpDialog.svelte";
  import { api, ApiError } from "../../api";
  import type { RuntimeMode } from "../../apiTypes";
  import { humanize } from "../../format";
  import { explainReasonCode } from "../../reasonCodes";
  import { NAV_ITEMS } from "../../nav";

  let {
    settings,
    save,
    principal = "—",
  }: {
    settings: Record<string, unknown>;
    save: (p: Record<string, unknown>) => void;
    principal?: string;
  } = $props();

  const language = $derived((settings["general.language"] as string) ?? "en");
  const region = $derived((settings["general.region"] as string) ?? "");
  const startupRoute = $derived((settings["general.startup_route"] as string) ?? "new-chat");

  // Runtime mode (ported): a governed, server-enforced control that re-confirms
  // the human principal on every change.
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
      if (mode && modeChoice === "") modeChoice = mode.allowed_modes[0] ?? "";
    } catch (e) {
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }

  async function confirm(values: StepUpValues) {
    if (pending === null) return;
    busy = true;
    dialogError = null;
    try {
      if (pending.kind === "activate_mode") {
        await api.activateRuntimeMode(pending.mode_name, values.reason);
        notice = { kind: "ok", text: `Activated runtime mode ${humanize(pending.mode_name)}.` };
      } else {
        await api.disableRuntimeMode(values.reason);
        notice = { kind: "ok", text: "Disabled the runtime mode." };
      }
      pending = null;
      await load();
    } catch (e) {
      const explained = e instanceof ApiError ? explainReasonCode(e.reasonCode) : null;
      dialogError = explained
        ? `${explained.plain}${explained.remediation ? " " + explained.remediation : ""}`
        : "The change was rejected by the runtime.";
    } finally {
      busy = false;
    }
  }

  onMount(load);
</script>

<h2>General</h2>

{#if notice}
  <p class="notice {notice.kind === 'ok' ? 'notice-ok' : 'notice-danger'}" role="status">{notice.text}</p>
{/if}

<section class="card">
  <h3>Regional</h3>
  <label>
    Language
    <select value={language} onchange={(e) => save({ "general.language": e.currentTarget.value })}>
      <option value="en">English</option>
      <option value="hi">हिन्दी</option>
      <option value="es">Español</option>
      <option value="fr">Français</option>
      <option value="de">Deutsch</option>
    </select>
  </label>
  <label>
    Region
    <input
      value={region}
      placeholder="e.g. IN, US"
      onchange={(e) => save({ "general.region": e.currentTarget.value })}
    />
  </label>
  <label>
    Default startup view
    <select value={startupRoute} onchange={(e) => save({ "general.startup_route": e.currentTarget.value })}>
      {#each NAV_ITEMS as item (item.id)}
        <option value={item.id}>{item.label}</option>
      {/each}
    </select>
  </label>
  <p class="sub">Regional and startup preferences are saved to your account.</p>
</section>

<section class="card">
  <h3>Runtime mode</h3>
  {#if loadError}
    <p class="error" role="alert">Unavailable: {loadError}</p>
  {:else if mode === null}
    <p class="sub">Loading…</p>
  {:else}
    <p>
      <strong>{humanize(mode.mode_name)}</strong> · {mode.status}
    </p>
    <div class="controls">
      <select bind:value={modeChoice}>
        {#each mode.allowed_modes as m (m)}
          <option value={m}>{humanize(m)}</option>
        {/each}
      </select>
      <button type="button" class="btn btn-soft" onclick={() => (pending = { kind: "activate_mode", mode_name: modeChoice })} disabled={modeChoice === ""}>
        Activate
      </button>
      <button type="button" class="btn btn-danger" onclick={() => (pending = { kind: "disable_mode" })}>
        Disable
      </button>
    </div>
  {/if}
</section>

{#if pending !== null}
  <StepUpDialog
    title={pending.kind === "activate_mode" ? `Activate ${humanize(pending.mode_name)}` : "Disable runtime mode"}
    {principal}
    requireToken={false}
    requireThreatAck={false}
    {busy}
    error={dialogError}
    onConfirm={confirm}
    onCancel={() => {
      pending = null;
      dialogError = null;
    }}
  />
{/if}

<style>
  label {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    max-width: 20rem;
    margin-top: var(--space-2);
  }
  .controls {
    display: flex;
    gap: var(--space-2);
    margin-top: var(--space-2);
  }
  .sub {
    color: var(--text-2);
  }
  .error {
    color: var(--danger);
  }
</style>
