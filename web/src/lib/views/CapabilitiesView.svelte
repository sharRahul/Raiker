<script lang="ts">
  import { onMount } from "svelte";
  import AuthorityMatrix from "../components/AuthorityMatrix.svelte";
  import Icon from "../components/Icon.svelte";
  import PageState from "../components/PageState.svelte";
  import StepUpDialog from "../components/StepUpDialog.svelte";
  import ToolControlBoard from "../components/ToolControlBoard.svelte";
  import type { StepUpValues } from "../components/StepUpDialog.svelte";
  import GuideLink from "../components/GuideLink.svelte";
  import { api, ApiError } from "../api";
  import type { CapabilityGate } from "../apiTypes";
  import {
    canDisable,
    canEnable,
    capabilityDescription,
    capabilityLabel,
    enableableTargets,
    groupByDomain,
    isDecisionMode,
    isDeferred,
    isInherent,
    isDisabled,
    authorityMatrixGates,
    isOnByDefault,
    realityLabel,
    realityNote,
    unsetResolutionNote,
    requiresStepUpToken,
    type DecisionMode,
  } from "../capabilityModel";
  import { explainReasonCode } from "../reasonCodes";
  import {
    AVAILABILITY_QUESTION,
    BEHAVIOUR_COPY,
    BEHAVIOUR_QUESTION,
    CANNOT_CHANGE_HERE,
    commonGates,
    permissionAttention,
    rowSummary,
  } from "../permissionLanguage";

  let { principal = "—" }: { principal?: string } = $props();

  let gates = $state<CapabilityGate[] | null>(null);
  let loadError = $state<string | null>(null);
  let search = $state("");
  let expanded = $state<string | null>(null);

  /**
   * Domain groups the owner has folded away.
   *
   * The registry holds 66 gates across a dozen domains and every one of them
   * rendered expanded, so finding the capability you came for meant scrolling
   * past every capability you did not. Collapsed by name rather than by index,
   * so filtering the list does not fold a different group than the one that was
   * closed.
   *
   * A search overrides it: typing is asking to see matches, and answering that
   * with a folded group would be the page arguing with the query.
   */
  let collapsedDomains = $state<string[]>([]);
  const searching = $derived(search.trim() !== "");

  /**
   * The two sections that come before the registry.
   *
   * Sixty-six equally weighted cards is a filing system: an owner arrives
   * either because something needs them or because they want to change one of a
   * handful of permissions, and the rest of the list is reference. Both are
   * derived from the same gates the registry renders, so neither can claim a
   * state the list below contradicts. A search is a request to see matches, so
   * both fold away while one is running.
   */
  const attention = $derived(gates === null ? [] : permissionAttention(gates));
  const common = $derived(gates === null ? [] : commonGates(gates));
  function isCollapsed(domain: string): boolean {
    return !searching && collapsedDomains.includes(domain);
  }
  function toggleDomain(domain: string) {
    collapsedDomains = collapsedDomains.includes(domain)
      ? collapsedDomains.filter((d) => d !== domain)
      : [...collapsedDomains, domain];
  }
  let notice = $state<{ kind: "ok" | "error"; text: string } | null>(null);

  // The per-capability decision mode is the primary control here. It arrives inline
  // on each gate (gate.decision_mode) from the single /api/capability-gates read, so
  // there is no per-capability fan-out. Local overrides after a successful set are
  // kept here so the segmented control updates without a full reload.
  let modeOverrides = $state<Record<string, DecisionMode>>({});
  let modeBusyCap = $state<string | null>(null);
  let selectedCaps = $state<Set<string>>(new Set());
  let bulkBusy = $state(false);

  function toggleCapSelected(capability: string) {
    const next = new Set(selectedCaps);
    if (next.has(capability)) next.delete(capability);
    else next.add(capability);
    selectedCaps = next;
  }
  function toggleSelectAllInGroup(caps: string[]) {
    const allSelected = caps.every((c) => selectedCaps.has(c));
    const next = new Set(selectedCaps);
    if (allSelected) { for (const c of caps) next.delete(c); }
    else { for (const c of caps) next.add(c); }
    selectedCaps = next;
  }
  function allSelectedInGroup(caps: string[]): boolean {
    return caps.length > 0 && caps.every((c) => selectedCaps.has(c));
  }
  // Bulk-apply a tightening mode (ask/deny) to all selected capabilities.
  async function bulkSetMode(mode: DecisionMode) {
    if (bulkBusy || selectedCaps.size === 0) return;
    bulkBusy = true;
    notice = null;
    try {
      for (const cap of selectedCaps) {
        await api.setCapabilityDecisionMode(cap, mode, "bulk-set via web UI");
        modeOverrides = { ...modeOverrides, [cap]: mode };
      }
      notice = { kind: "ok", text: `${selectedCaps.size} capabilit${selectedCaps.size === 1 ? "y" : "ies"} set to "${BEHAVIOUR_COPY[mode].label}".` };
      selectedCaps = new Set();
    } catch (e) {
      const explained = e instanceof ApiError ? explainReasonCode(e.reasonCode) : null;
      notice = { kind: "error", text: explained ? `${explained.plain} ${explained.remediation ?? ""}` : "The bulk change was rejected." };
    } finally {
      bulkBusy = false;
    }
  }

  function modeFor(gate: CapabilityGate): DecisionMode | "unknown" {
    const override = modeOverrides[gate.capability];
    if (override !== undefined) return override;
    return isDecisionMode(gate.decision_mode) ? gate.decision_mode : "unknown";
  }

  // The pending mutation awaiting step-up confirmation.
  type Pending =
    | {
        kind: "enable";
        capability: string;
        target: string;
        requireToken: boolean;
        requireThreatAck: boolean;
        ackNeeded: boolean;
      }
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

  // Integrated capabilities (a real executor) ship `enabled_runtime` as their
  // static default, but the web dashboard applies per-principal controls that
  // fail closed: each one starts off for your account until you turn it on, and
  // reaching `enabled_runtime` also needs a runtime-enablement mode active (not
  // Development preview). Surfacing that reconciles the README's "default
  // enabled_runtime" wording with the all-off state a fresh workspace shows
  // (FIX-05). We detect it as gates whose default is runtime-enabled but whose
  // effective state is not.
  const integratedButOff = $derived(
    (gates ?? []).filter(
      (g) =>
        g.default_state === "enabled_runtime" &&
        g.state !== "enabled_runtime" &&
        !isDeferred(g) &&
        !isInherent(g),
    ).length,
  );

  const filtered = $derived.by(() => {
    if (gates === null) return [];
    const q = search.trim().toLowerCase();
    // Only real tools appear here. Deferred capabilities (no executor) and
    // inherent contract surfaces are not tools: no row, no selector, no
    // pretend control. They stay visible in Diagnostics as fail-closed.
    const actionable = gates.filter((g) => !isDeferred(g) && !isInherent(g));
    const matches = q
      ? actionable.filter(
          (g) =>
            g.capability.toLowerCase().includes(q) ||
            capabilityLabel(g.capability).toLowerCase().includes(q),
        )
      : actionable;
    return groupByDomain(matches);
  });
  // A summary of eight, and which eight matters: the alphabetically first eight
  // are capabilities nobody has an opinion about, so on a fresh account the
  // summary said nothing at all. Ranked by authority instead — see
  // `authorityMatrixGates`.
  const governedGates = $derived(
    (gates ?? []).filter((gate) => !isDeferred(gate) && !isInherent(gate)),
  );
  const authorityGates = $derived(authorityMatrixGates(governedGates));

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
        text: `${capabilityLabel(capability)} is now set to “${BEHAVIOUR_COPY[mode].label}”.`,
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
    // Drive the step-up requirements from the gate's real activation
    // preconditions when the backend reports them, falling back to the static
    // Tier-2 list for older payloads. A human confirmation token is required
    // whenever the backend says so (or for the Tier-2 caps); the threat-model
    // acknowledgement is required when the capability needs one and none is on
    // record yet.
    const requireToken =
      gate.requires_human_confirmation ?? requiresStepUpToken(gate.capability);
    const ackNeeded =
      (gate.requires_threat_model_ack ?? requiresStepUpToken(gate.capability)) &&
      !(gate.threat_model_ack_recorded ?? false);
    pending = {
      kind: "enable",
      capability: gate.capability,
      target,
      requireToken,
      requireThreatAck: ackNeeded,
      ackNeeded,
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
          requireThreatAck: pending.requireThreatAck,
        };
      case "disable_cap":
        return {
          title: `Disable ${capabilityLabel(pending.capability)}`,
          requireToken: false,
          requireThreatAck: false,
        };
      case "set_mode":
        return {
          title: `Set ${capabilityLabel(pending.capability)} to “${BEHAVIOUR_COPY[pending.mode].label}”`,
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
      // Record the threat-model acknowledgement first (governed, owner-only) so
      // the activation check finds it satisfied. This only persists the ack; the
      // transition below still runs through the full governed gate.
      if (p.ackNeeded && values.threatAck) {
        await api.recordThreatModelAck(p.capability, values.reason);
      }
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
    return `${capabilityLabel(p.capability)} is now set to “${BEHAVIOUR_COPY[p.mode].label}”.`;
  }

  onMount(load);
</script>

  <GuideLink route="capabilities" />

{#if notice}
  <p class="notice {notice.kind === 'ok' ? 'notice-ok' : 'notice-danger'}" role="status">{notice.text}</p>
{/if}

{#if gates !== null && authorityGates.length > 0}
  <AuthorityMatrix gates={authorityGates} total={governedGates.length} />
{/if}

{#if integratedButOff > 0}
  <div class="runtime-note" role="note">
    <Icon name="info" size="md" />
    <!-- Five lines teaching the fail-closed model, on a page that already links
         to the guide section that teaches it. What is left is the one fact this
         page must state about its own rows, and the one route it is not. -->
    <span>
      Capabilities with a real executor start <strong>off</strong> on this account until you turn
      them on. To stop all work instead, use
      <a href="#/settings">Settings → Runtime configuration</a>.
    </span>
  </div>
{/if}

{#if selectedCaps.size > 0}
  <div class="bulk-bar" role="toolbar" aria-label="Bulk capability actions">
    <span class="bulk-count">{selectedCaps.size} selected</span>
    <button type="button" class="btn btn-ghost btn-sm" onclick={() => (selectedCaps = new Set())} disabled={bulkBusy}>Clear</button>
    <span class="bulk-label">Set all to:</span>
    <button type="button" class="btn btn-sm" onclick={() => void bulkSetMode("ask")} disabled={bulkBusy}>Ask</button>
    <button type="button" class="btn btn-sm btn-danger" onclick={() => void bulkSetMode("deny")} disabled={bulkBusy}>Deny</button>
  </div>
{/if}

<div class="toolbar">
  <div class="search">
    <Icon name="search" size="sm" />
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
    <Icon name="refresh" size="sm" />
    Refresh
  </button>
</div>

{#if loadError}
  <PageState state="error" title="Couldn't load capabilities" detail={loadError} />
{:else if gates === null}
  <PageState state="loading" title="Loading capabilities…" />
{:else}
  {#if !searching && attention.length > 0}
    <!-- VIS2-18's hierarchy, on this page: what needs a decision comes before
         what is merely configured. Narrow on purpose — a capability sitting at
         its default is not attention, and a page that calls everything
         attention has said nothing. -->
    <section class="cap-attention" aria-label="Needs your attention">
      <h2>Needs your attention</h2>
      <ul>
        {#each attention as item (item.capability)}
          <li><strong>{item.label}</strong> — {item.reason}</li>
        {/each}
      </ul>
    </section>
  {/if}

  {#if !searching && common.length > 0}
    <!-- The handful people actually come to change, above the registry that
         holds everything. Same gates, same controls: this is an ordering, not a
         second copy of the page's state. -->
    <section class="cap-common" aria-label="Common permissions">
      <h2>Common permissions</h2>
      <ul>
        {#each common as gate (gate.capability)}
          <li>
            <span class="cap-label">{capabilityLabel(gate.capability)}</span>
            <span class="cap-summary">{rowSummary(gate, !isDisabled(gate))}</span>
          </li>
        {/each}
      </ul>
      <p class="muted">Every permission, including these, is in the list below.</p>
    </section>
  {/if}

  <!-- The registry: everything, grouped by domain. It keeps the full list an
       owner may need to audit, and sits under the two sections that answer the
       questions people actually arrive with. -->
  <section class="cap-registry" aria-label="All permissions">
  {#each filtered as group (group.domain)}
    <div class="cap-list">
      <div class="phase-head">
        <label class="phase-select-all">
          <input
            type="checkbox"
            checked={allSelectedInGroup(group.gates.map((g) => g.capability))}
            onchange={() => toggleSelectAllInGroup(group.gates.map((g) => g.capability))}
            aria-label={`Select all ${group.domain} capabilities`}
          />
          {group.domain}
        </label>
        <button
          type="button"
          class="phase-fold"
          aria-expanded={!isCollapsed(group.domain)}
          onclick={() => toggleDomain(group.domain)}
        >
          <span class="phase-count">{group.gates.length}</span>
          <Icon name={isCollapsed(group.domain) ? "chevron-right" : "chevron-down"} size="sm" />
          <span class="sr-only">
            {isCollapsed(group.domain) ? "Show" : "Hide"}
            {group.domain} capabilities
          </span>
        </button>
      </div>
      {#each isCollapsed(group.domain) ? [] : group.gates as gate (gate.capability)}
        {@const isOpen = expanded === gate.capability}
        {@const mode = modeFor(gate)}
        <div class="cap card" class:open={isOpen}>
          <div class="cap-row">
            <input
              type="checkbox"
              class="cap-check"
              checked={selectedCaps.has(gate.capability)}
              onchange={() => toggleCapSelected(gate.capability)}
              aria-label={`Select ${capabilityLabel(gate.capability)}`}
            />
            <button
              type="button"
              class="cap-toggle"
              aria-expanded={isOpen}
              onclick={() => toggleExpand(gate.capability)}
            >
              <span class="chev" aria-hidden="true">
                <Icon name={isOpen ? "chevron-down" : "chevron-right"} size="sm" />
              </span>
              <span class="cap-name">
                <span class="cap-label">{capabilityLabel(gate.capability)}</span>
                <!-- Whether the capability is on was only discoverable by
                     opening the card and reading which buttons appeared, while
                     the decision mode beside it showed on every row on or off.
                     A permission list that cannot be scanned for what is on is
                     not a permission list. -->
                <!-- Availability and behaviour on the closed row, in the order
                     the page asks them: a list that has to be opened row by row
                     to learn what is on cannot be scanned.

                     One statement of availability, not two. This row carried a
                     separate "Off" chip beside the summary, which said the same
                     thing twice — and on a capability that is on by default the
                     two disagreed, the chip reading "On by default" next to a
                     summary reading "Off". BUG-239's distinction is kept: being
                     on because nothing is stored is a different fact from being
                     switched on, and it is said here rather than contradicted. -->
                {#if isOnByDefault(gate)}
                  <span class="cap-reality cap-default-on">On by default</span>
                {/if}
                <span class="cap-summary">
                  {rowSummary(gate, !isDisabled(gate) || isOnByDefault(gate))}
                </span>
                {#if realityLabel(gate)}
                  <span class="cap-reality">{realityLabel(gate)}</span>
                {/if}
              </span>
            </button>

            <ToolControlBoard
              gates={[gate]}
              showLabel={false}
              modes={modeOverrides}
              busyCapability={modeBusyCap}
              onDecision={(_capability, m) => setMode(gate, m)}
            />
          </div>

          {#if isOpen}
            <div class="cap-detail">
              <p class="cap-desc">{capabilityDescription(gate.capability)}</p>
              {#if realityNote(gate)}
                <!--
                  GEP-04 — this switch does not decide whether the capability
                  runs. Saying so, and naming what does, is the whole point: a
                  toggle beside a running feature that it does not govern tells
                  the owner something untrue about their own control.
                -->
                <p class="cap-reality-note">
                  <strong>{realityLabel(gate)}.</strong>
                  {realityNote(gate)}
                </p>
              {/if}
              {#if unsetResolutionNote(gate)}
                <!-- BUG-239 — three capabilities read an empty gate table as
                     something other than "off", and which one applies is not
                     guessable from the switch. The card says it rather than
                     leaving an owner to discover it from behaviour. -->
                <p class="cap-reality-note">{unsetResolutionNote(gate)}</p>
              {/if}
              {#if isDecisionMode(mode)}
                <p class="question">{BEHAVIOUR_QUESTION}</p>
                <p class="mode-hint">{BEHAVIOUR_COPY[mode].hint}</p>
              {/if}

              <p class="question">{AVAILABILITY_QUESTION}</p>
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
                  <!-- The fact is unchanged; the sentence is about the owner's
                       account rather than about our vocabulary. -->
                  <span class="muted">{CANNOT_CHANGE_HERE}</span>
                {/if}
              </div>
            </div>
          {/if}
        </div>
      {/each}
    </div>
  {/each}
  </section>
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
    font-size: var(--text-md);
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
  .phase-head { display:flex; align-items:center; justify-content:space-between; gap:var(--space-3); padding: 0 0.9rem 0.3rem; }
  .phase-fold { display:flex; align-items:center; gap:0.35rem; border:0; padding:0.15rem 0.2rem; background:transparent; color:var(--text-3); cursor:pointer; }
  .phase-fold:hover { color: var(--text-1); }
  .phase-count { font-size: var(--text-2xs); font-variant-numeric: tabular-nums; }
  /* VIS-06 — this is a control the owner clicks, not a status chip. */
  .phase-select-all { display:flex; align-items:center; gap:0.4rem; font-size:var(--text-xs); font-weight:650; color:var(--text-3); cursor:pointer; }
  .phase-select-all input { accent-color: var(--accent); }
  .cap-check { accent-color: var(--accent); flex:0 0 auto; }
  .bulk-bar { display:flex; align-items:center; gap:0.5rem; flex-wrap:wrap; padding:0.55rem 0.9rem; border:1px solid var(--accent-border); border-radius:var(--r-md); background:var(--accent-soft); margin-bottom:var(--space-4); }
  .bulk-count { font-weight:700; color:var(--accent); font-size:var(--text-sm); }
  .bulk-label { color:var(--text-3); font-size:var(--text-sm); margin-left:0.3rem; }
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
  /* GEP-04 — a switch that does not govern its own capability says so in the
     row, before the owner opens the card. Text, not colour alone. */
  .cap-reality {
    font-size: var(--text-2xs);
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--text-3);
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    padding: 0.05rem 0.35rem;
    white-space: nowrap;
  }
  /* On by default is not the same claim as Off, so it must not look like it:
     the accent border carries the difference and the words carry it alone if
     colour is unavailable. */
  .cap-default-on {
    color: var(--accent);
    border-color: var(--accent-border, var(--accent));
  }
  .cap-reality-note {
    font-size: var(--text-sm);
    color: var(--text-2);
    margin: 0 0 0.5rem;
    padding: 0.5rem 0.6rem;
    border-left: 2px solid var(--border-strong, var(--border));
    background: var(--raised, transparent);
    border-radius: var(--r-sm);
  }
  .cap-reality-note strong {
    color: var(--text-1);
  }
  .cap-detail {
    border-top: 1px solid var(--border);
    padding: var(--space-3) var(--space-4) var(--space-4);
    background: var(--sunken);
  }
  .cap-desc {
    font-size: var(--text-md);
    color: var(--text-2);
    margin: 0 0 0.4rem;
  }
  .mode-hint {
    font-size: var(--text-sm);
    color: var(--text-3);
    margin: 0 0 var(--space-3);
  }
  /* The two questions, as headings rather than as labels on controls: an owner
     reading down the card meets "Can Raiker use this?" and then "When Raiker
     wants to use it", which is the order the answers depend on. */
  .cap-attention, .cap-common {
    margin-bottom: var(--space-4);
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    background: var(--surface);
  }
  .cap-attention h2, .cap-common h2 { margin: 0 0 var(--space-2); font-size: var(--text-md); }
  .cap-attention ul, .cap-common ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.35rem; }
  .cap-common li { display: flex; align-items: baseline; justify-content: space-between; gap: var(--space-3); }
  .cap-attention li { color: var(--text-2); font-size: var(--text-sm); }
  .cap-common .muted { margin: var(--space-2) 0 0; font-size: var(--text-xs); }
  .question {
    margin: var(--space-3) 0 0.35rem;
    color: var(--text-2);
    font-size: var(--text-xs);
    font-weight: 650;
  }
  /* Availability and behaviour on the closed row, at metadata weight: the row
     is scanned, so this reads without competing with the capability's name. */
  .cap-summary { color: var(--text-3); font-size: var(--text-xs); white-space: nowrap; }
  .cap-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }
  .muted {
    color: var(--text-3);
    font-size: var(--text-sm);
  }
  .runtime-note {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    padding: 0.6rem 0.9rem;
    margin-bottom: var(--space-4);
    border: 1px solid var(--accent-border);
    border-radius: var(--r-md);
    background: var(--accent-soft);
    color: var(--text-2);
    font-size: var(--text-sm);
  }
  .runtime-note a {
    color: var(--accent);
    font-weight: 600;
  }
</style>
