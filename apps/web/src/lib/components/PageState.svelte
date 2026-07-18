<script lang="ts">
  let { state, title, detail = null }: { state: "loading" | "error" | "empty"; title: string; detail?: string | null } = $props();
</script>

<section
  class="state"
  class:danger={state === "error"}
  class:quiet={state === "loading"}
  role={state === "error" ? "alert" : "status"}
>
  {#if state === "loading"}<span class="dot" aria-hidden="true"></span>{/if}
  <strong>{title}</strong>
  {#if detail}<span class="detail">{detail}</span>{/if}
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
