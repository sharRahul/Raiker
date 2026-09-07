<script lang="ts">
  /**
   * One page's way into the guide (BUG-208 slice B).
   *
   * Every surface used to teach on the page, because `docs/guide/` was
   * unreachable from the product and the page was the only place an explanation
   * could live. Slice A gave it a destination; this is how a page points at it.
   *
   * Deliberately quiet. It sits where the page header's paragraph used to be and
   * takes one line instead of five, so the page opens with its own state rather
   * than with an explanation of itself. What it must never become is a second
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
  <a class="guide-link" href={`#/guide?section=${target.slug}`}>
    <Icon name="info" size="sm" />
    <span>{label ?? target.label}</span>
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
