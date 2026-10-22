<script lang="ts">
  import ApprovalModeControl from "../components/ApprovalModeControl.svelte";
  import { goalSummaries } from "../permissionGoals";
  import { onMount, tick } from "svelte";
  import AuthorityMatrix from "../components/AuthorityMatrix.svelte";
  import Icon from "../components/Icon.svelte";
  import PageState from "../components/PageState.svelte";
  import PermissionDetail from "../components/PermissionDetail.svelte";
  import ListDetail from "../components/ListDetail.svelte";
  import RowOverflow from "../components/RowOverflow.svelte";
  import StepUpDialog from "../components/StepUpDialog.svelte";
  import type { StepUpValues } from "../components/StepUpDialog.svelte";
  import GuideLink from "../components/GuideLink.svelte";
  import { api, ApiError } from "../api";
  import type { CapabilityGate } from "../apiTypes";
  import {
    canEnable,
    capabilityDescription,
    capabilityLabel,
    BUILD_PRESET,
    buildPresetPending,
    buildPresetSatisfied,
    enableableTargets,
    capabilityGroup,
    groupGates,
    type RegistryGrouping,
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
  let refreshing = $state(false);
  /**
   * UX-PERM-01 — the registry leads with what each permission is *for*. The
   * technical domains stay one switch away as the advanced view; the choice is
   * this viewer's, so it is remembered in this browser only.
   */
  const GROUPING_KEY = "raiker.permissions.grouping";
  let grouping = $state<RegistryGrouping>(readGrouping());
  function readGrouping(): RegistryGrouping {
    try {
      return window.localStorage.getItem(GROUPING_KEY) === "domain" ? "domain" : "task";
    } catch {
      return "task";
    }
  }
  function chooseGrouping(next: RegistryGrouping) {
    if (next === grouping) return;
    grouping = next;
    // A category from the other grouping names nothing; start from Overview.
    chooseCategory(OVERVIEW_ID);
    try {
      window.localStorage.setItem(GROUPING_KEY, next);
    } catch {
      // Remembering the view is a convenience.
    }
  }

  let notice = $state<{ kind: "ok" | "error"; text: string } | null>(null);

  /*
   * QUI-L06 — categories beside the permissions in them. Overview first, the
   * task groups next, and the system ones last under Advanced. The category is
   * in the address (`?category=`), and the permission open in the detail pane
   * is too (`?item=`, from ListDetail).
   */
  const OVERVIEW_ID = "overview";
  const ADVANCED_ID = "advanced";
  const ADVANCED_GROUP = "System and runtimes";
  function slug(group: string): string {
    return group === ADVANCED_GROUP && grouping === "task"
      ? ADVANCED_ID
      : group.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  }
  function categoryFromHash(): string {
    if (typeof window === "undefined") return OVERVIEW_ID;
    const requested = new URLSearchParams(window.location.hash.split("?", 2)[1] ?? "").get("category");
    return requested !== null && /^[a-z0-9-]{1,64}$/.test(requested) ? requested : OVERVIEW_ID;
  }
  let category = $state(categoryFromHash());
  let selectedCapability = $state<string | null>(null);
  let bulkMode = $state(false);
  function chooseCategory(id: string) {
    if (id !== category) selectedCapability = null;
    category = id;
    selectedCaps = new Set();
    if (typeof window === "undefined") return;
    const next = id === OVERVIEW_ID ? "#/capabilities" : `#/capabilities?category=${id}`;
    if (window.location.hash !== next) history.replaceState(history.state, "", next);
  }
  function categoryIdOf(capability: string): string {
    return slug(capabilityGroup(capability, grouping));
  }

  /*
   * The per-capability decision mode is the primary control here. It arrives
   * inline on each gate (gate.decision_mode) from the single
   * /api/capability-gates read, so there is no per-capability fan-out. A mode
   * the server has confirmed is kept here so the control updates without a full
   * reload.
   *
   * NEW-PERM-02 — `effective` is the read with every confirmation merged in,
   * and every summary on this page derives from it, so a control and the
   * sections above it can never disagree about a capability.
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
  const groups = $derived(groupGates(governedGates, grouping));
  const categories = $derived([
    { id: OVERVIEW_ID, label: "Overview", count: 0, review: 0 },
    ...groups.map((group) => ({
      id: slug(group.domain),
      label: slug(group.domain) === ADVANCED_ID ? "Advanced" : group.domain,
      count: group.gates.length,
      review: group.gates.filter((gate) =>
        attention.some((item) => item.capability === gate.capability),
      ).length,
    })),
  ]);
  const categoryGates = $derived(
    groups.find((group) => slug(group.domain) === category)?.gates ?? [],
  );
  const categoryLabel = $derived(
    categories.find((item) => item.id === category)?.label ?? "Overview",
  );

  /** Record a mode the server has confirmed, for every presentation at once. */
  function recordConfirmed(capability: string, mode: DecisionMode) {
    mutationSeq += 1;
    confirmedModes = confirmMode(confirmedModes, capability, mode, mutationSeq);
  }
  let modeBusyCap = $state<string | null>(null);
  let selectedCaps = $state<Set<string>>(new Set());
  let bulkBusy = $state(false);
  /** BUG-239 — the Build setup preset's own disclosure and in-flight flag. */
  let presetOpen = $state(false);
  let presetBusy = $state(false);

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
    let conflicted = false;
    try {
      for (const cap of [...selectedCaps]) {
        try {
          await api.setCapabilityDecisionMode(cap, mode, "bulk-set via web UI", shownMode(cap));
          recordConfirmed(cap, mode);
          applied.push(cap);
        } catch (e) {
          if (isConflict(e)) conflicted = true;
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
      // A capability changed elsewhere: show what it is now, not what it was.
      if (conflicted) await load();
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

  /**
   * §13.2 item 6 — what this page shows for a capability, sent with a change so
   * the server can refuse it (409 `capability_conflict`) when another tab or
   * device has changed it since. A mode the page cannot read is not claimed.
   */
  function shownMode(capability: string): string | undefined {
    const gate = effective.find((entry) => entry.capability === capability);
    const mode = gate ? modeFor(gate) : "unknown";
    return mode === "unknown" ? undefined : mode;
  }
  function shownState(capability: string): string | undefined {
    return effective.find((entry) => entry.capability === capability)?.state;
  }
  function isConflict(e: unknown): boolean {
    return e instanceof ApiError && e.reasonCode === "capability_conflict";
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
  const mutationBusy = $derived(bulkBusy || presetBusy || modeBusyCap !== null || busy);
  let dialogError = $state<string | null>(null);

  /*
   * BUG-239 — the Build setup preset.
   *
   * The switches a governed coding loop needs, offered once instead of
   * hunted for in a list of sixty-seven. It is not a default: writing to
   * somebody's files is a decision, so the owner sees exactly what it turns on
   * and takes it deliberately.
   *
   * Three things it deliberately does not do. It does not touch a decision
   * mode, so every one of these still asks. It does not call a bulk endpoint —
   * there is none, and inventing one would be the "easy mode API with weaker
   * enforcement" §18.6 refuses; it drives the same per-capability route the
   * row's own **Turn on** uses, so activation requirements, step-up and audit
   * are identical. And it reports per capability, for the reason NEW-PERM-02
   * gave: these are N independent governed mutations and a single sentence
   * about all of them can be untrue about most of them.
   */
  const presetPending = $derived(buildPresetPending(governedGates));
  const presetDone = $derived(
    governedGates.length > 0 && buildPresetSatisfied(governedGates),
  );

  async function applyBuildPreset() {
    if (mutationBusy || presetPending.length === 0) return;
    presetBusy = true;
    notice = null;
    const applied: string[] = [];
    const failed: string[] = [];
    try {
      for (const gate of presetPending) {
        const target = enableableTargets(gate)[0];
        if (!target) {
          failed.push(gate.capability);
          continue;
        }
        try {
          await api.setCapabilityState(gate.capability, {
            target_state: target,
            reason: "Build setup preset via web UI",
          });
          applied.push(gate.capability);
        } catch {
          failed.push(gate.capability);
        }
      }
      const outcome = bulkOutcome(applied, failed);
      if (outcome !== null) notice = outcome;
      presetOpen = failed.length > 0;
      await load();
    } finally {
      presetBusy = false;
    }
  }

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

  function selectable(gates: CapabilityGate[]): string[] {
    return gates.filter(gate => gate.can_current_principal_change).map(gate => gate.capability);
  }
  // A summary of eight, and which eight matters: the alphabetically first eight
  // are capabilities nobody has an opinion about, so on a fresh account the
  // summary said nothing at all. Ranked by authority instead — see
  // `authorityMatrixGates`.
  const authorityGates = $derived(authorityMatrixGates(governedGates));
  const posture = $derived(permissionPosture(governedGates));
  const goals = $derived(goalSummaries(effective));


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
      // of opening nothing.
      notice = {
        kind: "error",
        text: `${capabilityLabel(capability)} has no control in this build, so there is nothing to open.`,
      };
      return;
    }
    bulkMode = false;
    chooseCategory(categoryIdOf(capability));
    selectedCapability = capability;
    await tick();
    // Focus lands on the permission's own control in the detail pane, so the
    // shortcut helps a keyboard user as much as a pointer one.
    const control = document.querySelector<HTMLElement>(
      `.category-pane article[aria-label="${CSS.escape(capabilityLabel(capability))}"] button`,
    );
    control?.focus();
    control?.scrollIntoView?.({ block: "center" });
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
      await api.setCapabilityDecisionMode(capability, mode, "set via web UI", shownMode(capability));
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
      if (isConflict(e)) await load();
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
      if (isConflict(e) && explained) {
        // Nothing the dialog could supply fixes this: the choice was made
        // against a value that is no longer true. Close it and show today's.
        pending = null;
        notice = { kind: "error", text: `${explained.plain} ${explained.remediation}` };
        await load();
        return;
      }
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
        expected_state: shownState(p.capability),
      });
    } else if (p.kind === "disable_cap") {
      await api.disableCapability(p.capability, values.reason, shownState(p.capability));
    } else {
      await api.setCapabilityDecisionMode(p.capability, p.mode, values.reason, shownMode(p.capability));
    }
  }

  function describeSuccess(p: Pending): string {
    if (p.kind === "enable") return `Enabled ${capabilityLabel(p.capability)}.`;
    if (p.kind === "disable_cap") return `Disabled ${capabilityLabel(p.capability)}.`;
    return `${capabilityLabel(p.capability)} is now set to “${BEHAVIOUR_COPY[p.mode].label}”.`;
  }

  onMount(load);
</script>

<!-- QUI-L06 — one line for the active profile, then categories beside the
     permissions in them. The four-way choice is in the detail pane, one
     control at a time. -->
<header class="perm-head">
  <p class="lede" data-testid="permission-profile">
    {#if gates !== null}{posture.sentence}{:else}Choose what Raiker can use, and when it should ask you.{/if}
  </p>
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
    <RowOverflow
      label="permissions"
      items={[
        {
          label: bulkMode ? "Stop selecting" : "Select several",
          run: () => {
            bulkMode = !bulkMode;
            selectedCaps = new Set();
          },
        },
        {
          label: grouping === "task" ? "Group by technical area" : "Group by what it's for",
          run: () => chooseGrouping(grouping === "task" ? "domain" : "task"),
        },
      ]}
    />
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
  <div class="perm-layout">
    <nav class="category-rail" aria-label="Permission categories">
      <ul>
        {#each categories as item (item.id)}
          {#if item.id === ADVANCED_ID}<li class="rail-divider" aria-hidden="true"></li>{/if}
          <li>
            <button
              type="button"
              class="category"
              aria-current={category === item.id ? "page" : undefined}
              onclick={() => chooseCategory(item.id)}
            >
              <span>{item.label}</span>
              {#if item.review > 0}
                <span class="category-review">{item.review} to review</span>
              {:else if item.count > 0}
                <span class="category-count">{item.count}</span>
              {/if}
            </button>
          </li>
        {/each}
      </ul>
    </nav>

    <div class="category-pane">
      {#if category === OVERVIEW_ID}
        {#if goals.some((goal) => goal.verdict !== "not_reported")}
          <!-- UX-PERM-05 — the posture by goal, read-only, in seven plain
               sentences; Change opens the permission that decides it. -->
          <section class="panel goals" aria-label="What Raiker can do for you">
            <h2>What Raiker can do for you</h2>
            <ul class="goal-list">
              {#each goals.filter((goal) => goal.verdict !== "not_reported") as goal (goal.id)}
                <li class="goal goal-{goal.verdict}">
                  <Icon name={goal.verdict === "never" ? "x" : goal.verdict === "unknown" ? "info" : "check"} size="sm" />
                  <span class="goal-sentence">{goal.sentence}</span>
                  {#if goal.firstCapability}
                    <button
                      type="button"
                      class="btn btn-ghost btn-sm"
                      aria-label={`Change: ${goal.sentence}`}
                      onclick={() => void revealCapability(goal.firstCapability ?? "")}
                    >
                      Change
                    </button>
                  {/if}
                </li>
              {/each}
            </ul>
          </section>
        {/if}

        {#if !presetDone && presetPending.length > 0}
          <!-- BUG-239 — the Build setup preset, shown before it is taken. -->
          <section class="panel preset" aria-label="Set up for Build">
            <div class="preset-head">
              <div>
                <h2>Set up for Build</h2>
                <p class="preset-lede">
                  Building needs {BUILD_PRESET.length} permissions. Raiker still asks
                  before each change — this turns them on, not off.
                </p>
              </div>
              <div class="preset-actions">
                <button
                  type="button"
                  class="btn btn-ghost btn-sm"
                  aria-expanded={presetOpen}
                  onclick={() => (presetOpen = !presetOpen)}
                >
                  {presetOpen ? "Hide" : "What this turns on"}
                </button>
                <button
                  type="button"
                  class="btn btn-primary btn-sm"
                  disabled={mutationBusy}
                  onclick={() => void applyBuildPreset()}
                >
                  {presetBusy ? "Turning on…" : `Turn on ${presetPending.length}`}
                </button>
              </div>
            </div>
            {#if presetOpen}
              <ul class="preset-list">
                {#each BUILD_PRESET as row (row.capability)}
                  <li>
                    <span class="cap-label">{capabilityLabel(row.capability)}</span>
                    <span class="preset-what">{row.what}</span>
                    <span class="cap-summary">
                      {presetPending.some((g) => g.capability === row.capability)
                        ? "Off"
                        : "Already on"}
                    </span>
                  </li>
                {/each}
              </ul>
            {/if}
          </section>
        {/if}
        {#if governedGates.length === 0}
          <PageState state="empty" title="No permissions available" detail="Raiker has not reported any permission you can change." />
        {/if}
      {:else if bulkMode}
        <!-- Select several: the category as a checklist, with the bulk bar. -->
        <section class="panel bulk" aria-label="Select several permissions">
          <div class="bulk-bar" role="toolbar" aria-label="Bulk capability actions">
            <span class="bulk-count">{selectedCaps.size} selected</span>
            <button type="button" class="btn btn-ghost btn-sm" onclick={() => toggleSelectAllInGroup(selectable(categoryGates))} disabled={mutationBusy || selectable(categoryGates).length === 0}>
              {allSelectedInGroup(selectable(categoryGates)) ? "Clear all" : "Select all"}
            </button>
            <span class="bulk-label">Set all to:</span>
            <button type="button" class="btn btn-sm" onclick={() => void bulkSetMode("ask")} disabled={mutationBusy || selectedCaps.size === 0}>{BEHAVIOUR_COPY.ask.label}</button>
            <button type="button" class="btn btn-sm btn-danger" onclick={() => void bulkSetMode("deny")} disabled={mutationBusy || selectedCaps.size === 0}>{BEHAVIOUR_COPY.deny.label}</button>
          </div>
          <ul class="bulk-list">
            {#each categoryGates as gate (gate.capability)}
              <li>
                <label>
                  <input
                    type="checkbox"
                    disabled={mutationBusy || !gate.can_current_principal_change}
                    checked={selectedCaps.has(gate.capability)}
                    onchange={() => toggleCapSelected(gate.capability)}
                    aria-label={`Select ${capabilityLabel(gate.capability)}`}
                  />
                  <span class="cap-label">{capabilityLabel(gate.capability)}</span>
                  <span class="cap-summary">{rowSummary(gate, isAvailable(gate))}</span>
                </label>
              </li>
            {/each}
          </ul>
        </section>
      {:else}
        {#if category === ADVANCED_ID}
          <!-- QUI-P02 — the account's approval mode is set here, not on a
               composer: a composer's profile chip only ever asks more. -->
          <section class="panel approval-mode-panel" aria-labelledby="approval-mode-h">
            <h3 id="approval-mode-h">When something needs your decision</h3>
            <p class="posture-note-text">
              For every conversation on this account. A conversation set to Careful still asks.
            </p>
            <ApprovalModeControl />
          </section>
        {/if}
        <ListDetail
          items={categoryGates}
          key={(gate) => gate.capability}
          label={`${categoryLabel} permissions`}
          matches={(gate, query) =>
            `${gate.capability} ${capabilityLabel(gate.capability)} ${capabilityDescription(gate.capability)}`
              .toLowerCase()
              .includes(query)}
          searchLabel="Search permissions"
          storageKey="permissions"
          autoSelectFirst={true}
          bind:selectedId={selectedCapability}
        >
          {#snippet row(gate)}
            <span class="perm-row">
              <span class="cap-label">{capabilityLabel(gate.capability)}</span>
              <span class="cap-summary">
                {rowSummary(gate, isAvailable(gate))}{#if attention.some((item) => item.capability === gate.capability)} · Needs review{/if}
              </span>
            </span>
          {/snippet}
          {#snippet empty()}
            <p class="note">Nothing in this category is reported by this build.</p>
          {/snippet}
          {#snippet detail(gate)}
            <PermissionDetail
              {gate}
              review={attention.find((item) => item.capability === gate.capability)?.reason ?? null}
              busy={mutationBusy}
              modes={controlModes}
              onDecision={(capability, mode) => void setMode(capability, mode)}
              onEnable={startEnable}
              onDisable={startDisable}
            />
          {/snippet}
        </ListDetail>
      {/if}

      {#if category === ADVANCED_ID && !bulkMode}
        {#if integratedButOff > 0}
          <!-- Why a fresh account shows most things off, at note weight. -->
          <p class="posture-note">
            <Icon name="info" size="sm" />
            <span>
              Most capabilities with a real executor start <strong>off</strong> on this account until
              you turn them on. A new account starts with a small set of local, reversible ones
              available — and every one of them still asks.
            </span>
          </p>
        {/if}
        {#if notDecidedHere.length > 0}
          <!-- GEP-04 — gates that decide nothing here. Read-only, listed so
               the answer is here rather than missing. -->
          <details class="panel not-decided">
            <summary>
              Not decided here
              <span class="not-decided-count">{notDecidedHere.length}</span>
            </summary>
            <p class="not-decided-lead">
              Raiker reports a gate for each of these, and this page does not decide them: the work runs
              under a different control, or nothing in Raiker reaches it yet.
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
          <details class="panel authority-disclosure">
            <summary>How your permissions apply</summary>
            <AuthorityMatrix gates={authorityGates} total={governedGates.length} />
          </details>
        {/if}
      {/if}
    </div>
  </div>
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
  /* QUI-L06 — layout B with a category rail: categories on the left, the
     category's permissions and the one open beside them on the right. */
  .perm-layout {
    display: grid;
    grid-template-columns: 13rem minmax(0, 1fr);
    gap: var(--space-5);
    align-items: start;
  }
  .category-rail ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 2px;
  }
  .category {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
    width: 100%;
    min-height: var(--nav-row-h);
    padding: 0 var(--space-3);
    border: 0;
    border-radius: var(--r-sm);
    background: transparent;
    color: var(--text-2);
    font: inherit;
    font-size: var(--text-sm);
    font-weight: 600;
    text-align: left;
    cursor: pointer;
  }
  .category:hover {
    background: var(--sunken);
    color: var(--text-1);
  }
  .category[aria-current="page"] {
    background: var(--accent-soft);
    color: var(--text-1);
  }
  .category-count {
    color: var(--text-3);
    font-variant-numeric: tabular-nums;
    font-weight: 500;
  }
  .category-review {
    color: var(--warn-text);
    font-size: var(--text-xs);
    font-weight: 650;
  }
  .rail-divider {
    height: 1px;
    margin: var(--space-2) var(--space-3);
    background: var(--border);
  }
  .category-pane {
    min-width: 0;
    display: grid;
    gap: var(--space-3);
  }
  .perm-row {
    display: grid;
    gap: 0.1rem;
    min-width: 0;
  }
  .perm-row .cap-summary {
    color: var(--text-3);
    font-size: var(--text-xs);
  }
  .note {
    margin: 0;
    color: var(--text-2);
    font-size: var(--text-sm);
  }
  .bulk-list {
    list-style: none;
    margin: var(--space-3) 0 0;
    padding: 0;
    display: grid;
    gap: 2px;
  }
  .bulk-list label {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: var(--space-3);
    min-height: 44px;
    padding: 0 var(--space-2);
    border-radius: var(--r-sm);
  }
  .bulk-list label:hover {
    background: var(--sunken);
  }
  @media (max-width: 860px) {
    .perm-layout {
      grid-template-columns: 1fr;
    }
  }
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
  .goal-list { display:grid; gap:.4rem; margin:var(--space-2) 0 0; padding:0; list-style:none; }
  .goal { display:flex; align-items:center; gap:var(--space-2); min-width:0; }
  .goal :global(svg) { flex:none; color:var(--ok,var(--text-3)); }
  .goal-never :global(svg) { color:var(--text-3); }
  .goal-unknown :global(svg),.goal-automatic :global(svg) { color:var(--warn,var(--text-3)); }
  .goal-sentence { flex:1; min-width:0; color:var(--text-1); font-size:var(--text-sm); }
  .goal-never .goal-sentence { color:var(--text-2); }
  .goals h2 { margin:0; font-size:var(--text-md); }
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
  .approval-mode-panel {
    display: grid;
    gap: var(--space-2);
    justify-items: start;
    margin-bottom: var(--space-3);
  }
  .approval-mode-panel h3 {
    margin: 0;
    font-size: var(--text-sm);
  }
  .posture-note-text {
    margin: 0;
    color: var(--text-3);
    font-size: var(--text-xs);
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
  /* BUG-239 — the Build preset. Deliberately built from the page's existing
     panel, label and summary vocabulary rather than a banner of its own: it is
     a shortcut through the registry, not a different kind of object. */
  .preset-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: var(--space-3);
    flex-wrap: wrap;
  }
  .preset-lede {
    margin: var(--space-1) 0 0;
    color: var(--text-2);
    font-size: var(--text-sm);
    max-width: var(--prose-measure);
  }
  .preset-actions {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
  .preset-list {
    list-style: none;
    margin: var(--space-3) 0 0;
    padding: 0;
    display: grid;
  }
  .preset-list li {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-3);
    flex-wrap: wrap;
    padding: var(--space-2) 0;
    border-bottom: 1px solid var(--border);
  }
  .preset-list li:last-child {
    border-bottom: 0;
    padding-bottom: 0;
  }
  .preset-what {
    color: var(--text-2);
    font-size: var(--text-sm);
    flex: 1 1 14rem;
    min-width: 0;
  }
  .registry-heading {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    flex-wrap: wrap;
    gap: var(--space-3);
    margin-bottom: var(--space-3);
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
  .grouping{align-items:center;margin:0 0 var(--space-3)}
  .grouping-label{color:var(--text-3);font-size:var(--text-xs)}
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
  /* This is a control the owner clicks, not a status chip. */
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
