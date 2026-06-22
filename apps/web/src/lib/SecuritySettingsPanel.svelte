<script lang="ts">
  import { onMount } from "svelte";
  import Badge from "./Badge.svelte";
  import DisabledCapabilityExplainer from "./DisabledCapabilityExplainer.svelte";
  import StepUpAuthDialog from "./StepUpAuthDialog.svelte";
  import type { StepUpValues } from "./StepUpAuthDialog.svelte";
  import { api, ApiError } from "./api";
  import type { CapabilityGate, RuntimeMode } from "./apiTypes";
  import {
    canDisable,
    canEnable,
    enableableTargets,
    gateBadge,
    groupByPhase,
    isDeferred,
    isDisabled,
    requiresStepUpToken,
  } from "./capabilityModel";
  import { explainReasonCode } from "./reasonCodes";

  let { principal = "—" }: { principal?: string } = $props();

  let gates = $state<CapabilityGate[] | null>(null);
  let mode = $state<RuntimeMode | null>(null);
  let loadError = $state<string | null>(null);
  let notice = $state<{ kind: "ok" | "error"; text: string } | null>(null);
  let modeChoice = $state("");

  // The pending mutation awaiting step-up confirmation.
  type Pending =
    | { kind: "enable"; capability: string; target: string; requireToken: boolean }
    | { kind: "disable_cap"; capability: string }
    | { kind: "activate_mode"; mode_name: string }
    | { kind: "disable_mode" };
  let pending = $state<Pending | null>(null);
  let busy = $state(false);
  let dialogError = $state<string | null>(null);

  const phases = $derived(gates ? groupByPhase(gates) : []);

  async function load() {
    loadError = null;
    try {
      [gates, mode] = await Promise.all([api.capabilityGates(), api.runtimeMode()]);
      if (mode && modeChoice === "") {
        modeChoice = mode.allowed_modes[0] ?? "";
      }
    } catch (e) {
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }

  function startEnable(gate: CapabilityGate) {
    const targets = enableableTargets(gate);
    // Prefer the strongest enabled state the backend offers.
    const target = targets.includes("enabled_runtime") ? "enabled_runtime" : targets[0];
    pending = {
      kind: "enable",
      capability: gate.capability,
      target,
      requireToken: requiresStepUpToken(gate.capability),
    };
    dialogError = null;
  }

  function stepUpProps() {
    if (pending === null) return null;
    switch (pending.kind) {
      case "enable":
        return {
          title: `Enable ${pending.capability}`,
          requireToken: pending.requireToken,
          requireThreatAck: pending.requireToken,
        };
      case "disable_cap":
        return { title: `Disable ${pending.capability}`, requireToken: false, requireThreatAck: false };
      case "activate_mode":
        return { title: `Activate ${pending.mode_name}`, requireToken: false, requireThreatAck: false };
      case "disable_mode":
        return { title: "Disable runtime mode", requireToken: false, requireThreatAck: false };
    }
  }

  async function confirm(values: StepUpValues) {
    if (pending === null) return;
    busy = true;
    dialogError = null;
    try {
      await runMutation(pending, values);
      notice = { kind: "ok", text: describeSuccess(pending) };
      pending = null;
      await load();
    } catch (e) {
      const explained = e instanceof ApiError ? explainReasonCode(e.reasonCode) : null;
      // Keep the dialog open so the user can supply what the backend says is missing.
      dialogError = explained
        ? `${explained.plain}${explained.remediation ? " " + explained.remediation : ""}`
        : "The change was rejected by the runtime.";
    } finally {
      busy = false;
    }
  }

  async function runMutation(p: Pending, values: StepUpValues): Promise<void> {
    if (p.kind === "enable") {
      await api.setCapabilityState(p.capability, {
        target_state: p.target,
        reason: values.reason,
        confirmation_token: values.confirmationToken ?? undefined,
      });
    } else if (p.kind === "disable_cap") {
      await api.disableCapability(p.capability, values.reason);
    } else if (p.kind === "activate_mode") {
      await api.activateRuntimeMode(p.mode_name, values.reason);
    } else {
      await api.disableRuntimeMode(values.reason);
    }
  }

  function describeSuccess(p: Pending): string {
    if (p.kind === "enable") return `Enabled ${p.capability} (${p.target}).`;
    if (p.kind === "disable_cap") return `Disabled ${p.capability}.`;
    if (p.kind === "activate_mode") return `Activated runtime mode ${p.mode_name}.`;
    return "Disabled the runtime mode.";
  }

  onMount(load);
</script>

<h1 id="page-title">Security Settings</h1>
<p class="lead">
  The single, gated path to change runtime modes and capability gates. Every change re-confirms your
  human principal and is enforced server-side — the UI adds no authority of its own.
</p>

{#if notice}
  <p class="notice" class:notice-error={notice.kind === "error"} role="status">{notice.text}</p>
{/if}

<section aria-labelledby="rm-h" class="card">
  <h2 id="rm-h">Runtime Mutations</h2>

  {#if loadError}
    <p class="state-error">Unavailable: {loadError}</p>
  {:else if gates === null || mode === null}
    <p class="state-loading">Loading…</p>
  {:else}
    <div class="mode-row">
      <div>
        <p><span class="k">Runtime mode</span> <code>{mode.mode_name}</code> · {mode.status}</p>
        <p class="sub">Activated by {mode.activated_by || "—"}</p>
      </div>
      <div class="mode-controls">
        <label class="sr-only" for="mode-select">Mode to activate</label>
        <select id="mode-select" bind:value={modeChoice}>
          {#each mode.allowed_modes as m (m)}
            <option value={m}>{m}</option>
          {/each}
        </select>
        <button
          type="button"
          onclick={() => {
            pending = { kind: "activate_mode", mode_name: modeChoice };
            dialogError = null;
          }}
          disabled={modeChoice === ""}
        >
          Activate
        </button>
        <button
          type="button"
          class="danger"
          onclick={() => {
            pending = { kind: "disable_mode" };
            dialogError = null;
          }}
        >
          Disable
        </button>
      </div>
    </div>

    {#each phases as group (group.phase)}
      <h3 class="phase">Phase {group.phase}</h3>
      <table class="gates">
        <thead>
          <tr><th>Capability</th><th>State</th><th>Controls</th></tr>
        </thead>
        <tbody>
          {#each group.gates as gate (gate.capability)}
            <tr>
              <td class="mono">{gate.capability}</td>
              <td><Badge variant={gateBadge(gate)} /></td>
              <td>
                {#if canEnable(gate)}
                  <button type="button" onclick={() => startEnable(gate)}>Enable</button>
                {/if}
                {#if canDisable(gate)}
                  <button
                    type="button"
                    class="danger"
                    onclick={() => {
                      pending = { kind: "disable_cap", capability: gate.capability };
                      dialogError = null;
                    }}
                  >
                    Disable
                  </button>
                {/if}
                {#if !gate.can_current_principal_change}
                  <span class="muted">Not permitted for your principal</span>
                {:else if isDisabled(gate) && (isDeferred(gate) || enableableTargets(gate).length === 0)}
                  <DisabledCapabilityExplainer {gate} />
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/each}
  {/if}
</section>

<section aria-labelledby="ss-h" class="card">
  <h2 id="ss-h">Secret Settings</h2>
  <p class="deferred-notice" role="note">
    <strong>Secret storage is not implemented (deferred).</strong> There is no secret/credential
    store in this local single-user runtime, so there is nothing to enter here.
  </p>
  <p class="sub">
    What is enforced today is read-only redaction and a deny-by-default policy: secret-like strings
    (API keys, bearer tokens, passwords, private keys) are redacted from API responses, event logs,
    and approval previews. This view is informational only — it contains no secret input fields.
  </p>
  <ul class="policy">
    <li>API responses pass through a redaction middleware before leaving the local server.</li>
    <li>Secret-like content in memory/approval payloads is shown as <code>[REDACTED]</code>.</li>
    <li>No capability can read or export raw secrets; sensitive domains stay deferred.</li>
  </ul>
</section>

{#if pending !== null}
  {@const p = stepUpProps()}
  {#if p}
    <StepUpAuthDialog
      title={p.title}
      {principal}
      requireToken={p.requireToken}
      requireThreatAck={p.requireThreatAck}
      {busy}
      error={dialogError}
      onConfirm={confirm}
      onCancel={() => {
        pending = null;
        dialogError = null;
      }}
    />
  {/if}
{/if}

<style>
  .lead {
    max-width: 70ch;
    color: #c2c2c9;
  }
  .card {
    border: 1px solid #2a2a2e;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    background: #101013;
    margin-top: 1rem;
  }
  .card h2 {
    margin-top: 0;
  }
  .mode-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    flex-wrap: wrap;
    border-bottom: 1px solid #1f1f24;
    padding-bottom: 0.75rem;
  }
  .mode-controls {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }
  .phase {
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #8b8b93;
    margin: 0.9rem 0 0.3rem;
  }
  table.gates {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.84rem;
  }
  .gates th,
  .gates td {
    text-align: left;
    padding: 0.3rem 0.5rem;
    border-bottom: 1px solid #1f1f24;
    vertical-align: top;
  }
  .gates th {
    color: #8b8b93;
    font-weight: 600;
  }
  .mono {
    font-family: ui-monospace, monospace;
    color: #b6b6bd;
  }
  button {
    background: #1c2a3a;
    color: #cfe5ff;
    border: 1px solid #2d5a82;
    border-radius: 5px;
    padding: 0.25rem 0.7rem;
    cursor: pointer;
    margin-right: 0.4rem;
  }
  button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  button:focus-visible {
    outline: 2px solid #6aa9ff;
    outline-offset: 1px;
  }
  button.danger {
    background: #2a1212;
    color: #ff8a80;
    border-color: #8a2f2f;
  }
  select {
    background: #0e0e11;
    border: 1px solid #33333a;
    color: #d6d6dc;
    border-radius: 5px;
    padding: 0.25rem 0.4rem;
  }
  .k {
    color: #8b8b93;
    text-transform: uppercase;
    font-size: 0.66rem;
    letter-spacing: 0.05em;
    margin-right: 0.4rem;
  }
  .sub {
    color: #9a9aa2;
    font-size: 0.82rem;
  }
  .muted {
    color: #8b8b93;
    font-size: 0.8rem;
  }
  code {
    font-family: ui-monospace, monospace;
    color: #cfe5ff;
  }
  .notice {
    border: 1px solid #2f7d3a;
    background: #11251a;
    color: #9be0a8;
    border-radius: 8px;
    padding: 0.5rem 0.85rem;
    font-size: 0.86rem;
  }
  .notice-error {
    border-color: #8a2f2f;
    background: #2a1212;
    color: #ef9a9a;
  }
  .deferred-notice {
    border: 1px solid #8a6d1f;
    background: #2a2310;
    color: #e6c66a;
    border-radius: 8px;
    padding: 0.55rem 0.85rem;
    font-size: 0.86rem;
  }
  .policy {
    color: #b6b6bd;
    font-size: 0.84rem;
    margin: 0.5rem 0 0;
    padding-left: 1.1rem;
  }
  .state-error {
    color: #ef9a9a;
  }
  .state-loading {
    color: #9a9aa2;
  }
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }
</style>
