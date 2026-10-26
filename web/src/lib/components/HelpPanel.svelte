<script lang="ts">
  /**
   * QUI-L05 — layout E, the help panel.
   *
   * 360 px beside the page, opened from **?**, starting on the article for the
   * page you are on, with search over every article. It replaces the Guide
   * page: each chapter of `docs/guide/` is one article with its own address
   * (`#/guide?section=<slug>`), so an old link still lands on what it named.
   *
   * An article opens as its intro and a list of its parts, and a part opens on
   * its own (`&part=<id>`). The panel never puts a whole chapter in front of
   * the owner: `working-in-chat.md` runs to 900 lines, and someone who pressed
   * **?** on the approvals card came for the 80 about approvals. Search reaches
   * the parts too, so a query lands on the heading that answers it.
   *
   * It renders with the same `Markdown` the transcript uses, and the same
   * cross-reference rewriting the Guide page used (BUG-301), so a link in one
   * article opens the other here rather than a page that no longer exists.
   */
  import { tick, untrack } from "svelte";
  import { api } from "../api";
  import type { GuideIndex, GuideSection } from "../apiTypes";
  import Icon from "./Icon.svelte";
  import Markdown from "./Markdown.svelte";
  import { closeHelp, help } from "../help.svelte";
  import { guideSectionFor } from "../guideSections";
  import { resolveGuideLinks, unwrapGuideProse } from "../guideLinks";

  let { current }: { current: string } = $props();

  interface Match {
    key: string;
    slug: string;
    part: string;
    title: string;
    within: string;
    summary: string;
  }

  /** The most results a search lists; past this the query wants another word. */
  const MAX_MATCHES = 20;

  let index = $state<GuideIndex | null>(null);
  let article = $state<GuideSection | null>(null);
  let query = $state("");
  let error = $state("");
  let panel = $state<HTMLElement>();
  let returnFocusTo: HTMLElement | null = null;
  // Each load and each keystroke in search takes a number; a load that comes
  // back after a newer one started is dropped, so an article still loading
  // cannot land over the results the owner has started typing for.
  let latest = 0;

  const slugs = $derived(new Set((index?.sections ?? []).map((section) => section.slug)));
  const pageArticle = $derived(guideSectionFor(current));
  const matches = $derived.by((): Match[] => {
    const words = query.trim().toLowerCase();
    const sections = index?.sections ?? [];
    const articles = sections.map((section) => ({
      key: section.slug,
      slug: section.slug,
      part: "",
      title: section.title,
      within: "",
      summary: section.summary ?? "",
    }));
    if (words === "") return articles;
    const hit = (text: string) => text.toLowerCase().includes(words);
    const found = articles.filter((item) => hit(`${item.title} ${item.summary} ${item.slug.replace(/-/g, " ")}`));
    for (const section of sections) {
      for (const part of section.parts ?? []) {
        if (!hit(`${part.title} ${part.summary}`)) continue;
        found.push({
          key: `${section.slug}#${part.id}`,
          slug: section.slug,
          part: part.id,
          title: part.title,
          within: section.title,
          summary: part.summary,
        });
      }
    }
    return found.slice(0, MAX_MATCHES);
  });
  // Where a part sits in its article, so the reader can step to the next one
  // without going back to the list.
  const position = $derived.by(() => {
    if (article === null || article.part === "") return null;
    const parts = article.parts ?? [];
    const at = parts.findIndex((part) => part.id === article?.part);
    return { previous: parts[at - 1] ?? null, next: parts[at + 1] ?? null };
  });

  async function loadIndex() {
    if (index !== null) return;
    try {
      index = await api.guide();
    } catch {
      error = "Help could not be loaded. Check that Raiker is running, then open it again.";
    }
  }

  async function show(slug: string | null, part = "") {
    error = "";
    const mine = ++latest;
    if (slug === null) {
      article = null;
      return;
    }
    try {
      const found = await api.guideSection(slug, part ? { part } : {});
      if (mine !== latest) return;
      article = found;
    } catch {
      if (mine !== latest) return;
      // A part that moved or was renamed still has an article to land on.
      if (part !== "") return show(slug);
      article = null;
      error = "That article could not be opened. Choose another from the list.";
    }
    await tick();
    panel?.querySelector<HTMLElement>(".help-body")?.scrollTo?.({ top: 0 });
  }

  function open(match: Match) {
    query = "";
    void show(match.slug, match.part);
  }

  // Open: remember what had focus, read the index, and show the article asked
  // for — or this page's own — then put the keyboard in the panel. A link
  // followed inside the panel reopens it on another article; focus stays put.
  $effect(() => {
    if (!help.open) return;
    const asked = help.slug;
    const askedPart = help.part;
    // Only the request reopens the panel. Everything else this reads (the
    // panel element once it binds, the article it is about to replace) is
    // untracked: reading it here reran the open and put the first part back
    // over whatever the owner had just chosen.
    untrack(() => {
      const focused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      if (focused === null || !panel?.contains(focused)) returnFocusTo = focused;
      query = "";
      const wanted = asked ?? pageArticle?.slug ?? null;
      const part = asked === null ? (pageArticle?.part ?? "") : (askedPart ?? "");
      const opened = ++latest;
      void loadIndex()
        .then(() => (opened === latest ? show(wanted, part) : undefined))
        .then(async () => {
        await tick();
        panel?.querySelector<HTMLElement>("[data-help-focus]")?.focus();
      });
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
        oninput={() => {
          latest += 1;
          article = null;
        }}
      />
    </label>

    {#if error}<p class="help-error" role="alert">{error}</p>{/if}

    <div class="help-body" aria-live="polite">
      {#if article !== null && article.part !== ""}
        <button type="button" class="btn btn-ghost btn-sm back" onclick={() => void show(article?.slug ?? null)}>
          <Icon name="chevron-left" size="sm" /> {article.title}
        </button>
        <article class="help-article" aria-label={`${article.title}: ${(article.parts ?? []).find((part) => part.id === article?.part)?.title ?? ""}`}>
          <!-- BUG-301 — the text is the product's own and its targets were
               resolved against the article list before they got here. -->
          <Markdown text={resolveGuideLinks(unwrapGuideProse(article.markdown), slugs, article.slug)} inAppLinks />
        </article>
        {#if position !== null && (position.previous !== null || position.next !== null)}
          <nav class="help-steps" aria-label="More in this article">
            {#if position.previous !== null}
              {@const previous = position.previous}
              <button type="button" class="step" onclick={() => void show(article?.slug ?? null, previous.id)}>
                <span>Previous</span>{previous.title}
              </button>
            {/if}
            {#if position.next !== null}
              {@const next = position.next}
              <button type="button" class="step next" onclick={() => void show(article?.slug ?? null, next.id)}>
                <span>Next</span>{next.title}
              </button>
            {/if}
          </nav>
        {/if}
      {:else if article !== null}
        <button type="button" class="btn btn-ghost btn-sm back" onclick={() => (article = null)}>
          <Icon name="chevron-left" size="sm" /> All articles
        </button>
        <article class="help-article help-intro" aria-label={article.title}>
          <Markdown text={resolveGuideLinks(unwrapGuideProse(article.markdown), slugs, article.slug)} inAppLinks />
        </article>
        {#if (article.parts ?? []).length > 0}
          <h3 class="help-heading" id="help-parts">In this article</h3>
          <ul class="help-list" aria-labelledby="help-parts">
            {#each article.parts ?? [] as part (part.id)}
              <li>
                <button type="button" onclick={() => void show(article?.slug ?? null, part.id)}>
                  <strong>{part.title}</strong>
                  {#if part.summary}<span>{part.summary}</span>{/if}
                </button>
              </li>
            {/each}
          </ul>
        {/if}
      {:else if index !== null && !index.available}
        <p class="muted">
          This build did not ship its help articles. Set RAIKER_GUIDE_DIR to a checkout's
          docs/guide to read them here.
        </p>
      {:else if index !== null}
        {#if pageArticle !== null && query.trim() === ""}
          <p class="on-this-page">
            On this page:
            <button type="button" class="link" onclick={() => void show(pageArticle.slug, pageArticle.part ?? "")}>
              {pageArticle.label}
            </button>
          </p>
        {/if}
        <ul class="help-list" aria-label={query.trim() === "" ? "Help articles" : "Search results"}>
          {#each matches as match (match.key)}
            <li>
              <button type="button" onclick={() => open(match)}>
                {#if match.within}<small>{match.within}</small>{/if}
                <strong>{match.title}</strong>
                {#if match.summary}<span>{match.summary}</span>{/if}
              </button>
            </li>
          {:else}
            <li class="muted">Nothing in help matches “{query}”.</li>
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
  .help-heading {
    margin: var(--space-4) 0 var(--space-2);
    padding: 0 var(--space-3);
    color: var(--text-3);
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .help-steps {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-2);
    margin-top: var(--space-4);
    padding-top: var(--space-3);
    border-top: 1px solid var(--border);
  }
  .step {
    display: grid;
    gap: 0.15rem;
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: transparent;
    color: var(--text-1);
    font: inherit;
    font-size: var(--text-sm);
    text-align: left;
    cursor: pointer;
  }
  .step.next {
    grid-column: 2;
    text-align: right;
  }
  .step:hover {
    background: var(--sunken);
  }
  .step span {
    color: var(--text-3);
    font-size: var(--text-xs);
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
  .help-list small {
    color: var(--text-3);
    font-size: var(--text-xs);
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
