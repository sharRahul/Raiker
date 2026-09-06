<script lang="ts">
  let { tokens = null, source = null }: { tokens?: number | null; source?: string | null } = $props();
  const label = $derived(tokens
    ? `${new Intl.NumberFormat(undefined, { notation: "compact" }).format(tokens)} context · ${source === "owner" ? "Admin" : source === "provider" ? "Runtime" : "Config"}`
    : "Context capacity unknown");
</script>

<a class:unknown={!tokens} href="#/models?tab=models" aria-label="Model context capacity">{label}</a>

<style>
  a { display:inline-flex; min-height:28px; align-items:center; padding:.25rem .55rem; border:1px solid var(--border); border-radius:var(--r-pill); background:var(--surface); color:var(--text-2); font-size:var(--text-xs); text-decoration:none; white-space:nowrap; } a.unknown { color:var(--warn); }
</style>
