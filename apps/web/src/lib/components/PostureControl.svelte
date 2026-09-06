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
   *     Protected · Local · Ask first
   *
   * and that chip opens the exact same controls, unchanged — the approval-mode
   * control and the environment badge are composed here rather than replaced,
   * so the behaviour, the API calls and their own tests are untouched. Nothing
   * is removed and nothing is one click further away than it was: the chip is a
   * click, and so was opening the approval menu.
   *
   * The word "Protected" leads because it is the assurance a normal user wants
   * from a glance. The two facts after it are the ones that change what happens
   * to *this* turn. Everything below the fold in the popover — the full gate
   * matrix — stays on Permissions, which is where a matrix belongs.
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
  }: {
    /** Chat has no execution environment of its own; Build and Tasks do. */
    showEnvironment?: boolean;
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

  /** The shortest true thing about what happens when a decision is needed. */
  const askSummary = $derived.by(() => {
    if (mode === null) return null;
    if (mode === "manual") return "Ask first";
    if (mode === "auto") return "Auto-approve";
    if (mode === "skip") return "Skip prompts";
    return "Decline unattended";
  });

  // VIS-15 — the resting state is neutral. This turns amber only for a posture
  // that is genuinely less careful than the default, so the colour means
  // something the one time it appears.
  const relaxed = $derived(mode === "auto" || mode === "skip");

  const summary = $derived(
    ["Protected", whereSummary, askSummary].filter((part) => part !== null).join(" · "),
  );

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

      <div class="field">
        <p class="field-label">Data boundary</p>
        <p class="field-detail">
          This Raiker runs on your machine and answers only on loopback. Anything
          that leaves it is a gated action.
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
