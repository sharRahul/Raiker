<script lang="ts">
  /*
   * B17 / C13, 03 Composer execution states (2026-11-07) — the composer's row
   * for a turn that is *already running*.
   *
   * It says what the turn is doing now (from its own events), how long it has
   * run (counted from Send — the one figure a running turn can state
   * truthfully), and opens the step drawer: the turn's own tool calls, each
   * with its state in words. It no longer carries an input or a Stop button:
   * the prompt queues follow-ups while a turn runs, and Send becomes Stop in
   * its own place (`RunSendButton`). Stop and steer are both governed by
   * `RunningTurn`; neither grants anything.
   */
  import Icon from "./Icon.svelte";
  import type { ToolCallRow, ToolCallState } from "../chatPresentation";
  import { elapsedLabel, type RunningTurn } from "../runningTurn.svelte";

  let {
    control,
    activity = "",
    steps = [],
  }: {
    control: RunningTurn;
    /** QUI-C03 — what the turn is doing now, from its own events (`workingLine`). */
    activity?: string;
    /** This turn's tool calls, in call order (`toolActivity`). */
    steps?: readonly ToolCallRow[];
  } = $props();

  const STATE_WORDS: Record<ToolCallState, string> = {
    running: "Running",
    waiting: "Waiting for you",
    success: "Done",
    failed: "Failed",
    denied: "Declined",
    refused: "Refused",
  };
  const STATE_ICON: Record<ToolCallState, "circle" | "clock" | "check" | "warning" | "x"> = {
    running: "circle",
    waiting: "clock",
    success: "check",
    failed: "warning",
    denied: "x",
    refused: "x",
  };

  let drawerOpen = $state(false);
  let now = $state(Date.now());

  $effect(() => {
    if (control.startedAt === null) return;
    now = Date.now();
    const timer = setInterval(() => (now = Date.now()), 1000);
    return () => clearInterval(timer);
  });

  const elapsed = $derived(control.startedAt === null ? "" : elapsedLabel(now - control.startedAt));
  const stepCount = $derived(steps.length);
</script>

<div class="running">
<div class="turn-control" data-testid="turn-control">
  <p class="working-line" role="status" aria-live="polite">
    <span class="activity">{activity !== "" ? `${activity}…` : "Writing the answer…"}</span>
    {#if elapsed !== ""}<span class="elapsed" aria-label={`Running for ${elapsed}`}>{elapsed}</span>{/if}
  </p>
  {#if stepCount > 0}
    <button
      type="button"
      class="btn btn-ghost btn-sm steps-toggle"
      aria-expanded={drawerOpen}
      aria-controls="turn-step-drawer"
      onclick={() => (drawerOpen = !drawerOpen)}
    >
      {stepCount} step{stepCount === 1 ? "" : "s"}
      <Icon name={drawerOpen ? "chevron-up" : "chevron-down"} size="sm" />
    </button>
  {/if}
</div>

{#if drawerOpen && stepCount > 0}
  <ol id="turn-step-drawer" class="step-drawer" aria-label="Steps in this turn">
    {#each steps as step (step.actionId)}
      <li class="step step-{step.state}">
        <Icon name={STATE_ICON[step.state]} size="sm" />
        <span class="step-what">{step.action ? `${step.label} · ${step.action}` : step.label}</span>
        <span class="step-state">{STATE_WORDS[step.state]}</span>
      </li>
    {/each}
  </ol>
{/if}

{#if control.stopping}
  <p class="control-note" role="status">
    Stop requested. The turn ends at its next safe boundary and keeps what it has already done.
  </p>
{/if}
{#if control.error}
  <p class="control-note error" role="alert">{control.error}</p>
{/if}
</div>

<style>
  /* One column across the card: the bar it sits in is a row. */
  .running { display: flex; flex-direction: column; gap: var(--space-1); width: 100%; min-width: 0; }
  .turn-control {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    width: 100%;
    min-width: 0;
  }
  .working-line {
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
    flex: 1 1 auto;
    min-width: 0;
    margin: 0;
    font-size: var(--text-xs);
    color: var(--text-2);
  }
  .activity { min-width: 0; overflow-wrap: anywhere; }
  .elapsed { flex: 0 0 auto; color: var(--text-3); font-variant-numeric: tabular-nums; }
  .steps-toggle { flex: 0 0 auto; gap: var(--space-1); }
  .step-drawer {
    list-style: none;
    margin: 0;
    padding: var(--space-1) 0;
    max-height: 12rem;
    overflow-y: auto;
    border-top: 1px solid var(--border);
    display: grid;
    gap: 2px;
  }
  .step {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: var(--space-2);
    min-height: 2rem;
    padding: 0 var(--space-1);
    font-size: var(--text-xs);
    color: var(--text-2);
  }
  .step-what { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-1); }
  .step-state { color: var(--text-3); }
  .step-failed .step-state, .step-failed :global(svg) { color: var(--danger); }
  .step-waiting .step-state { color: var(--warn-text); }
  .control-note {
    margin: 0;
    font-size: var(--text-sm);
    color: var(--text-2);
  }
  .control-note.error {
    color: var(--danger);
  }
</style>
