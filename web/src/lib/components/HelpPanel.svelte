<script lang="ts">
  /**
   * QUI-L05 — layout E, the help panel.
   *
   * 360 px beside the page, opened from **?**, starting on the article for the
   * page you are on, with search over every article. It replaces the Guide
   * page: each chapter of `docs/guide/` is one article with its own address
   * (`#/guide?section=<slug>`), so an old link still lands on what it named.
   *
   * It renders a chapter with the same `Markdown` the transcript uses, and the
   * same cross-reference rewriting the Guide page used (BUG-301), so a link in
   * one article opens the other here rather than a page that no longer exists.
   */
  import { tick } from "svelte";
  import { api } from "../api";
  import type { GuideIndex, GuideSection } from "../apiTypes";
  import Icon from "./Icon.svelte";
  import Markdown from "./Markdown.svelte";
  import { closeHelp, help } from "../help.svelte";
  import { guideSectionFor } from "../guideSections";
  import { resolveGuideLinks } from "../guideLinks";

  let { current }: { current: string } = $props();

  let index = $state<GuideIndex | null>(null);
  let article = $state<GuideSection | null>(null);
  let query = $state("");
  let error = $state("");
  let panel = $state<HTMLElement>();
  let returnFocusTo: HTMLElement | null = null;

  const slugs = $derived(new Set((index?.sections ?? []).map((section) => section.slug)));
  const pageArticle = $derived(guideSectionFor(current));
  const matches = $derived.by(() => {
    const words = query.trim().toLowerCase();
    const sections = index?.sections ?? [];
    if (words === "") return sections;
    return sections.filter((section) =>
      `${section.title} ${section.summary ?? ""} ${section.slug.replace(/-/g, " ")}`
        .toLowerCase()
        .includes(words),
    );
  });

  async function loadIndex() {
    if (index !== null) return;
    try {
      index = await api.guide();
    } catch {
      error = "Help could not be loaded. Check that Raiker is running, then open it again.";
    }
  }

  async function show(slug: string | null) {
    error = "";
    if (slug === null) {
      article = null;
      return;
    }
    try {
      article = await api.guideSection(slug);
    } catch {
      article = null;
      error = "That article could not be opened. Choose another from the list.";
    }
  }

  // Open: remember what had focus, read the index, and show the article asked
  // for — or this page's own — then put the keyboard in the panel.
  $effect(() => {
    if (!help.open) return;
    returnFocusTo = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    query = "";
    const wanted = help.slug ?? pageArticle?.slug ?? null;
    void loadIndex().then(() => show(wanted)).then(async () => {
      await tick();
      panel?.querySelector<HTMLElement>("[data-help-focus]")?.focus();
    });
    const onKeydown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.stopPropagation();
      close();
    };
    window.addEventListener("keydown", onKeydown);
    return () => window.removeEventListener("keydown", onKeydown);
  });

  function close() {
    closeHelp();
    returnFocusTo?.focus();
  }
</script>

{#if help.open}
  <aside class="help-panel" aria-label="Help" bind:this={panel}>
    <header>
      <h2>Help</h2>
      <button type="button" class="btn btn-ghost btn-sm" aria-label="Close help" onclick={close}>
        <Icon name="x" size="sm" />
      </button>
    </header>
    <label class="help-search">
      <Icon name="search" size="sm" />
      <span class="sr-only">Search help</span>
      <input
        type="search"
        placeholder="Search help"
        bind:value={query}
        data-help-focus
        oninput={() => (article = null)}
      />
    </label>

    {#if error}<p class="help-error" role="alert">{error}</p>{/if}

    <div class="help-body" aria-live="polite">
      {#if article !== null}
        <button type="button" class="btn btn-ghost btn-sm back" onclick={() => (article = null)}>
          <Icon name="chevron-left" size="sm" /> All articles
        </button>
        <article class="help-article" aria-label={article.title}>
          <!-- BUG-301 — the text is the product's own and its targets were
               resolved against the article list before they got here. -->
          <Markdown text={resolveGuideLinks(article.markdown, slugs)} inAppLinks />
        </article>
      {:else if index !== null && !index.available}
        <p class="muted">
          This build did not ship its help articles. Set RAIKER_GUIDE_DIR to a checkout's
          docs/guide to read them here.
        </p>
      {:else if index !== null}
        {#if pageArticle !== null && query.trim() === ""}
          <p class="on-this-page">
            On this page:
            <button type="button" class="link" onclick={() => void show(pageArticle.slug)}>
              {pageArticle.label}
            </button>
          </p>
        {/if}
        <ul class="help-list" aria-label="Help articles">
          {#each matches as section (section.slug)}
            <li>
              <button type="button" onclick={() => void show(section.slug)}>
                <strong>{section.title}</strong>
                {#if section.summary}<span>{section.summary}</span>{/if}
              </button>
            </li>
          {:else}
            <li class="muted">No article matches “{query}”.</li>
          {/each}
        </ul>
      {:else}
        <p class="muted">Opening help…</p>
      {/if}
    </div>
  </aside>
{/if}

<style>
  .help-panel {
    position: fixed;
    top: var(--topbar-h);
    right: 0;
    bottom: 0;
    z-index: var(--z-popover);
    width: min(360px, 100vw);
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    padding: var(--space-4);
    border-left: 1px solid var(--border);
    background: var(--surface);
    box-shadow: var(--shadow-2);
    overflow: hidden;
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  header h2 {
    margin: 0;
    font-size: var(--text-lg);
  }
  .help-search {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: 0 var(--space-3);
    min-height: var(--control-normal);
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    color: var(--text-3);
  }
  /* The frame is the field: focus marks the frame, not a second box inside it. */
  .help-search:focus-within {
    outline: 2px solid var(--focus-ring);
    outline-offset: 1px;
  }
  .help-search input,
  .help-search input:focus-visible {
    box-shadow: none;
    min-height: 0;
    padding: 0;
  }
  .help-search input {
    flex: 1;
    min-width: 0;
    border: 0;
    outline: 0;
    background: transparent;
    color: var(--text-1);
    font: inherit;
  }
  .help-body {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
  }
  .back {
    margin-bottom: var(--space-2);
  }
  .help-article {
    font-size: var(--text-sm);
  }
  .on-this-page {
    margin: 0 0 var(--space-3);
    color: var(--text-2);
    font-size: var(--text-sm);
  }
  .link {
    border: 0;
    padding: 0;
    background: none;
    color: var(--accent);
    font: inherit;
    cursor: pointer;
    text-decoration: underline;
  }
  .help-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 2px;
  }
  .help-list button {
    display: grid;
    gap: 0.15rem;
    width: 100%;
    padding: var(--space-2) var(--space-3);
    border: 0;
    border-radius: var(--r-sm);
    background: transparent;
    color: var(--text-1);
    font: inherit;
    text-align: left;
    cursor: pointer;
  }
  .help-list button:hover {
    background: var(--sunken);
  }
  .help-list span {
    color: var(--text-2);
    font-size: var(--text-sm);
  }
  .muted {
    color: var(--text-3);
    font-size: var(--text-sm);
  }
  .help-error {
    margin: 0;
    color: var(--danger);
    font-size: var(--text-sm);
  }
</style>
