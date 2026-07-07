<script lang="ts">
  import { onMount } from "svelte";
  import Icon from "../components/Icon.svelte";
  import StepUpDialog from "../components/StepUpDialog.svelte";
  import type { StepUpValues } from "../components/StepUpDialog.svelte";
  import { api, ApiError } from "../api";
  import type { CapabilityGate } from "../apiTypes";
  import {
    canDisable,
    canEnable,
    capabilityDescription,
    capabilityLabel,
    DECISION_MODE_COPY,
    DECISION_MODES,
    enableableTargets,
    groupByPhase,
    isDecisionMode,
    requiresStepUpToken,
    type DecisionMode,
  } from "../capabilityModel";
  import { explainReasonCode } from "../reasonCodes";

  let { principal = "—" }: { principal?: string } = $props();

  let gates = $state<CapabilityGate[] | null>(null);
  let loadError = $state<string | null>(null);
  let search = $state("");
  let expanded = $state<string | null>(null);
  let notice = $state<{ kind: "ok" | "error"; text: string } | null>(null);

  // The per-capability decision mode is the primary control here. It arrives inline
  // on each gate (gate.decision_mode) from the single /api/capability-gates read, so
  // there is no per-capability fan-out. Local overrides after a successful set are
  // kept here so the segmented control updates without a full reload.
  let modeOverrides = $state<Record<string, DecisionMode>>({});
  let modeBusyCap = $state<string | null>(null);

  function modeFor(gate: CapabilityGate): DecisionMode | "unknown" {
    const override = modeOverrides[gate.capability];
    if (override !== undefined) return override;
    return isDecisionMode(gate.decision_mode) ? gate.decision_mode : "unknown";
  }

  // The pending mutation awaiting step-up confirmation.
  type Pending =
    | { kind: "enable"; capability: string; target: string; requireToken: boolean }
    | { kind: "disable_cap"; capability: string }
    | { kind: "set_mode"; capability: string; mode: DecisionMode };
  let pending = $state<Pending | null>(null);
  let busy = $state(false);
  let dialogError = $state<string | null>(null);

  async function load() {
    loadError = null;
    try {
      gates = await api.capabilityGates();
      modeOverrides = {};
    } catch (e) {
      gates = null;
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }

  const filtered = $derived.by(() => {
    if (gates === null) return [];
    const q = search.trim().toLowerCase();
    const matches = q
      ? gates.filter(
          (g) =>
            g.capability.toLowerCase().includes(q) ||
            capabilityLabel(g.capability).toLowerCase().includes(q),
        )
      : gates;
    return groupByPhase(matches);
  });

  function toggleExpand(capability: string) {
    expanded = expanded === capability ? null : capability;
  }

  async function setMode(gate: CapabilityGate, mode: DecisionMode) {
    const capability = gate.capability;
    if (modeFor(gate) === mode || modeBusyCap !== null) return;
    // Tightening modes (ask/deny) apply immediately; loosening modes (allow/auto)
    // require the step-up window with an explicit reason.
    if (mode === "allow" || mode === "auto") {
      pending = { kind: "set_mode", capability, mode };
      dialogError = null;
      return;
    }
    modeBusyCap = capability;
    notice = null;
    try {
      await api.setCapabilityDecisionMode(capability, mode, "set via web UI");
      modeOverrides = { ...modeOverrides, [capability]: mode };
      notice = {
        kind: "ok",
        text: `${capabilityLabel(capability)} is now set to “${DECISION_MODE_COPY[mode].label}”.`,
      };
    } catch (e) {
      const explained = e instanceof ApiError ? explainReasonCode(e.reasonCode) : null;
      notice = {
        kind: "error",
        text: explained ? `${explained.plain} ${explained.remediation ?? ""}` : "The change was rejected.",
      };
    } finally {
      modeBusyCap = null;
    }
  }

  function startEnable(gate: CapabilityGate) {
    const targets = enableableTargets(gate);
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
          title: `Enable ${capabilityLabel(pending.capability)}`,
          requireToken: pending.requireToken,
          requireThreatAck: pending.requireToken,
        };
      case "disable_cap":
        return {
          title: `Disable ${capabilityLabel(pending.capability)}`,
          requireToken: false,
          requireThreatAck: false,
        };
      case "set_mode":
        return {
          title: `Set ${capabilityLabel(pending.capability)} to “${DECISION_MODE_COPY[pending.mode].label}”`,
          requireToken: false,
          requireThreatAck: false,
        };
    }
  }

  async function confirm(values: StepUpValues) {
    if (pending === null) return;
    busy = true;
    dialogError = null;
    try {
      const p = pending;
      await runMutation(p, values);
      notice = { kind: "ok", text: describeSuccess(p) };
      pending = null;
      await load();
      // load() clears overrides; re-apply the just-set mode so the control reflects it
      // even if the persisted read lags (the set itself is authoritative).
      if (p.kind === "set_mode") {
        modeOverrides = { [p.capability]: p.mode };
      }
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
    } else {
      await api.setCapabilityDecisionMode(p.capability, p.mode, values.reason);
    }
  }

  function describeSuccess(p: Pending): string {
    if (p.kind === "enable") return `Enabled ${capabilityLabel(p.capability)}.`;
    if (p.kind === "disable_cap") return `Disabled ${capabilityLabel(p.capability)}.`;
    return `${capabilityLabel(p.capability)} is now set to “${DECISION_MODE_COPY[p.mode].label}”.`;
  }

  onMount(load);
</script>

<p class="page-lead">
  Choose how the agent should handle each thing it can do. For every capability, pick whether an
  AI-proposed action should <strong>ask you first</strong> (the default), be <strong>allowed</strong>
  without prompting, run <strong>automatically</strong>, or always be <strong>denied</strong>. Every
  choice is enforced server-side — this page adds no authority of its own.
</p>

{#if notice}
  <p class="notice {notice.kind === 'ok' ? 'notice-ok' : 'notice-danger'}" role="status">{notice.text}</p>
{/if}

<div class="toolbar">
  <div class="search">
    <Icon name="search" size={15} />
    <label class="sr-only" for="cap-search">Search capabilities</label>
    <input
      id="cap-search"
      class="search-input"
      type="search"
      placeholder="Search capabilities…"
      bind:value={search}
    />
  </div>
  <button type="button" class="btn btn-ghost btn-sm" onclick={load} aria-label="Refresh capabilities">
    <Icon name="refresh" size={15} />
    Refresh
  </button>
</div>

{#if loadError}
  <p class="error" role="alert">Unavailable: {loadError}</p>
{:else if gates === null}
  <p class="loading">Loading…</p>
{:else}
  {#each filtered as group (group.phase)}
    <div class="cap-list">
      {#each group.gates as gate (gate.capability)}
        {@const isOpen = expanded === gate.capability}
        {@const mode = modeFor(gate)}
        <div class="cap card" class:open={isOpen}>
          <div class="cap-row">
            <button
              type="button"
              class="cap-toggle"
              aria-expanded={isOpen}
              onclick={() => toggleExpand(gate.capability)}
            >
              <span class="chev" aria-hidden="true">
                <Icon name={isOpen ? "chevron-down" : "chevron-right"} size={15} />
              </span>
              <span class="cap-name">
                <span class="cap-label">{capabilityLabel(gate.capability)}</span>
              </span>
            </button>

            <div
              class="mode-seg"
              role="group"
              aria-label={`Decision mode for ${capabilityLabel(gate.capability)}`}
            >
              {#each DECISION_MODES as m (m)}
                <button
                  type="button"
                  class="mode-btn"
                  class:selected={mode === m}
                  title={DECISION_MODE_COPY[m].hint}
                  aria-pressed={mode === m}
                  onclick={() => setMode(gate, m)}
                  disabled={modeBusyCap === gate.capability}
                >
                  {DECISION_MODE_COPY[m].label}
                </button>
              {/each}
            </div>
          </div>

          {#if isOpen}
            <div class="cap-detail">
              <p class="cap-desc">{capabilityDescription(gate.capability)}</p>
              {#if isDecisionMode(mode)}
                <p class="mode-hint">{DECISION_MODE_COPY[mode].hint}</p>
              {/if}

              <div class="cap-actions">
                {#if canEnable(gate)}
                  <button type="button" class="btn btn-soft btn-sm" onclick={() => startEnable(gate)}>
                    Turn on
                  </button>
                {/if}
                {#if canDisable(gate)}
                  <button
                    type="button"
                    class="btn btn-danger btn-sm"
                    onclick={() => {
                      pending = { kind: "disable_cap", capability: gate.capability };
                      dialogError = null;
                    }}
                  >
                    Turn off
                  </button>
                {/if}
                {#if !gate.can_current_principal_change}
                  <span class="muted">On/off changes are not permitted for your principal.</span>
                {/if}
              </div>
            </div>
          {/if}
        </div>
      {/each}
    </div>
  {/each}
{/if}

{#if pending !== null}
  {@const p = stepUpProps()}
  {#if p}
    <StepUpDialog
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
  .toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
  }
  .search {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    background: var(--surface);
    border: 1px solid var(--border-strong);
    border-radius: var(--r-pill);
    padding: 0.3rem 0.8rem;
    color: var(--text-3);
    max-width: 22rem;
    flex: 1;
  }
  .search:focus-within {
    border-color: var(--focus-ring);
  }
  .search-input {
    font: inherit;
    font-size: 0.88rem;
    border: none;
    background: transparent;
    color: var(--text-1);
    width: 100%;
  }
  .search-input:focus {
    outline: none;
  }
  .cap-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    margin-bottom: var(--space-2);
  }
  .cap {
    padding: 0;
    overflow: hidden;
  }
  .cap.open {
    border-color: var(--accent-border);
  }
  .cap-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.5rem 0.9rem;
    flex-wrap: wrap;
  }
  .cap-toggle {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex: 1;
    min-width: 12rem;
    font: inherit;
    text-align: left;
    background: transparent;
    border: none;
    padding: 0.15rem 0;
    cursor: pointer;
    color: var(--text-1);
  }
  .cap-toggle:hover {
    color: var(--accent);
  }
  .chev {
    color: var(--text-3);
    display: grid;
    place-items: center;
  }
  .cap-name {
    display: flex;
    align-items: baseline;
    gap: 0.6rem;
    min-width: 0;
    flex-wrap: wrap;
  }
  .cap-label {
    font-weight: 600;
  }
  .mode-seg {
    display: inline-flex;
    gap: 2px;
    background: var(--sunken);
    border: 1px solid var(--border);
    border-radius: var(--r-pill);
    padding: 3px;
    flex-shrink: 0;
  }
  .mode-btn {
    font: inherit;
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--text-2);
    background: transparent;
    border: none;
    border-radius: var(--r-pill);
    padding: 0.2rem 0.7rem;
    cursor: pointer;
  }
  .mode-btn:hover:not(:disabled):not(.selected) {
    color: var(--text-1);
  }
  .mode-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .mode-btn.selected {
    background: var(--accent-soft);
    color: var(--accent);
    box-shadow: var(--shadow-1);
  }
  .cap-detail {
    border-top: 1px solid var(--border);
    padding: var(--space-3) var(--space-4) var(--space-4);
    background: var(--sunken);
  }
  .cap-desc {
    font-size: 0.88rem;
    color: var(--text-2);
    margin: 0 0 0.4rem;
  }
  .mode-hint {
    font-size: 0.8rem;
    color: var(--text-3);
    margin: 0 0 var(--space-3);
  }
  .cap-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }
  .muted {
    color: var(--text-3);
    font-size: 0.8rem;
  }
  .error {
    color: var(--danger);
  }
  .loading {
    color: var(--text-2);
    font-size: 0.84rem;
  }
</style>
