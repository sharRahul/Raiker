<script lang="ts">
  /**
   * When planned work runs, and how — one composer control.
   *
   * FIXED-1389 — the Tasks composer stacked three rows of pills above its
   * input (templates, timing, run mode), each pill a different shape from the
   * composer's own controls, and a fourth "Runs now" control in the bar that
   * opened a details panel. The two questions now live behind one control in
   * the bar, drawn like the `+` and Tools menus beside it, and its label still
   * says what was chosen — a closed menu never hides the timing.
   */
  import Icon from "./Icon.svelte";

  interface Choice {
    id: string;
    label: string;
  }

  let {
    timing = $bindable(),
    runMode = $bindable(),
    timings,
    runModes,
    summary,
    detailsOpen = $bindable(false),
    disabled = false,
  }: {
    timing: string;
    runMode: string;
    timings: readonly Choice[];
    runModes: readonly Choice[];
    /** The chosen timing in one line, shown on the trigger. */
    summary: string;
    /** Whether the schedule and organisation fields are showing. */
    detailsOpen?: boolean;
    disabled?: boolean;
  } = $props();

  let open = $state(false);
  let root = $state<HTMLDivElement>();
  let trigger = $state<HTMLButtonElement>();

  const HINTS: Record<string, string> = {
    now: "Starts as soon as you create it.",
    at: "Runs once, at the time you set.",
    repeating: "Runs on a schedule until you stop it.",
    single: "One pass, then reports back.",
    background: "Keeps working in the background until it is done.",
  };

  function chooseTiming(id: string) {
    timing = id;
    // A start time is required for both scheduled kinds, and it lives in the
    // details: open them rather than leave Create disabled for a field the
    // owner cannot see.
    if (id !== "now") detailsOpen = true;
  }

  $effect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (root !== undefined && !root.contains(event.target as Node)) open = false;
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.stopPropagation();
      open = false;
      trigger?.focus();
    };
    window.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKey, true);
    return () => {
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKey, true);
    };
  });
</script>

<div class="schedule-menu" bind:this={root}>
  <button
    type="button"
    class="composer-control schedule-toggle"
    aria-haspopup="dialog"
    aria-expanded={open}
    aria-controls="task-schedule-menu"
    {disabled}
    bind:this={trigger}
    onclick={() => (open = !open)}
  >
    <Icon name="clock" size="sm" />
    <span class="summary">{summary}</span>
    <Icon name="chevron-down" size="sm" />
  </button>

  {#if open}
    <div class="sheet-scrim" role="presentation" onclick={() => (open = false)}></div>
    <div class="menu menu-surface" id="task-schedule-menu" role="dialog" aria-label="Schedule">
      <div class="section" role="group" aria-label="When to run">
        <p class="menu-heading">When</p>
        <div class="segmented">
          {#each timings as entry (entry.id)}
            <button
              type="button"
              class="segment"
              aria-pressed={timing === entry.id}
              onclick={() => chooseTiming(entry.id)}>{entry.label}</button
            >
          {/each}
        </div>
        <p class="hint">{HINTS[timing] ?? ""}</p>
      </div>
      {#if timing === "now"}
        <div class="section" role="group" aria-label="How it runs">
          <p class="menu-heading">How it runs</p>
          <div class="segmented">
            {#each runModes as entry (entry.id)}
              <button
                type="button"
                class="segment"
                aria-pressed={runMode === entry.id}
                onclick={() => (runMode = entry.id)}>{entry.label}</button
              >
            {/each}
          </div>
          <p class="hint">{HINTS[runMode] ?? ""}</p>
        </div>
      {/if}
      <div class="footer">
        <button
          type="button"
          class="btn btn-ghost btn-sm"
          aria-expanded={detailsOpen}
          aria-controls="task-details"
          onclick={() => (detailsOpen = !detailsOpen)}
        >
          <Icon name="settings" size="sm" />
          {detailsOpen ? "Hide details" : "Title, priority and more…"}
        </button>
        <button type="button" class="btn btn-primary btn-sm" onclick={() => (open = false)}>Done</button>
      </div>
    </div>
  {/if}
</div>

<style>
  .schedule-menu {
    position: relative;
    display: inline-flex;
  }
  .schedule-toggle {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    min-height: 32px;
    max-width: 16rem;
    padding: 0 0.6rem;
    border: 1px solid var(--border);
    border-radius: var(--r-pill);
    background: var(--surface);
    color: var(--text-2);
    font-size: var(--text-xs);
    white-space: nowrap;
    cursor: pointer;
  }
  .schedule-toggle:hover:not(:disabled),
  .schedule-toggle[aria-expanded="true"] {
    border-color: var(--accent-border);
    color: var(--accent);
  }
  .schedule-toggle[aria-expanded="true"] {
    background: var(--accent-soft);
  }
  .schedule-toggle:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .schedule-toggle:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: 1px;
  }
  .summary {
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .menu {
    position: absolute;
    left: 0;
    bottom: calc(100% + 6px);
    z-index: var(--z-popover);
    width: min(20rem, calc(100vw - 2rem));
    display: grid;
    gap: var(--space-3);
    padding: var(--space-3);
    text-align: left;
  }
  .section {
    display: grid;
    gap: 0.4rem;
  }
  .menu-heading {
    margin: 0;
    color: var(--text-3);
    font-size: var(--text-2xs);
    font-weight: 650;
  }
  /* One track, equal segments: the same shape as the page tabs above. */
  .segmented {
    display: grid;
    grid-auto-columns: minmax(0, 1fr);
    grid-auto-flow: column;
    gap: 2px;
    padding: 2px;
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--sunken);
  }
  .segment {
    min-height: 30px;
    padding: 0 0.5rem;
    border: 0;
    border-radius: calc(var(--r-md) - 2px);
    background: transparent;
    color: var(--text-2);
    font-size: var(--text-xs);
    white-space: nowrap;
    cursor: pointer;
  }
  .segment:hover {
    color: var(--text-1);
  }
  .segment[aria-pressed="true"] {
    background: var(--surface);
    color: var(--text-1);
    font-weight: 600;
    box-shadow: var(--shadow-1);
  }
  .segment:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: -2px;
  }
  .hint {
    margin: 0;
    color: var(--text-3);
    font-size: var(--text-2xs);
  }
  .footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
    padding-top: var(--space-2);
    border-top: 1px solid var(--border);
  }
  .footer .btn {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
  }
  .sheet-scrim {
    display: none;
  }
  @media (max-width: 47.9rem) {
    .sheet-scrim {
      display: block;
      position: fixed;
      inset: 0;
      z-index: var(--z-scrim);
      background: var(--overlay);
    }
    .menu {
      position: fixed;
      inset: auto 0 0 0;
      z-index: var(--z-modal);
      width: auto;
      max-width: none;
      border-radius: var(--r-lg) var(--r-lg) 0 0;
      padding: var(--space-4) var(--space-4) var(--space-5);
      box-shadow: var(--shadow-3);
    }
    .segment {
      min-height: 2.5rem;
    }
  }
</style>
