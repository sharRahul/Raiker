<script lang="ts">
  import Badge from "./Badge.svelte";

  let {
    runtimeMode = "—",
    scope = "local · single-user",
    principal = "—",
    ready = false,
    warnings = [],
    fixture = false,
    connecting = false,
  }: {
    runtimeMode?: string;
    scope?: string;
    principal?: string;
    ready?: boolean;
    warnings?: string[];
    fixture?: boolean;
    connecting?: boolean;
  } = $props();
</script>

<div class="runtime-banner" role="status" aria-label="Runtime status">
  <span class="brand">Raiker</span>
  <span class="rb-item"><span class="rb-key">Mode</span> <code>{runtimeMode}</code></span>
  <span class="rb-item"><span class="rb-key">Scope</span> {scope}</span>
  <span class="rb-item"><span class="rb-key">Principal</span> {principal}</span>
  <span class="rb-item">
    <span class="rb-key">Readiness</span>
    {#if connecting}
      <span class="rb-connecting">connecting…</span>
    {:else if ready}<Badge variant="implemented" />{:else}<Badge variant="blocked" />{/if}
  </span>
  {#each warnings as warning (warning)}
    <span class="rb-item rb-warning"><Badge variant="deferred" /> {warning}</span>
  {/each}
  {#if fixture}
    <span class="fixture-tag">FIXTURE DATA — not connected to a runtime</span>
  {/if}
</div>

<style>
  .runtime-banner {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem 1rem;
    font-size: 0.85rem;
    color: #d4d4da;
  }
  .brand {
    font-weight: 700;
    letter-spacing: 0.04em;
    color: #eaeaf0;
  }
  .rb-key {
    color: #8b8b93;
    text-transform: uppercase;
    font-size: 0.68rem;
    letter-spacing: 0.05em;
    margin-right: 0.25rem;
  }
  code {
    color: #cfe5ff;
  }
  .rb-connecting {
    color: #8b8b93;
    font-style: italic;
  }
  .fixture-tag {
    margin-left: auto;
    color: #e6c66a;
    border: 1px dashed #8a6d1f;
    padding: 0.1rem 0.5rem;
    border-radius: 6px;
    font-size: 0.72rem;
  }
</style>
