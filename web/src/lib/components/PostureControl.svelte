<script lang="ts">
  /**
   * VIS-08 — governance, summarized to one control, expanded on request.
   *
   * Governance is Raiker's strongest differentiator and the composer was the
   * place it cost the most. Chat and Build each carried the approval-mode
   * control and the execution-environment badge side by side, permanently, so
   * the room under every message the owner ever typed was spent on two
   * configuration surfaces that do not change from one turn to the next. Asking
   * a question looked like operating a control plane.
   *
   * The posture is one chip now:
   *
   *     Local · Asks first
   *
   * and that chip opens the exact same controls, unchanged — the approval-mode
   * control and the environment badge are composed here rather than replaced,
   * so the behaviour, the API calls and their own tests are untouched. Nothing
   * is removed and nothing is one click further away than it was: the chip is a
   * click, and so was opening the approval menu.
   *
   * VIS2-07 — the chip used to open with the constant word "Protected", so a
   * workspace set to approve everything automatically read
   *
   *     Protected · Local · Auto-approve
   *
   * in amber. The colour said "this is a relaxed posture" and the first word
   * said "you are covered", about the same setting, at the same moment. A
   * standing reassurance is not a state: it is true in every state, so it
   * cannot be read as a description of this one, and next to a warning tone it
   * actively misleads.
   *
   * The chip now states only what changed and what it does — where work runs,
   * and what happens when a decision is needed — in the mode's own words. What
   * *does* still hold in every posture has not been deleted; it moved into the
   * popover, where it is a sentence naming the specific protections rather than
   * one adjective standing in for all of them. Everything below that — the full
   * gate matrix — stays on Permissions, which is where a matrix belongs.
   */
  import { onMount } from "svelte";
  import { api } from "../api";
  import { APPROVAL_MODES, type ApprovalMode } from "../approvalMode";
  import type { ExecutionEnvironment } from "../apiTypes";
  import Icon from "./Icon.svelte";
  import ApprovalModeControl from "./ApprovalModeControl.svelte";
  import ExecutionEnvironmentBadge from "./ExecutionEnvironmentBadge.svelte";

  let {
    showEnvironment = true,
    exceptionOnly = false,
  }: {
    /** Chat has no execution environment of its own; Build and Tasks do. */
    showEnvironment?: boolean;
    /**
     * COMPOSER-12 — render only when the posture is not the careful default.
     *
     * A composer at rest should not carry a governance control: the owner is
     * typing, and the policy system is not what they came to think about. What
     * a composer *must* do is say something the moment the posture stops being
     * the cautious one — "approves automatically" is a fact about the next
     * thing they press, and that is exactly when a chip earns its room.
     *
     * The posture stays inspectable either way: Tools carries a permanent entry
     * to Permissions, so nothing is hidden, only quiet while it is ordinary.
     */
    exceptionOnly?: boolean;
  } = $props();

  let open = $state(false);
  let mode = $state<ApprovalMode | null>(null);
  let environment = $state<ExecutionEnvironment | null>(null);
  let environmentUnavailable = $state(false);
  let root = $state<HTMLDivElement>();
  let trigger = $state<HTMLButtonElement>();

  // Read-only summaries. The controls inside the popover own the writes; these
  // exist so the collapsed chip can say something true without opening.
  onMount(() => {
    void (async () => {
      try {
        mode = (await api.composerApprovalMode()).approval_mode;
      } catch {
        mode = null;
      }
    })();
    if (!showEnvironment) return;
    void (async () => {
      try {
        const view = await api.executionEnvironments();
        environment = view.environments.find((item) => item.selected) ?? null;
      } catch {
        environmentUnavailable = true;
      }
    })();
  });

  /** The shortest true thing about where work runs. */
  const whereSummary = $derived.by(() => {
    if (!showEnvironment) return null;
    if (environmentUnavailable) return "Environment unknown";
    if (environment === null) return null;
    return environment.kind === "container" ? "Sandboxed" : "Local";
  });

  /**
   * The shortest true thing about what happens when a decision is needed.
   *
   * Written as what Raiker does, not as how safe that is. "Approves
   * automatically" is a fact the owner can check against what they chose;
   * "Protected" was a verdict on it.
   */
  const askSummary = $derived.by(() => {
    if (mode === null) return null;
    if (mode === "manual") return "Asks first";
    if (mode === "auto") return "Approves automatically";
    if (mode === "skip") return "Raises no approvals";
    return "Declines unattended";
  });

  // VIS-15 — the resting state is neutral. This turns amber only for a posture
  // that is genuinely less careful than the default, so the colour means
  // something the one time it appears.
  const relaxed = $derived(mode === "auto" || mode === "skip");

  const summary = $derived.by(() => {
    const parts = [whereSummary, askSummary].filter((part) => part !== null);
    // Never an empty chip: a posture that could not be read says so, which is a
    // different thing from a posture that is fine.
    return parts.length > 0 ? parts.join(" · ") : "Not readable";
  });

  const modeDetail = $derived(
    APPROVAL_MODES.find((option) => option.mode === mode)?.detail ?? null,
  );

  $effect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (root !== undefined && !root.contains(event.target as Node)) open = false;
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        open = false;
        trigger?.focus();
      }
    };
    window.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKey);
    };
  });
</script>

{#if !exceptionOnly || relaxed}
<div class="posture" bind:this={root}>
  <button
    type="button"
    class="chip"
    class:relaxed
    aria-expanded={open}
    aria-haspopup="dialog"
    aria-label={`Governance posture: ${summary}`}
    bind:this={trigger}
    onclick={() => (open = !open)}
  >
    <Icon name="lock" size="sm" />
    <span class="chip-text">{summary}</span>
    <Icon name="chevron-right" size="sm" />
  </button>

  {#if open}
    <div class="panel motion-enter" role="dialog" aria-label="Governance posture">
      <div class="field">
        <p class="field-label">Approval policy</p>
        <ApprovalModeControl />
        {#if modeDetail}<p class="field-detail">{modeDetail}</p>{/if}
      </div>

      {#if showEnvironment}
        <div class="field">
          <p class="field-label">Where work runs</p>
          <ExecutionEnvironmentBadge />
        </div>
      {/if}

      <!-- VIS2-07 — what holds in *every* posture, named rather than summarised
           as an adjective on the chip. This is the half of "Protected" that was
           worth keeping: it says which protections do not depend on the
           approval mode, so relaxing that mode does not read as switching
           everything off. -->
      <div class="field">
        <p class="field-label">Regardless of this setting</p>
        <p class="field-detail">
          This Raiker runs on your machine and answers only on loopback.
          Capability gates and policy still apply to every action, and every
          action is still recorded.
        </p>
      </div>

      <!-- The full gate matrix lives on Permissions and is not repeated here.
           A summary that grows into the thing it summarizes is not a summary. -->
      <a class="detail-link" href="#/capabilities">
        See every capability and how it must ask
      </a>
    </div>
  {/if}
</div>
{/if}

<style>
  .posture {
    position: relative;
    display: inline-flex;
  }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 0.32rem;
    min-height: 28px;
    padding: 0.25rem 0.55rem;
    border: 1px solid var(--border);
    border-radius: var(--r-pill);
    background: var(--surface);
    color: var(--text-2);
    font-size: var(--text-xs);
    white-space: nowrap;
  }
  .chip:hover {
    color: var(--text-1);
    background: var(--sunken);
  }
  .chip[aria-expanded="true"] :global(svg:last-child) {
    transform: rotate(90deg);
  }
  /* The one coloured state, and only because it is the one worth noticing. */
  .chip.relaxed {
    border-color: var(--warn-border, var(--border));
    color: var(--warn);
  }
  .panel {
    position: absolute;
    bottom: calc(100% + 6px);
    left: 0;
    z-index: 70;
    width: min(22rem, 78vw);
    display: grid;
    gap: var(--space-3);
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--raised);
    box-shadow: var(--shadow-2);
  }
  .field {
    display: grid;
    gap: 0.3rem;
    justify-items: start;
  }
  .field-label {
    margin: 0;
    font-size: var(--text-xs);
    font-weight: 650;
    color: var(--text-1);
  }
  .field-detail {
    margin: 0;
    font-size: var(--text-xs);
    color: var(--text-3);
  }
  .detail-link {
    font-size: var(--text-xs);
  }
  @media (max-width: 720px) {
    .chip-text {
      overflow: hidden;
      text-overflow: ellipsis;
      max-width: 11rem;
    }
  }
</style>
