<script lang="ts">
  let { state, title, detail = null }: { state: "loading" | "error" | "empty"; title: string; detail?: string | null } = $props();
</script>

<section class:danger={state === "error"} class="state" role={state === "error" ? "alert" : "status"}>
  <strong>{title}</strong>
  {#if detail}<span>{detail}</span>{/if}
</section>

<style>
  .state { display: grid; gap: var(--space-1); padding: var(--space-4); border: 1px solid var(--border); border-radius: var(--r-md); color: var(--text-2); }
  .state strong { color: var(--text-1); }
  .state.danger { border-color: var(--danger-border); background: var(--danger-soft); }
</style>
