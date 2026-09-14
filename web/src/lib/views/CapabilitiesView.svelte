<script lang="ts">
  import { onMount, tick } from "svelte";
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
    capabilityDomain,
    capabilityLabel,
    enableableTargets,
    groupByDomain,
    isAvailable,
    isDecisionMode,
    isDeferred,
    isInherent,
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
    behaviourCopy,
    commonGates,
    permissionAttention,
    rowSummary,
  } from "../permissionLanguage";
  import {
    bulkOutcome,
    confirmMode,
    confirmedModeValues,
    effectiveGates,
    survivingModes,
    type ConfirmedModes,
  } from "../permissionViewModel";

  let { principal = "—" }: { principal?: string } = $props();

  let gates = $state<CapabilityGate[] | null>(null);
  let loadError = $state<string | null>(null);
  let search = $state("");
  let expanded = $state<string | null>(null);
  let statusFilter = $state("all");
  let domainFilter = $state("all");
  let refreshing = $state(false);

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
  const filtering = $derived(searching || statusFilter !== "all" || domainFilter !== "all");

  function isCollapsed(domain: string): boolean {
    return !searching && collapsedDomains.includes(domain);
  }
  function toggleDomain(domain: string) {
    collapsedDomains = collapsedDomains.includes(domain)
      ? collapsedDomains.filter((d) => d !== domain)
      : [...collapsedDomains, domain];
  }
  let notice = $state<{ kind: "ok" | "error"; text: string } | null>(null);

  /*
   * The per-capability decision mode is the primary control here. It arrives
   * inline on each gate (gate.decision_mode) from the single
   * /api/capability-gates read, so there is no per-capability fan-out. A mode
   * the server has confirmed is kept here so the control updates without a full
   * reload.
   *
   * NEW-PERM-02 — this used to be *only* the control's private knowledge. Every
   * summary above the registry read the raw gate list instead, so a capability
   * set to Never showed Never on its control and Automatic in the two sections
   * above it. There is one list now: `effective` is the read with every
   * confirmation merged in, and nothing on this page derives from anything else.
   */
  let confirmedModes = $state<ConfirmedModes>({});
  /** Counts confirmed mutations, so a slow refresh cannot undo a fast change. */
  let mutationSeq = $state(0);
  const effective = $derived(effectiveGates(gates ?? [], confirmedModes));
  const controlModes = $derived(confirmedModeValues(confirmedModes));

  /**
   * The two sections that come before the registry.
   *
   * Sixty-six equally weighted cards is a filing system: an owner arrives
   * either because something needs them or because they want to change one of a
   * handful of permissions, and the rest of the list is reference. Both derive
   * from `effective` — the same list the registry renders — so neither can claim
   * a state the list below contradicts. A search is a request to see matches, so
   * both fold away while one is running.
   */
  const attention = $derived(permissionAttention(effective));
  const common = $derived(commonGates(effective));

  /** Record a mode the server has confirmed, for every presentation at once. */
  function recordConfirmed(capability: string, mode: DecisionMode) {
    mutationSeq += 1;
    confirmedModes = confirmMode(confirmedModes, capability, mode, mutationSeq);
  }
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
  /*
   * Bulk-apply a tightening mode (ask/deny) to all selected capabilities.
   *
   * NEW-PERM-02 — these are N independent governed mutations, and the loop used
   * to stop at the first refusal and report "The bulk change was rejected". The
   * capabilities already changed stayed changed, so the sentence told the owner
   * something untrue about their own policy. Every selection is now attempted,
   * each outcome is recorded against its own capability, and the report names
   * what changed and what did not.
   */
  async function bulkSetMode(mode: DecisionMode) {
    if (mutationBusy || selectedCaps.size === 0 || (mode !== "ask" && mode !== "deny")) return;
    bulkBusy = true;
    notice = null;
    const applied: string[] = [];
    const failed: string[] = [];
    try {
      for (const cap of [...selectedCaps]) {
        try {
          await api.setCapabilityDecisionMode(cap, mode, "bulk-set via web UI");
          recordConfirmed(cap, mode);
          applied.push(cap);
        } catch {
          failed.push(cap);
        }
      }
      const outcome = bulkOutcome(applied, failed);
      if (outcome !== null) {
        notice =
          failed.length === 0
            ? {
                kind: "ok",
                text: `${outcome.text.replace(/\.$/, "")} to “${BEHAVIOUR_COPY[mode].label}”.`,
              }
            : outcome;
      }
      // Only what changed leaves the selection, so a refused capability is still
      // selected and can be retried without finding it in the registry again.
      selectedCaps = new Set(failed);
    } finally {
      bulkBusy = false;
    }
  }

  /**
   * The mode a row renders. `gate` already comes from `effective`, so the
   * confirmation is merged in before this is asked — there is no second place
   * that has to remember to apply it.
   */
  function modeFor(gate: CapabilityGate): DecisionMode | "unknown" {
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
  const mutationBusy = $derived(bulkBusy || modeBusyCap !== null || busy);
  let dialogError = $state<string | null>(null);

  /** Counts reads, so an older one cannot land on top of a newer one. */
  let loadSeq = 0;

  async function load() {
    /*
     * NEW-PERM-02 — a read is only authoritative about what the server held
     * when it left. Two things are stamped before it goes: which read this is,
     * so a slow one that resolves after a fast one is discarded rather than
     * rendered; and how many mutations had been confirmed, so the confirmations
     * this response already reflects are dropped and anything confirmed while it
     * was in flight survives it. Without the second, pressing Refresh just after
     * a change showed the owner the value they had replaced.
     */
    const read = ++loadSeq;
    const confirmedBefore = mutationSeq;
    loadError = null;
    refreshing = true;
    try {
      const fresh = await api.capabilityGates();
      if (read !== loadSeq) return;
      gates = fresh;
      const editable = new Set(fresh.filter(g => g.can_current_principal_change && !isDeferred(g) && !isInherent(g)).map(g => g.capability));
      selectedCaps = new Set([...selectedCaps].filter(cap => editable.has(cap)));
      confirmedModes = survivingModes(confirmedModes, confirmedBefore);
    } catch (e) {
      if (read !== loadSeq) return;
      gates = null;
      selectedCaps = new Set();
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    } finally {
      if (read === loadSeq) refreshing = false;
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
    effective.filter(
      (g) =>
        g.default_state === "enabled_runtime" &&
        g.state !== "enabled_runtime" &&
        !isDeferred(g) &&
        !isInherent(g),
    ).length,
  );

  const filtered = $derived.by(() => {
    const q = search.trim().toLowerCase();
    return groupByDomain(governedGates.filter(gate => {
      const text = `${gate.capability} ${capabilityLabel(gate.capability)} ${capabilityDescription(gate.capability)} ${capabilityDomain(gate.capability)}`.toLowerCase();
      if (q && !text.includes(q)) return false;
      if (domainFilter !== "all" && capabilityDomain(gate.capability) !== domainFilter) return false;
      if (statusFilter === "on") return isAvailable(gate);
      if (statusFilter === "off") return !isAvailable(gate);
      if (statusFilter === "attention") return attention.some(item => item.capability === gate.capability);
      if (statusFilter === "selected") return selectedCaps.has(gate.capability);
      return true;
    }));
  });
  const visibleCount = $derived(filtered.reduce((count, group) => count + group.gates.length, 0));

  function clearFilters() {
    search = "";
    statusFilter = "all";
    domainFilter = "all";
  }
  function selectable(gates: CapabilityGate[]): string[] {
    return gates.filter(gate => gate.can_current_principal_change).map(gate => gate.capability);
  }
  // A summary of eight, and which eight matters: the alphabetically first eight
  // are capabilities nobody has an opinion about, so on a fresh account the
  // summary said nothing at all. Ranked by authority instead — see
  // `authorityMatrixGates`.
  const governedGates = $derived(
    effective.filter((gate) => !isDeferred(gate) && !isInherent(gate)),
  );
  const authorityGates = $derived(authorityMatrixGates(governedGates));
  const domains = $derived(groupByDomain(governedGates).map(group => group.domain));
  const onCount = $derived(governedGates.filter(isAvailable).length);

  function toggleExpand(capability: string) {
    expanded = expanded === capability ? null : capability;
  }

  /** The row's own control, so a shortcut can land keyboard focus on it. */
  function rowToggleId(capability: string): string {
    return `cap-row-${capability}`;
  }

  /*
   * NEW-PERM-01 — the shortcut the two top sections were missing.
   *
   * Common permissions and Needs your attention were lists of text. They are
   * the most prominent thing on the page, they name exactly the permissions an
   * owner arrived to change, and neither offered a way to change one: the owner
   * read the name, then went and found the same name again in a registry of
   * sixty-six rows. Prominence that does not act is friction wearing the
   * clothes of help.
   *
   * This is deliberately a reveal rather than a second copy of the control. Two
   * editable copies of one permission is how a page comes to disagree with
   * itself, which is the defect next door (NEW-PERM-02). So the shortcut moves
   * the owner to the one control that exists — clearing a filter that would hide
   * it, opening the group that holds it, opening the row, and putting the
   * keyboard on it, because a shortcut that scrolls and leaves focus behind has
   * only helped the half of the page that uses a mouse.
   */
  async function revealCapability(capability: string) {
    const gate = effective.find((entry) => entry.capability === capability);
    if (gate === undefined || isDeferred(gate) || isInherent(gate)) {
      // Never a dead action: a capability with no registry row says so instead
      // of scrolling to nothing.
      notice = {
        kind: "error",
        text: `${capabilityLabel(capability)} has no control in this build, so there is nothing to open.`,
      };
      return;
    }
    clearFilters();
    const domain = capabilityDomain(capability);
    collapsedDomains = collapsedDomains.filter((entry) => entry !== domain);
    expanded = capability;
    await tick();
    const control = document.getElementById(rowToggleId(capability));
    if (control === null) return;
    // Focus first, and never behind a scroll helper that a non-browser DOM does
    // not implement: the keyboard landing on the control is the part of this
    // that a screen-reader user depends on, and it must not be lost to an
    // environment where scrolling is a no-op.
    control.focus();
    control.scrollIntoView?.({ block: "center" });
  }

  async function setMode(gate: CapabilityGate, mode: DecisionMode) {
    const capability = gate.capability;
    if (modeFor(gate) === mode || mutationBusy || !gate.can_current_principal_change) return;
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
      recordConfirmed(capability, mode);
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
    if (mutationBusy || !canEnable(gate)) return;
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
    if (pending === null || mutationBusy) return;
    busy = true;
    dialogError = null;
    try {
      const p = pending;
      await runMutation(p, values);
      notice = { kind: "ok", text: describeSuccess(p) };
      pending = null;
      // Record the confirmation before the reload leaves, so the read cannot
      // clear it: the set is authoritative and the persisted read may lag it.
      if (p.kind === "set_mode") recordConfirmed(p.capability, p.mode);
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

<header class="permissions-header">
  <div>
    <h1>Permissions</h1>
    <p>Choose what Raiker can use and when it should ask you.</p>
  </div>
  <GuideLink route="capabilities" />
</header>

{#if notice}
  <p class="notice {notice.kind === 'ok' ? 'notice-ok' : 'notice-danger'}" role="status">{notice.text}</p>
{/if}

{#if gates !== null && authorityGates.length > 0}
  <div class="permission-stats" role="group" aria-label="Filter permissions by status">
    {#each [{id: "all", label: "All permissions", count: governedGates.length}, {id: "on", label: "Available", count: onCount}, {id: "off", label: "Unavailable", count: governedGates.length - onCount}, {id: "attention", label: "Needs review", count: attention.length}] as item}
      <button type="button" class:active={statusFilter === item.id} aria-pressed={statusFilter === item.id} onclick={() => statusFilter = item.id}>
        <strong>{item.count}</strong><span>{item.label}</span>
      </button>
    {/each}
  </div>
  <details class="authority-disclosure">
    <summary>How your permissions apply</summary>
    <AuthorityMatrix gates={authorityGates} total={governedGates.length} />
  </details>
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
    <button type="button" class="btn btn-ghost btn-sm" onclick={() => (selectedCaps = new Set())} disabled={mutationBusy}>Clear</button>
    <span class="bulk-label">Set all to:</span>
    <!-- REM-PERM-02 — the same words the controls below use. These two said
         "Ask" and "Deny" about the values every other control on the page calls
         "Ask me" and "Never", so one policy had two names on one screen. -->
    <button type="button" class="btn btn-sm" onclick={() => void bulkSetMode("ask")} disabled={mutationBusy}>{BEHAVIOUR_COPY.ask.label}</button>
    <button type="button" class="btn btn-sm btn-danger" onclick={() => void bulkSetMode("deny")} disabled={mutationBusy}>{BEHAVIOUR_COPY.deny.label}</button>
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
      placeholder="Search permissions, actions or groups…"
      bind:value={search}
    />
  </div>
  <button type="button" class="btn btn-ghost btn-sm" onclick={load} disabled={refreshing || mutationBusy} aria-label="Refresh capabilities">
    <Icon name="refresh" size="sm" />
    {refreshing ? "Refreshing…" : "Refresh"}
  </button>
</div>

{#if loadError}
  <PageState state="error" title="Couldn't load capabilities" detail={loadError} />
{:else if gates === null}
  <PageState state="loading" title="Loading capabilities…" />
{:else}
  {#if !filtering && attention.length > 0}
    <!-- VIS2-18's hierarchy, on this page: what needs a decision comes before
         what is merely configured. Narrow on purpose — a capability sitting at
         its default is not attention, and a page that calls everything
         attention has said nothing. -->
    <section class="cap-attention" aria-label="Needs your attention">
      <h2>Needs your attention</h2>
      <ul>
        {#each attention as item (item.capability)}
          <li>
            <span class="shortcut-text"><strong>{item.label}</strong> — {item.reason}</span>
            <!-- NEW-PERM-01 — the section says a decision wants a second look,
                 so it offers the place to make it. -->
            <button
              type="button"
              class="btn btn-ghost btn-sm"
              onclick={() => void revealCapability(item.capability)}
            >
              Review
              <span class="sr-only">{item.label}</span>
            </button>
          </li>
        {/each}
      </ul>
    </section>
  {/if}

  {#if !filtering && common.length > 0}
    <!-- The handful people actually come to change, above the registry that
         holds everything. Same gates, same controls: this is an ordering, not a
         second copy of the page's state. -->
    <section class="cap-common" aria-label="Common permissions">
      <h2>Common permissions</h2>
      <ul>
        {#each common as gate (gate.capability)}
          <li>
            <span class="shortcut-text">
              <span class="cap-label">{capabilityLabel(gate.capability)}</span>
              <span class="cap-summary">{rowSummary(gate, isAvailable(gate))}</span>
            </span>
            <button
              type="button"
              class="btn btn-ghost btn-sm"
              onclick={() => void revealCapability(gate.capability)}
            >
              Manage
              <span class="sr-only">{capabilityLabel(gate.capability)}</span>
            </button>
          </li>
        {/each}
      </ul>

    </section>
  {/if}

  <!-- The registry: everything, grouped by domain. It keeps the full list an
       owner may need to audit, and sits under the two sections that answer the
       questions people actually arrive with. -->
  <section class="cap-registry" aria-label="All permissions">
  <div class="registry-heading">
    <div><h2>All permissions</h2><p aria-live="polite">Showing {visibleCount} of {governedGates.length} permissions</p></div>
    <div class="registry-filters">
      <label>Group
        <select bind:value={domainFilter} aria-label="Permission group">
          <option value="all">All groups</option>
          {#each domains as domain}<option value={domain}>{domain}</option>{/each}
        </select>
      </label>
      <label>Show
        <select bind:value={statusFilter} aria-label="Permission status">
          <option value="all">All permissions</option>
          <option value="on">Available</option>
          <option value="off">Unavailable</option>
          <option value="attention">Needs review</option>
          <option value="selected">Selected</option>
        </select>
      </label>
      <button type="button" class="btn btn-ghost btn-sm" onclick={() => collapsedDomains = []}>Expand groups</button>
      <button type="button" class="btn btn-ghost btn-sm" disabled={searching} onclick={() => collapsedDomains = [...domains]}>Collapse groups</button>
      {#if filtering}<button type="button" class="btn btn-ghost btn-sm" onclick={clearFilters}>Clear filters</button>{/if}
    </div>
  </div>
  {#if visibleCount === 0}
    <PageState state="empty" title={governedGates.length === 0 ? "No permissions available" : "No matching permissions"} detail={governedGates.length === 0 ? "This runtime has not reported any configurable tools." : "Try a different search, group or status filter."} />
  {/if}
  {#each filtered as group (group.domain)}
    <div class="cap-list">
      <div class="phase-head">
        <label class="phase-select-all">
          <input
            type="checkbox"
            disabled={mutationBusy || selectable(group.gates).length === 0}
            indeterminate={selectable(group.gates).some(cap => selectedCaps.has(cap)) && !allSelectedInGroup(selectable(group.gates))}
            checked={allSelectedInGroup(selectable(group.gates))}
            onchange={() => toggleSelectAllInGroup(selectable(group.gates))}
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
        <div class="cap card" class:open={isOpen}>
          <div class="cap-row">
            <input
              type="checkbox"
              class="cap-check"
              disabled={mutationBusy || !gate.can_current_principal_change}
              checked={selectedCaps.has(gate.capability)}
              onchange={() => toggleCapSelected(gate.capability)}
              aria-label={`Select ${capabilityLabel(gate.capability)}`}
            />
            <button
              type="button"
              class="cap-toggle"
              id={rowToggleId(gate.capability)}
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
                  {rowSummary(gate, isAvailable(gate))}
                </span>
                {#if realityLabel(gate)}
                  <span class="cap-reality">{realityLabel(gate)}</span>
                {/if}
              </span>
            </button>

            <ToolControlBoard
              gates={[gate]}
              showLabel={false}
              modes={controlModes}
              busyCapability={mutationBusy ? gate.capability : null}
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
              <!-- NEW-PERM-03 — an unrecognised mode used to drop this block
                   entirely, so the card answered the behaviour question with
                   silence. It is answered as Unknown instead. -->
              <p class="question">{BEHAVIOUR_QUESTION}</p>
              <p class="mode-hint">{behaviourCopy(gate.decision_mode).hint}</p>

              <p class="question">{AVAILABILITY_QUESTION}</p>
              <div class="cap-actions">
                {#if canEnable(gate)}
                  <button type="button" class="btn btn-soft btn-sm" disabled={mutationBusy} onclick={() => startEnable(gate)}>
                    Turn on
                  </button>
                {/if}
                {#if canDisable(gate)}
                  <button
                    type="button"
                    class="btn btn-danger btn-sm"
                    disabled={mutationBusy}
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
  .permissions-header { display: flex; align-items: start; justify-content: space-between; gap: var(--space-4); margin-bottom: var(--space-4); }
  .permissions-header h1 { margin: 0; font-size: var(--text-xl); }
  .permissions-header p { margin: var(--space-2) 0 0; color: var(--text-2); }
  .permission-stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-3); margin-bottom: var(--space-4); }
  .permission-stats button { display: flex; flex-direction: column; align-items: start; gap: var(--space-2); padding: var(--space-4); border: 1px solid var(--border); border-radius: var(--r-lg); background: var(--surface); color: var(--text-2); font: inherit; cursor: pointer; text-align: left; }
  .permission-stats strong { font-size: var(--text-xl); color: var(--text-1); font-variant-numeric: tabular-nums; }
  .permission-stats button.active { border-color: var(--accent); background: var(--accent-soft); }
  .authority-disclosure { margin-bottom: var(--space-4); }
  .authority-disclosure summary { cursor: pointer; color: var(--text-2); padding: var(--space-2) 0; }
  .registry-heading { display: flex; justify-content: space-between; align-items: end; flex-wrap: wrap; gap: var(--space-3); margin-bottom: var(--space-4); }
  .registry-heading h2 { font-size: var(--text-md); margin: 0; }
  .registry-heading p { font-size: var(--text-sm); color: var(--text-3); margin: var(--space-2) 0 0; }
  .registry-filters { display: flex; align-items: end; gap: var(--space-2); flex-wrap: wrap; }
  .registry-filters label { display: grid; gap: var(--space-1); font-size: var(--text-xs); color: var(--text-2); }
  .registry-filters select { font: inherit; font-size: var(--text-sm); color: var(--text-1); background: var(--surface); border: 1px solid var(--border-strong); border-radius: var(--r-sm); padding: var(--space-2); max-width: 100%; }
  @media (max-width: 600px) {
    .permission-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .permissions-header { flex-wrap: wrap; }
    .registry-filters { width: 100%; }
  }
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
  .cap-attention li { color: var(--text-2); font-size: var(--text-sm); }
  /* NEW-PERM-01 — each entry is a fact and the action on it, so the row reads
     left to right and the buttons line up down the right-hand edge. Wraps
     rather than truncates at a phone width: the name of the permission is the
     part that must survive. */
  .cap-attention li, .cap-common li { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); flex-wrap: wrap; }
  .shortcut-text { display: flex; align-items: baseline; gap: var(--space-3); flex: 1 1 12rem; min-width: 0; flex-wrap: wrap; }
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
