<script lang="ts">
  import type { Snippet } from "svelte";

  type PageLayout = "reading" | "workspace" | "operational" | "work-surface";

  let {
    lead, title, actions, children, layout = "workspace",
  }: { lead?: string; title?: Snippet; actions?: Snippet; children: Snippet; layout?: PageLayout } = $props();
</script>

<section class={`page ${layout}`} data-layout={layout} data-testid="responsive-page">
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
  .page {
    width: min(100%, var(--page-workspace));
    margin: 0 auto;
    display: grid;
    grid-template-columns: repeat(var(--grid-columns), minmax(0, 1fr));
    column-gap: var(--grid-gap);
  }
  .page > :global(*) { grid-column: 1 / -1; }
  .page.reading { width: min(100%, var(--page-reading)); }
  .page.reading :global(.page-lead), .page.reading > :global(p) { max-width: var(--prose-measure); }
  .page.operational { width: min(100%, var(--page-operational)); }
  .page.work-surface { width: 100%; min-height: var(--content-h); }
  .page.work-surface > :global(*) { min-height: 0; }
  .heading { display: flex; align-items: start; justify-content: space-between; gap: var(--space-3); }
  .actions { display: flex; gap: var(--space-2); }
  .lead { margin: 0 0 var(--space-4); color: var(--text-2); }
  @media (max-width: 720px) { .page { width: 100%; display: block; } .heading { align-items: stretch; flex-direction: column; } }
</style>
