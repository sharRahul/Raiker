<script lang="ts">
  /**
   * One page's way into the guide (BUG-208 slice B).
   *
   * The guide is the destination for explanation; this is how a page points at
   * it. Deliberately quiet — one line — so the page opens with its own state
   * rather than with an explanation of itself. What it must never become is a second
   * place to write prose: the label names the section, and the section carries
   * the words.
   */
  import Icon from "./Icon.svelte";
  import { guideSectionFor, type GuideTarget } from "../guideSections";

  let {
    /** The route this link sits on; its section is resolved from the map. */
    route,
    /** Overrides the map, for a panel whose subject is not its route's. */
    section = null,
    /** Overrides the label, when "How X works" reads better than the title. */
    label = null,
  }: { route?: string; section?: string | null; label?: string | null } = $props();

  const target = $derived<GuideTarget | null>(
    section !== null
      ? { slug: section, label: label ?? `How ${section.replace(/-/g, " ")} works` }
      : route !== undefined
        ? guideSectionFor(route)
        : null,
  );
</script>

{#if target !== null}
  <!-- Quiet UI — an icon with its words as the accessible name and tooltip,
       so a page opens with its own content rather than a sentence about it. -->
  <a class="guide-link" href={`#/guide?section=${target.slug}`} aria-label={label ?? target.label} title={label ?? target.label}>
    <Icon name="info" size="sm" />
  </a>
{/if}

<style>
  .guide-link {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    color: var(--text-3);
    font-size: var(--text-sm);
    text-decoration: none;
    border-radius: var(--r-pill);
  }
  .guide-link:hover {
    color: var(--text-1);
    text-decoration: underline;
  }
</style>
