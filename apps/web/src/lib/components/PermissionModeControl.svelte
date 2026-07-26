<script lang="ts">
  import { onMount } from "svelte";
  import { api } from "../api";
  import type { CapabilityGate } from "../apiTypes";

  type ComposerMode = "ask" | "safe_auto" | "custom";
  let mode = $state<ComposerMode>("ask");
  let gates = $state<CapabilityGate[]>([]);
  let busy = $state(false);
  let error = $state<string | null>(null);

  onMount(async () => {
    try {
      gates = await api.capabilityGates();
      if (gates.length > 0 && gates.every((gate) => gate.decision_mode === "auto")) mode = "safe_auto";
      else if (new Set(gates.map((gate) => gate.decision_mode)).size > 1) mode = "custom";
    } catch { error = "Permissions unavailable"; }
  });

  async function setMode(next: ComposerMode) {
    if (next === "custom") { window.location.hash = "#/capabilities"; return; }
    if (busy) return;
    busy = true; error = null;
    try {
      for (const gate of gates) {
        await api.setCapabilityDecisionMode(gate.capability, next === "ask" ? "ask" : "auto", "chat composer global mode");
      }
      mode = next;
    } catch { error = "Permission change was not accepted."; }
    finally { busy = false; }
  }
</script>

<div class="permission-control">
  <select aria-label="Global permissions" value={mode} disabled={busy} onchange={(event) => void setMode((event.currentTarget as HTMLSelectElement).value as ComposerMode)}>
    <option value="ask">Ask every time</option>
    <option value="safe_auto">Approve safe actions</option>
    <option value="custom">Custom permissions…</option>
  </select>
  {#if error}<span role="status">{error}</span>{/if}
</div>

<style>
  .permission-control { display:flex; align-items:center; gap:.35rem; }
  select { border:none; background:transparent; color:var(--text-2); font:inherit; font-size:.78rem; font-weight:600; padding:.25rem .35rem; border-radius:var(--r-md); }
  select:hover:not(:disabled) { background:var(--neutral-soft); }
  span { color:var(--danger, #b3292f); font-size:.74rem; }
</style>
