<script lang="ts">
  import { onMount, tick } from "svelte";
  import AuthorityMatrix from "../components/AuthorityMatrix.svelte";
  import Icon from "../components/Icon.svelte";
  import PageState from "../components/PageState.svelte";
  import PermissionRow from "../components/PermissionRow.svelte";
  import StepUpDialog from "../components/StepUpDialog.svelte";
  import type { StepUpValues } from "../components/StepUpDialog.svelte";
  import GuideLink from "../components/GuideLink.svelte";
  import { api, ApiError } from "../api";
  import type { CapabilityGate } from "../apiTypes";
  import {
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
    governsItsOwnCapability,
    realityLabel,
    realityNote,
    authorityMatrixGates,
    requiresStepUpToken,
    type DecisionMode,
  } from "../capabilityModel";
  import { explainReasonCode } from "../reasonCodes";
  import {
    BEHAVIOUR_COPY,
    commonGates,
    permissionAttention,
    permissionPosture,
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

  /*
   * Permissions, rebuilt 2026-09-14.
   *
   * Nothing about what the runtime enforces changed here, and nothing about the
   * page's contracts did either: the two questions, the one merged view model
   * behind every summary (NEW-PERM-02), the shortcuts that move focus to a real
   * control (NEW-PERM-01), the honest Unknown (NEW-PERM-03) and the one owner
   * vocabulary (REM-PERM-02) are all kept. What changed is the shape an owner
   * meets them in.
   *
   * The page had grown seven stacked bands before the first permission: a
   * heading that repeated the one in the top bar, four page-width tiles
   * restating the list as counts, a disclosure, a banner, a bulk bar, a search
   * row, and then two more headed sections. Two of those bands filtered the same
   * list in two different idioms — tiles at the top, selects two-thirds of the
   * way down — so the page had two answers to "what am I looking at" and no
   * obvious place to change one permission.
   *
   * It is one column of four panels now: posture and filters, what needs the
   * owner, what they usually come for, and the registry — with the read-only
   * authority table demoted below all of them (REM-PERM-01) rather than sitting
   * above the controls it summarises.
   */

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

  const withControls = $derived(
    effective.filter((gate) => !isDeferred(gate) && !isInherent(gate)),
  );
  /**
   * The permissions this page actually decides.
   *
   * GEP-04 established that fourteen of these gates decide nothing when
   * flipped — nothing in the product reaches the executor, or the work runs
   * under a different named control — and answered it with a chip on the row.
   * A chip is honest and insufficient: they still carried a mode control, still
   * joined a bulk selection, and still counted toward the page's own summary of
   * what an owner had decided. Everything on this page below this line is a
   * decision; what is not is listed, read-only, at the foot.
   */
  const governedGates = $derived(withControls.filter(governsItsOwnCapability));
  const notDecidedHere = $derived(
    withControls
      .filter((gate) => !governsItsOwnCapability(gate))
      .map((gate) => ({
        capability: gate.capability,
        label: capabilityLabel(gate.capability),
        reality: realityLabel(gate),
        note: realityNote(gate),
      }))
      .sort((a, b) => a.label.localeCompare(b.label)),
  );

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
  const attention = $derived(permissionAttention(governedGates));
  const common = $derived(commonGates(governedGates));

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
      const editable = new Set(fresh.filter(g => g.can_current_principal_change && !isDeferred(g) && !isInherent(g) && governsItsOwnCapability(g)).map(g => g.capability));
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
    governedGates.filter(
      (g) => g.default_state === "enabled_runtime" && g.state !== "enabled_runtime",
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
  const authorityGates = $derived(authorityMatrixGates(governedGates));
  const domains = $derived(groupByDomain(governedGates).map(group => group.domain));
  const posture = $derived(permissionPosture(governedGates));

  /**
   * The status filters, as one control instead of two.
   *
   * These counts were four page-width tiles at the top of the page and a
   * `<select>` two-thirds of the way down it, both setting `statusFilter`. One
   * idiom, in one place, beside the sentence they are counts of. `Selected`
   * appears only once there is a selection to filter to.
   */
  const statusFilters = $derived([
    { id: "all", label: "All", count: governedGates.length },
    { id: "on", label: "Available", count: posture.available },
    { id: "off", label: "Unavailable", count: governedGates.length - posture.available },
    { id: "attention", label: "Needs review", count: attention.length },
    ...(selectedCaps.size > 0
      ? [{ id: "selected", label: "Selected", count: selectedCaps.size }]
      : []),
  ]);

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
    const gate = governedGates.find((entry) => entry.capability === capability);
    if (gate === undefined) {
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

  async function setMode(capability: string, mode: DecisionMode) {
    const gate = effective.find((entry) => entry.capability === capability);
    if (gate === undefined) return;
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

  function startDisable(gate: CapabilityGate) {
    if (mutationBusy) return;
    pending = { kind: "disable_cap", capability: gate.capability };
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

<!-- One page title, and it is the one in the top bar that every other page
     uses. This view carried a second `<h1>` reading "Permissions" directly
     under it — the only view in the product that did. -->
<header class="perm-head">
  <p class="lede">Choose what Raiker can use, and when it should ask you.</p>
  <div class="head-actions">
    <button
      type="button"
      class="btn btn-ghost btn-sm"
      onclick={load}
      disabled={refreshing || mutationBusy}
      aria-label="Refresh capabilities"
    >
      <Icon name="refresh" size="sm" />
      {refreshing ? "Refreshing…" : "Refresh"}
    </button>
    <GuideLink route="capabilities" />
  </div>
</header>

{#if notice}
  <p class="notice {notice.kind === 'ok' ? 'notice-ok' : 'notice-danger'}" role="status">{notice.text}</p>
{/if}

{#if loadError}
  <PageState state="error" title="Couldn't load capabilities" detail={loadError} />
{:else if gates === null}
  <PageState state="loading" title="Loading capabilities…" />
{:else}
  <!-- One posture summary, with the counts as the page's single status filter
       (REM-PERM-01). -->
  <section class="panel posture" aria-label="Permission posture">
    <p class="posture-line">{posture.sentence}</p>
    <div class="chip-row" role="group" aria-label="Filter permissions by status">
      {#each statusFilters as item (item.id)}
        <button
          type="button"
          class="chip"
          aria-pressed={statusFilter === item.id}
          onclick={() => (statusFilter = item.id)}
        >
          <span class="chip-count">{item.count}</span>
          {item.label}
        </button>
      {/each}
    </div>
    {#if integratedButOff > 0}
      <!-- Why a fresh account shows almost everything off. One sentence, at
           note weight: it was a full-width accent banner competing with the
           controls under it. -->
      <p class="posture-note">
        <Icon name="info" size="sm" />
        <span>
          Capabilities with a real executor start <strong>off</strong> on this account until you
          turn them on. To stop all work instead, use
          <a href="#/settings">Settings → Runtime configuration</a>.
        </span>
      </p>
    {/if}
  </section>

  {#if !filtering && attention.length > 0}
    <!-- What needs a decision comes before what is merely configured. Narrow on
         purpose — a capability sitting at its default is not attention, and a
         page that calls everything attention has said nothing. -->
    <section class="panel panel-attention" aria-label="Needs your attention">
      <h2>Needs your attention</h2>
      <ul class="shortcuts">
        {#each attention as item (item.capability)}
          <li>
            <span class="shortcut-text">
              <span class="cap-label">{item.label}</span>
              <span class="cap-summary">{item.reason}</span>
            </span>
            <!-- The section says a decision wants a second look, so it offers
                 the place to make it (NEW-PERM-01). -->
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
    <section class="panel" aria-label="Common permissions">
      <h2>Common permissions</h2>
      <ul class="shortcuts">
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
  <section class="panel registry" aria-label="All permissions">
    <div class="registry-heading">
      <div>
        <h2>All permissions</h2>
        <p aria-live="polite">Showing {visibleCount} of {governedGates.length} permissions</p>
      </div>
      <!-- One toolbar: find, narrow, fold, reset. The search sat in a band of
           its own two sections above this heading, so the control and the list
           it filtered were not on screen together. -->
      <div class="registry-filters">
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
        <label class="sr-only" for="cap-group">Permission group</label>
        <select id="cap-group" bind:value={domainFilter}>
          <option value="all">All groups</option>
          {#each domains as domain}<option value={domain}>{domain}</option>{/each}
        </select>
        <button type="button" class="btn btn-ghost btn-sm" onclick={() => collapsedDomains = []}>Expand groups</button>
        <button type="button" class="btn btn-ghost btn-sm" disabled={searching} onclick={() => collapsedDomains = [...domains]}>Collapse groups</button>
        {#if filtering}<button type="button" class="btn btn-ghost btn-sm" onclick={clearFilters}>Clear filters</button>{/if}
      </div>
    </div>

    {#if selectedCaps.size > 0}
      <div class="bulk-bar" role="toolbar" aria-label="Bulk capability actions">
        <span class="bulk-count">{selectedCaps.size} selected</span>
        <button type="button" class="btn btn-ghost btn-sm" onclick={() => (selectedCaps = new Set())} disabled={mutationBusy}>Clear</button>
        <span class="bulk-label">Set all to:</span>
        <!-- REM-PERM-02 — the same words the controls below use. These two said
             "Ask" and "Deny" about the values every other control on the page
             calls "Ask me" and "Never", so one policy had two names on one
             screen. -->
        <button type="button" class="btn btn-sm" onclick={() => void bulkSetMode("ask")} disabled={mutationBusy}>{BEHAVIOUR_COPY.ask.label}</button>
        <button type="button" class="btn btn-sm btn-danger" onclick={() => void bulkSetMode("deny")} disabled={mutationBusy}>{BEHAVIOUR_COPY.deny.label}</button>
      </div>
    {/if}

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
          <PermissionRow
            {gate}
            open={expanded === gate.capability}
            selected={selectedCaps.has(gate.capability)}
            busy={mutationBusy}
            modes={controlModes}
            toggleId={rowToggleId(gate.capability)}
            onToggleOpen={toggleExpand}
            onToggleSelect={toggleCapSelected}
            onDecision={(capability, mode) => void setMode(capability, mode)}
            onEnable={startEnable}
            onDisable={startDisable}
          />
        {/each}
      </div>
    {/each}
  </section>

  {#if notDecidedHere.length > 0}
    <!--
      GEP-04, second answer. These gates exist, and flipping them decides
      nothing: either nothing in the product reaches the executor, or the work
      runs under a different named control. They used to sit in the registry
      with a grey chip and a full set of mode buttons, so a quarter of a page of
      decisions was not decisions — and an owner could set one, select it for a
      bulk change, and come away believing they had closed something.

      They are not hidden. Hiding a capability an owner can ask about is its own
      dishonesty, and the note is the answer they actually need: what really
      governs this, or why nothing runs.
    -->
    <details class="panel not-decided">
      <summary>
        Not decided here
        <span class="not-decided-count">{notDecidedHere.length}</span>
      </summary>
      <p class="not-decided-lead">
        Raiker reports a gate for each of these, and this page does not decide them: the work runs
        under a different control, or nothing in Raiker reaches it yet. They are listed so the
        answer is here rather than missing.
      </p>
      <ul class="not-decided-list">
        {#each notDecidedHere as item (item.capability)}
          <li>
            <span class="not-decided-head">
              <span class="cap-label">{item.label}</span>
              <span class="cap-reality">{item.reality}</span>
            </span>
            <p>{item.note}</p>
          </li>
        {/each}
      </ul>
    </details>
  {/if}

  {#if authorityGates.length > 0}
    <!-- REM-PERM-01 — evidence, not the owner's first task. The read-only
         table used to sit above every control on the page; it is reference for
         a question an owner asks second, so it reads second, and closed. -->
    <details class="panel authority-disclosure">
      <summary>How your permissions apply</summary>
      <AuthorityMatrix gates={authorityGates} total={governedGates.length} />
    </details>
  {/if}
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
  /* One column of panels, each with the same padding, radius and border, so the
     page reads as one surface rather than as seven bands that each invented
     their own. */
  .perm-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4);
    margin-bottom: var(--space-4);
    flex-wrap: wrap;
  }
  .lede {
    margin: 0;
    color: var(--text-2);
    font-size: var(--text-md);
  }
  .head-actions {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  .panel {
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    background: var(--surface);
    padding: var(--space-4);
    margin-bottom: var(--space-4);
  }
  .panel h2 {
    margin: 0 0 var(--space-3);
    font-size: var(--text-md);
  }
  .posture {
    display: grid;
    gap: var(--space-3);
  }
  .posture-line {
    margin: 0;
    color: var(--text-1);
    font-size: var(--text-base);
  }
  .chip-count {
    font-variant-numeric: tabular-nums;
    font-weight: 700;
    margin-right: 0.3rem;
  }
  .posture-note {
    display: flex;
    align-items: flex-start;
    gap: var(--space-2);
    margin: 0;
    padding-top: var(--space-3);
    border-top: 1px solid var(--border);
    color: var(--text-2);
    font-size: var(--text-sm);
  }
  .posture-note a {
    color: var(--accent);
    font-weight: 600;
  }
  /* The one panel that is about something unresolved keeps a marker, in text
     weight rather than in a fill: a page where a section shouts is a page where
     the shout stops meaning anything. */
  .panel-attention {
    border-inline-start: 3px solid var(--warn);
  }
  .shortcuts {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
  }
  .shortcuts li {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    flex-wrap: wrap;
    padding: var(--space-2) 0;
    border-bottom: 1px solid var(--border);
  }
  .shortcuts li:last-child {
    border-bottom: 0;
    padding-bottom: 0;
  }
  .shortcut-text {
    display: flex;
    align-items: baseline;
    gap: var(--space-3);
    flex: 1 1 12rem;
    min-width: 0;
    flex-wrap: wrap;
  }
  .cap-label {
    font-weight: 600;
  }
  .cap-summary {
    color: var(--text-3);
    font-size: var(--text-xs);
  }
  .registry-heading {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    flex-wrap: wrap;
    gap: var(--space-3);
    margin-bottom: var(--space-3);
  }
  .registry-heading h2 {
    margin: 0;
  }
  .registry-heading p {
    font-size: var(--text-sm);
    color: var(--text-3);
    margin: var(--space-1) 0 0;
  }
  .registry-filters {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
  .registry-filters select {
    font: inherit;
    font-size: var(--text-sm);
    color: var(--text-1);
    background: var(--surface);
    border: 1px solid var(--border-strong);
    border-radius: var(--r-sm);
    padding: var(--space-2);
    max-width: 100%;
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
    min-width: 14rem;
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
  .bulk-bar {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--accent-border);
    border-radius: var(--r-md);
    background: var(--accent-soft);
    margin-bottom: var(--space-3);
  }
  .bulk-count {
    font-weight: 700;
    color: var(--accent);
    font-size: var(--text-sm);
  }
  .bulk-label {
    color: var(--text-3);
    font-size: var(--text-sm);
    margin-left: 0.3rem;
  }
  .cap-list {
    display: flex;
    flex-direction: column;
    margin-bottom: var(--space-4);
  }
  /* The group's last hairline would double the next group heading's rule. */
  .cap-list :global(.cap.card:last-child) {
    border-bottom: 0;
  }
  .cap-list:last-child {
    margin-bottom: 0;
  }
  /* A group heading, not another card: the rows underneath carry the surface. */
  .phase-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-1) var(--space-2);
    border-bottom: 1px solid var(--border-strong);
  }
  .phase-fold {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    border: 0;
    padding: 0.15rem 0.2rem;
    background: transparent;
    color: var(--text-3);
    cursor: pointer;
  }
  .phase-fold:hover {
    color: var(--text-1);
  }
  .phase-count {
    font-size: var(--text-2xs);
    font-variant-numeric: tabular-nums;
  }
  /* VIS-06 — this is a control the owner clicks, not a status chip. */
  .phase-select-all {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: var(--text-xs);
    font-weight: 650;
    letter-spacing: var(--tracking-wide);
    text-transform: uppercase;
    color: var(--text-3);
    cursor: pointer;
  }
  .phase-select-all input {
    accent-color: var(--accent);
  }
  /* The read-only list of gates this page does not decide. Drawn as reference —
     no control, no selection — because that is exactly what it is. */
  .not-decided summary,
  .authority-disclosure summary {
    cursor: pointer;
    color: var(--text-2);
    font-size: var(--text-md);
    font-weight: 650;
  }
  .not-decided-count {
    font-variant-numeric: tabular-nums;
    font-weight: 700;
    color: var(--text-3);
    margin-left: var(--space-2);
  }
  .not-decided-lead {
    margin: var(--space-3) 0 0;
    color: var(--text-2);
    font-size: var(--text-sm);
    max-width: var(--prose-measure);
  }
  .not-decided-list {
    list-style: none;
    margin: var(--space-3) 0 0;
    padding: 0;
    display: grid;
    gap: var(--space-3);
  }
  .not-decided-list li {
    display: grid;
    gap: var(--space-1);
    padding-inline-start: var(--space-3);
    border-inline-start: 2px solid var(--border);
  }
  .not-decided-head {
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
  .not-decided-list p {
    margin: 0;
    color: var(--text-2);
    font-size: var(--text-sm);
    line-height: 1.5;
    max-width: var(--prose-measure);
  }
  .cap-reality {
    font-size: var(--text-2xs);
    font-weight: 700;
    letter-spacing: var(--tracking-wide);
    text-transform: uppercase;
    color: var(--text-3);
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    padding: 0.05rem 0.35rem;
    white-space: nowrap;
  }
  @media (max-width: 700px) {
    .perm-head,
    .registry-heading {
      flex-direction: column;
      align-items: stretch;
    }
    .registry-filters {
      width: 100%;
    }
    .search {
      flex: 1 1 100%;
    }
  }
</style>
