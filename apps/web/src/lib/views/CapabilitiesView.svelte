<script lang="ts">
  import { onMount } from "svelte";
  import Badge from "../components/Badge.svelte";
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
    explainCapability,
    gateBadge,
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

  // Decision modes are fetched lazily per expanded capability (53 caps × eager
  // fetches would trip the API rate limit for no benefit).
  let decisionModes = $state<Record<string, DecisionMode | "unknown">>({});
  let modeBusy = $state(false);

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

  async function toggleExpand(capability: string) {
    expanded = expanded === capability ? null : capability;
    if (expanded !== null && decisionModes[capability] === undefined) {
      try {
        const result = await api.capabilityDecisionMode(capability);
        decisionModes = {
          ...decisionModes,
          [capability]: isDecisionMode(result.decision_mode) ? result.decision_mode : "unknown",
        };
      } catch {
        decisionModes = { ...decisionModes, [capability]: "unknown" };
      }
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

  async function setMode(capability: string, mode: DecisionMode) {
    if (decisionModes[capability] === mode) return;
    // Tightening modes (ask/deny) apply immediately; loosening modes (allow/auto)
    // require the step-up window with an explicit reason.
    if (mode === "allow" || mode === "auto") {
      pending = { kind: "set_mode", capability, mode };
      dialogError = null;
      return;
    }
    modeBusy = true;
    notice = null;
    try {
      await api.setCapabilityDecisionMode(capability, mode, "set via web UI");
      decisionModes = { ...decisionModes, [capability]: mode };
      notice = { kind: "ok", text: `Decision mode for ${capabilityLabel(capability)} is now “${mode}”.` };
    } catch (e) {
      const explained = e instanceof ApiError ? explainReasonCode(e.reasonCode) : null;
      notice = {
        kind: "error",
        text: explained ? `${explained.plain} ${explained.remediation ?? ""}` : "The change was rejected.",
      };
    } finally {
      modeBusy = false;
    }
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
          title: `Set ${capabilityLabel(pending.capability)} to “${pending.mode}”`,
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
      await runMutation(pending, values);
      notice = { kind: "ok", text: describeSuccess(pending) };
      if (pending.kind === "set_mode") {
        decisionModes = { ...decisionModes, [pending.capability]: pending.mode };
      }
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
    } else {
      await api.setCapabilityDecisionMode(p.capability, p.mode, values.reason);
    }
  }

  function describeSuccess(p: Pending): string {
    if (p.kind === "enable") return `Enabled ${capabilityLabel(p.capability)} (${p.target}).`;
    if (p.kind === "disable_cap") return `Disabled ${capabilityLabel(p.capability)}.`;
    return `Decision mode for ${capabilityLabel(p.capability)} is now “${p.mode}”.`;
  }

  onMount(load);
</script>

<p class="page-lead">
  Everything the agent can do, and the rules for doing it. Each capability has a
  <strong>gate</strong> (on/off) and a <strong>decision mode</strong> — how AI-proposed actions are
  handled: ask you first (default), allow, run automatically, or always deny. Changes are enforced
  server-side; this page adds no authority of its own.
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
    <h2 class="phase-h">Phase {group.phase}</h2>
    <div class="cap-list">
      {#each group.gates as gate (gate.capability)}
        {@const isOpen = expanded === gate.capability}
        {@const explanation = explainCapability(gate)}
        <div class="cap card" class:open={isOpen}>
          <button
            type="button"
            class="cap-row"
            aria-expanded={isOpen}
            onclick={() => toggleExpand(gate.capability)}
          >
            <span class="chev" aria-hidden="true">
              <Icon name={isOpen ? "chevron-down" : "chevron-right"} size={15} />
            </span>
            <span class="cap-name">
              <span class="cap-label">{capabilityLabel(gate.capability)}</span>
              <code class="cap-code">{gate.capability}</code>
            </span>
            <Badge variant={gateBadge(gate)} />
          </button>

          {#if isOpen}
            <div class="cap-detail">
              <p class="cap-desc">{capabilityDescription(gate.capability)}</p>

              {#if explanation.kind !== "enabled"}
                <p class="cap-why">
                  <Icon name="info" size={14} />
                  {explanation.why} {explanation.requirement}
                </p>
              {/if}

              <dl class="cap-meta">
                <div><dt>State</dt><dd><code>{gate.state}</code></dd></div>
                <div><dt>Default</dt><dd><code>{gate.default_state}</code></dd></div>
                <div><dt>Source</dt><dd><code>{gate.source}</code></dd></div>
              </dl>

              <div class="mode-block">
                <p class="field-label">Decision mode for AI-proposed actions</p>
                {#if decisionModes[gate.capability] === undefined}
                  <p class="loading">Loading mode…</p>
                {:else}
                  <div class="mode-seg" role="group" aria-label={`Decision mode for ${gate.capability}`}>
                    {#each DECISION_MODES as mode (mode)}
                      <button
                        type="button"
                        class="mode-btn"
                        class:selected={decisionModes[gate.capability] === mode}
                        title={DECISION_MODE_COPY[mode].hint}
                        aria-pressed={decisionModes[gate.capability] === mode}
                        onclick={() => setMode(gate.capability, mode)}
                        disabled={modeBusy}
                      >
                        {DECISION_MODE_COPY[mode].label}
                      </button>
                    {/each}
                  </div>
                  <p class="mode-hint">
                    {isDecisionMode(decisionModes[gate.capability])
                      ? DECISION_MODE_COPY[decisionModes[gate.capability] as DecisionMode].hint
                      : "Current mode could not be read."}
                  </p>
                {/if}
              </div>

              <div class="cap-actions">
                {#if canEnable(gate)}
                  <button type="button" class="btn btn-soft btn-sm" onclick={() => startEnable(gate)}>
                    Enable gate
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
                    Disable gate
                  </button>
                {/if}
                {#if !gate.can_current_principal_change}
                  <span class="muted">Gate changes are not permitted for your principal.</span>
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
  .phase-h {
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--text-3);
    margin: var(--space-4) 0 var(--space-2);
  }
  .cap-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
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
    gap: 0.6rem;
    width: 100%;
    font: inherit;
    text-align: left;
    background: transparent;
    border: none;
    padding: 0.6rem 0.9rem;
    cursor: pointer;
    color: var(--text-1);
  }
  .cap-row:hover {
    background: var(--sunken);
  }
  .chev {
    color: var(--text-3);
    display: grid;
    place-items: center;
  }
  .cap-name {
    flex: 1;
    display: flex;
    align-items: baseline;
    gap: 0.6rem;
    min-width: 0;
    flex-wrap: wrap;
  }
  .cap-label {
    font-weight: 600;
  }
  .cap-code {
    color: var(--text-3);
    font-size: 0.74rem;
  }
  .cap-detail {
    border-top: 1px solid var(--border);
    padding: var(--space-3) var(--space-4) var(--space-4);
    background: var(--sunken);
  }
  .cap-desc {
    font-size: 0.88rem;
    color: var(--text-2);
    margin: 0 0 0.5rem;
  }
  .cap-why {
    display: flex;
    gap: 0.4rem;
    align-items: flex-start;
    font-size: 0.82rem;
    color: var(--info);
    margin: 0 0 0.6rem;
  }
  .cap-meta {
    display: flex;
    gap: 1.2rem;
    flex-wrap: wrap;
    margin: 0 0 var(--space-3);
  }
  .cap-meta div {
    display: flex;
    gap: 0.35rem;
    align-items: baseline;
  }
  .cap-meta dt {
    font-size: 0.7rem;
    font-weight: 650;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-3);
  }
  .cap-meta dd {
    margin: 0;
    font-size: 0.8rem;
  }
  .mode-block {
    margin-bottom: var(--space-3);
  }
  .mode-seg {
    display: inline-flex;
    gap: 2px;
    background: var(--surface);
    border: 1px solid var(--border-strong);
    border-radius: var(--r-pill);
    padding: 3px;
  }
  .mode-btn {
    font: inherit;
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--text-2);
    background: transparent;
    border: none;
    border-radius: var(--r-pill);
    padding: 0.22rem 0.8rem;
    cursor: pointer;
  }
  .mode-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .mode-btn.selected {
    background: var(--accent-soft);
    color: var(--accent);
  }
  .mode-hint {
    font-size: 0.76rem;
    color: var(--text-3);
    margin: 0.35rem 0 0;
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
