<script lang="ts">
  // BUG-37 — loading as a shape, not only a sentence.
  //
  // A pulsing dot next to "Loading tasks…" tells you something is happening and
  // nothing about what is coming, so the page jumps when it arrives. `lines`
  // opts a loading state into a skeleton of the shape that is about to replace
  // it, which holds the space and sets the expectation. The one-line form stays
  // the default: where the eventual shape is genuinely unknown, drawing a fake
  // one would be a guess dressed up as information.
  //
  // Error and empty are unchanged in behaviour — `role="alert"` for an error a
  // screen reader must hear now, `role="status"` for everything else.
  let {
    state,
    title,
    detail = null,
    lines = 0,
  }: {
    state: "loading" | "error" | "empty";
    title: string;
    detail?: string | null;
    /** Draw this many skeleton rows under a loading state. 0 keeps the line form. */
    lines?: number;
  } = $props();
</script>

<section
  class="state"
  class:danger={state === "error"}
  class:quiet={state === "loading" && lines === 0}
  class:skeletal={state === "loading" && lines > 0}
  role={state === "error" ? "alert" : "status"}
>
  {#if state === "loading" && lines === 0}<span class="dot" aria-hidden="true"></span>{/if}
  <strong>{title}</strong>
  {#if detail}<span class="detail">{detail}</span>{/if}
  {#if state === "loading" && lines > 0}
    <div class="skeleton-rows" aria-hidden="true">
      {#each Array.from({ length: lines }, (_, index) => index) as row (row)}
        <div class="skeleton skeleton-line"></div>
      {/each}
    </div>
  {/if}
</section>

<style>
  .state {
    display: grid;
    gap: var(--space-1);
    padding: var(--space-4);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    color: var(--text-2);
  }
  .state strong { color: var(--text-1); }
  .state.danger {
    border-color: var(--danger-border);
    background: var(--danger-soft);
  }
  .state.danger strong { color: var(--danger); }
  .state.quiet {
    grid-template-columns: auto 1fr;
    align-items: center;
    gap: var(--space-2);
    border-color: transparent;
    padding: var(--space-3) 0;
  }
  .state.quiet strong { color: var(--text-2); font-weight: 600; }
  /* The skeleton form carries its own heading, so the border would be a second
     frame around a block that is already shaped like the content it replaces. */
  .state.skeletal {
    border-color: transparent;
    padding: var(--space-3) 0;
  }
  .state.skeletal strong { color: var(--text-3); font-size: var(--text-sm); font-weight: 600; }
  .skeleton-rows { margin-top: var(--space-3); }
  .dot {
    width: 0.55rem;
    height: 0.55rem;
    border-radius: 50%;
    background: var(--accent);
    animation: pulse 1.1s ease-in-out infinite alternate;
  }
  @keyframes pulse {
    from { opacity: 0.35; transform: scale(0.8); }
    to { opacity: 1; transform: scale(1); }
  }
</style>
