<script lang="ts">
  import type { Snippet } from "svelte";

  let {
    lead, title, actions, children, layout = "workspace",
  }: { lead?: string; title?: Snippet; actions?: Snippet; children: Snippet; layout?: "reading" | "workspace" } = $props();
</script>

<section class="page" class:reading={layout === "reading"} data-layout={layout} data-testid="responsive-page">
  {#if title || actions}
    <div class="heading">
      <div>{#if title}{@render title()}{/if}</div>
      {#if actions}<div class="actions">{@render actions()}</div>{/if}
    </div>
  {/if}
  {#if lead}<p class="lead">{lead}</p>{/if}
  {@render children()}
</section>

<style>
  .page { width: min(100%, 90rem); margin: 0 auto; }
  .page.reading { width: min(100%, 72rem); }
  .heading { display: flex; align-items: start; justify-content: space-between; gap: var(--space-3); }
  .actions { display: flex; gap: var(--space-2); }
  .lead { margin: 0 0 var(--space-4); color: var(--text-2); }
  @media (max-width: 720px) { .page { width: 100%; } .heading { align-items: stretch; flex-direction: column; } }
</style>
