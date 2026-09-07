<script lang="ts">
  /**
   * The user guide, inside the product (BUG-208 slice A).
   *
   * `docs/guide/` always held the material the interface was explaining on every
   * screen, and the product could not reach a word of it — the only way in was
   * the README's documentation list, which is not something a person running the
   * app is reading. So the prose stayed on the page, because the page was the
   * only place it could be.
   *
   * This is the destination that makes the rest of BUG-208 possible: with a
   * guide the product can open, a page header that begins "A project is…" has
   * somewhere to move to rather than somewhere to be deleted from.
   *
   * It renders with the same `Markdown` component the transcript uses, so a
   * guide page looks like the rest of Raiker and gains nothing of its own.
   */
  import { onMount } from "svelte";
  import { api } from "../api";
  import type { GuideIndex, GuideSection } from "../apiTypes";
  import Markdown from "../components/Markdown.svelte";
  import EmptyState from "../components/EmptyState.svelte";

  let { section: requested = null }: { section?: string | null } = $props();

  let index = $state<GuideIndex | null>(null);
  let current = $state<GuideSection | null>(null);
  let loading = $state(true);
  let error = $state("");

  /** Load one section. Does not touch the hash — see the effect below. */
  async function load(slug: string) {
    error = "";
    try {
      current = await api.guideSection(slug);
    } catch {
      error = "That guide page could not be opened.";
    }
  }

  /** Clicking a section navigates; the effect below does the loading. */
  function openSection(slug: string) {
    window.location.hash = `#/guide?section=${slug}`;
  }

  onMount(async () => {
    try {
      index = await api.guide();
    } catch {
      error = "The guide could not be loaded.";
    } finally {
      loading = false;
    }
  });

  // Driven by the route, not by the click. A hash change inside the guide does
  // not remount this view, so a deep link arriving while it is already open —
  // which is exactly what a contextual "Learn more" produces — would otherwise
  // leave the reader on whichever page loaded first.
  $effect(() => {
    const catalogue = index;
    if (catalogue === null || !catalogue.available) return;
    const wanted =
      requested !== null && catalogue.sections.some((s) => s.slug === requested)
        ? requested
        : (catalogue.sections[0]?.slug ?? null);
    if (wanted === null || wanted === current?.slug) return;
    void load(wanted);
  });
</script>

<section class="guide" aria-label="Guide">
  {#if loading}
    <p class="muted">Opening the guide…</p>
  {:else if error}
    <p class="error-line" role="alert">{error}</p>
  {:else if index === null || !index.available}
    <!-- A build that shipped no guide says so and names the reason, rather than
         rendering an empty list that reads as "there is nothing to read". -->
    <EmptyState
      title="This build did not ship the guide"
      body="The guide is packaged with Raiker. Set RAIKER_GUIDE_DIR to a checkout's docs/guide to read it here."
    />
  {:else}
    <div class="guide-layout">
      <nav class="guide-sections" aria-label="Guide sections">
        {#each index.sections as section (section.slug)}
          <button
            type="button"
            class:active={current?.slug === section.slug}
            onclick={() => void openSection(section.slug)}
          >
            <strong>{section.title}</strong>
            {#if section.summary}<span>{section.summary}</span>{/if}
          </button>
        {/each}
      </nav>

      <article class="guide-page" aria-live="polite">
        {#if current}
          <Markdown text={current.markdown} />
        {/if}
      </article>
    </div>
  {/if}
</section>

<style>
  .guide {
    display: grid;
    gap: var(--space-4);
  }
  .guide-layout {
    display: grid;
    grid-template-columns: minmax(200px, 260px) minmax(0, 1fr);
    gap: var(--space-5);
    align-items: start;
  }
  .guide-sections {
    display: grid;
    gap: var(--space-1);
    position: sticky;
    top: var(--space-4);
  }
  .guide-sections button {
    display: grid;
    gap: 0.15rem;
    padding: var(--space-3);
    border: 1px solid transparent;
    border-radius: var(--r-md);
    background: transparent;
    color: var(--text-2);
    text-align: left;
    cursor: pointer;
  }
  .guide-sections button:hover {
    background: var(--sunken);
  }
  .guide-sections button.active {
    border-color: var(--accent-border);
    background: var(--accent-soft);
  }
  .guide-sections strong {
    color: var(--text-1);
    font-size: var(--text-md);
  }
  .guide-sections span {
    color: var(--text-3);
    font-size: var(--text-xs);
    line-height: 1.35;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
  }
  .guide-page {
    min-width: 0;
    padding: var(--space-5);
    border: 1px solid var(--neutral-border);
    border-radius: var(--r-lg);
    background: var(--surface);
  }
  .muted {
    color: var(--text-3);
  }
  @media (max-width: 900px) {
    .guide-layout {
      grid-template-columns: minmax(0, 1fr);
    }
    .guide-sections {
      position: static;
    }
  }
</style>
