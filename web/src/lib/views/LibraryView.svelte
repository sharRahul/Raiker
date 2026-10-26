<script lang="ts">
  /**
   * QUI-F15 — the Library: everything Raiker has made, in one place.
   *
   * Documents a conversation generated, images and designs from Design, answer
   * blocks the owner pinned, and pull requests Build opened. One server read
   * (`GET /api/library`) over the records those already live in, so deleting
   * something where it lives removes it here too. Each row opens where the
   * item came from.
   *
   * Used twice: as the Library tab in Work, and inside a project (`projectId`
   * set), where it shows that project's items and no project filter.
   */
  import { onMount } from "svelte";
  import AnswerParts from "../components/AnswerParts.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import PageState from "../components/PageState.svelte";
  import ShowMore from "../components/ShowMore.svelte";
  import { api, ApiError } from "../api";
  import { contract } from "../generated/apiContract";
  import type { ContentPart, LibraryItem, ProjectView } from "../generated/apiContract";
  import type { IconName } from "../icons";
  import { relativeTime } from "../format";
  import { PAGE_SIZE, page } from "../pagination";

  let {
    projectId = null,
    compact = false,
    exclude = [],
  }: {
    /** Show one project's items, without the project filter. */
    projectId?: string | null;
    /** Inside a project page: a smaller empty state, no heading. */
    compact?: boolean;
    /** Kinds the surrounding page already shows its own way (a project's image strip). */
    exclude?: LibraryItem["kind"][];
  } = $props();

  type Kind = "all" | LibraryItem["kind"];

  const ALL_KINDS: { id: Kind; label: string }[] = [
    { id: "all", label: "All" },
    { id: "document", label: "Documents" },
    { id: "image", label: "Images" },
    { id: "design", label: "Designs" },
    { id: "block", label: "Pinned" },
    { id: "pull_request", label: "Pull requests" },
  ];
  const KINDS = $derived(ALL_KINDS.filter((option) => option.id === "all" || !exclude.includes(option.id)));

  const ICONS: Record<LibraryItem["kind"], IconName> = {
    document: "file",
    image: "design",
    design: "design",
    block: "pin",
    pull_request: "branch",
  };

  let items = $state<LibraryItem[] | null>(null);
  let projects = $state<ProjectView[]>([]);
  let loadError = $state<string | null>(null);
  let kind = $state<Kind>("all");
  let projectFilter = $state("");
  let shown = $state(PAGE_SIZE);
  let openBlock = $state<string | null>(null);
  let notice = $state("");

  const scoped = $derived(
    (items ?? []).filter(
      (item) =>
        (kind === "all" || item.kind === kind) &&
        (projectId !== null || projectFilter === "" || item.project_id === projectFilter),
    ),
  );
  /** Kinds with nothing in them are offered disabled, so a filter never empties the page. */
  const present = $derived(new Set((items ?? []).map((item) => item.kind)));

  async function load() {
    loadError = null;
    try {
      const answer = await contract.getLibrary(projectId ? { project_id: projectId } : {});
      items = answer.items.filter((item) => !exclude.includes(item.kind));
    } catch (error) {
      loadError = error instanceof ApiError ? error.message : "The Library could not be read.";
    }
  }

  onMount(async () => {
    await load();
    if (projectId === null) {
      try {
        projects = (await api.projects()).projects;
      } catch {
        // The filter is supplementary; without it the page still lists everything.
        projects = [];
      }
    }
  });

  function say(message: string) {
    notice = message;
    setTimeout(() => {
      if (notice === message) notice = "";
    }, 3000);
  }

  function context(item: LibraryItem): string {
    const parts = [item.detail];
    if (projectId === null && item.project_name) parts.push(item.project_name);
    if (item.session_title) parts.push(`from “${item.session_title}”`);
    parts.push(relativeTime(item.created_at));
    return parts.join(" · ");
  }

  async function download(item: LibraryItem) {
    if (!item.download_url) return;
    const name = item.kind === "image" ? `${item.item_id.split(":")[1]}.png` : item.title;
    try {
      await api.downloadLibraryItem(item.download_url, name);
    } catch {
      say(`Could not download ${item.title}: it may have been deleted where it was made.`);
    }
  }

  async function unpin(item: LibraryItem) {
    if (!item.pin_id) return;
    try {
      await contract.unpinBlock(item.pin_id);
      items = (items ?? []).filter((row) => row.item_id !== item.item_id);
      say("Unpinned. The answer it came from is unchanged.");
    } catch {
      say("Could not unpin: try again.");
    }
  }

  async function move(item: LibraryItem, target: string) {
    if (!item.pin_id) return;
    try {
      const moved = await contract.movePin(item.pin_id, { project_id: target || null });
      items = (items ?? []).map((row) =>
        row.item_id === item.item_id
          ? { ...row, project_id: moved.project_id, project_name: moved.project_name }
          : row,
      );
      say(moved.project_name ? `Moved to ${moved.project_name}` : "Moved out of its project");
    } catch {
      say("Could not move it: try again.");
    }
  }
</script>

<section class="library" class:compact aria-label={projectId ? "Project library" : "Library"}>
  {#if loadError}
    <PageState state="error" title="The Library could not be read" detail={loadError} />
    <p><button type="button" class="btn btn-soft btn-sm" onclick={() => void load()}>Try again</button></p>
  {:else if items === null}
    <PageState state="loading" title="Reading the Library…" lines={3} />
  {:else if items.length === 0 && compact}
    <p class="none">Nothing made here yet. Documents Raiker writes and blocks you pin in this project's chats appear here.</p>
  {:else if items.length === 0}
    <EmptyState
      icon="library"
      title="Nothing made yet"
      body="Documents Raiker writes, images and designs, and answer blocks you pin appear here."
    >
      {#snippet action()}<a class="btn btn-soft" href="#/new-chat">Start a chat</a>{/snippet}
    </EmptyState>
  {:else}
    <div class="filters">
      <div class="chip-row" role="group" aria-label="Show">
        {#each KINDS as option (option.id)}
          <button
            type="button"
            class="chip"
            aria-pressed={kind === option.id}
            disabled={option.id !== "all" && !present.has(option.id)}
            onclick={() => {
              kind = option.id;
              shown = PAGE_SIZE;
            }}>{option.label}</button
          >
        {/each}
      </div>
      {#if projectId === null && projects.length > 0}
        <label class="project-filter">
          <span class="sr-only">Filter by project</span>
          <select bind:value={projectFilter} aria-label="Filter by project">
            <option value="">All projects</option>
            {#each projects as project (project.project_id)}
              <option value={project.project_id}>{project.name}</option>
            {/each}
          </select>
        </label>
      {/if}
      <span class="notice" role="status">{notice}</span>
    </div>

    {#if scoped.length === 0}
      <p class="none">Nothing here matches these filters.</p>
    {:else}
      <ul class="rows">
        {#each page(scoped, shown) as item (item.item_id)}
          <li class="row" data-kind={item.kind}>
            {#if item.kind === "image" && item.download_url}
              <img class="mark thumb" src={item.download_url} alt="" loading="lazy" />
            {:else}
              <span class="mark" aria-hidden="true"><Icon name={ICONS[item.kind]} size="md" /></span>
            {/if}
            <div class="text">
              {#if item.kind === "block"}
                <button
                  type="button"
                  class="title link"
                  aria-expanded={openBlock === item.item_id}
                  onclick={() => (openBlock = openBlock === item.item_id ? null : item.item_id)}
                >{item.title}</button>
              {:else}
                <a
                  class="title"
                  href={item.href}
                  target={item.external ? "_blank" : undefined}
                  rel={item.external ? "noopener noreferrer" : undefined}>{item.title}</a
                >
              {/if}
              <span class="meta">{context(item)}</span>
            </div>
            <div class="actions">
              {#if item.kind === "block"}
                {#if projectId === null && projects.length > 0}
                  <label>
                    <span class="sr-only">Project for {item.title}</span>
                    <select
                      class="move"
                      value={item.project_id ?? ""}
                      aria-label={`Project for ${item.title}`}
                      onchange={(event) => void move(item, (event.currentTarget as HTMLSelectElement).value)}
                    >
                      <option value="">No project</option>
                      {#each projects as project (project.project_id)}
                        <option value={project.project_id}>{project.name}</option>
                      {/each}
                    </select>
                  </label>
                {/if}
                {#if item.session_id}
                  <a class="btn btn-ghost btn-sm" href={item.href}>Open conversation</a>
                {/if}
                <button type="button" class="btn btn-ghost btn-sm" onclick={() => void unpin(item)}>Unpin</button>
              {:else if item.download_url}
                <button
                  type="button"
                  class="btn btn-ghost btn-sm icon-only"
                  aria-label={`Download ${item.title}`}
                  title="Download"
                  onclick={() => void download(item)}
                >
                  <Icon name="download" size="sm" />
                </button>
              {/if}
            </div>
            {#if item.kind === "block" && openBlock === item.item_id && item.block}
              <div class="block">
                <AnswerParts
                  text=""
                  parts={[{ type: item.block.type as ContentPart["type"], text: "", data: item.block.data as Record<string, unknown>, reason_code: "" }]}
                />
              </div>
            {/if}
          </li>
        {/each}
      </ul>
      <ShowMore total={scoped.length} shown={Math.min(shown, scoped.length)} noun="items" onmore={() => (shown += PAGE_SIZE)} />
    {/if}
  {/if}
</section>

<style>
  .library {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
  .filters {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-2) var(--space-3);
  }
  .project-filter select,
  .move {
    font: inherit;
    font-size: var(--text-sm);
    color: var(--text-1);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    padding: 0.3rem 0.5rem;
  }
  .notice {
    font-size: var(--text-sm);
    color: var(--text-2);
  }
  .notice:empty { display: none; }
  .none {
    color: var(--text-2);
    font-size: var(--text-sm);
    margin: 0;
  }
  .rows {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
  }
  .row {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: var(--space-1) var(--space-3);
    min-height: 64px;
    padding: var(--space-2) var(--space-2);
    border-radius: var(--r-md);
  }
  .row:hover { background: var(--sunken); }
  .mark {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    border-radius: var(--r-sm);
    background: var(--sunken);
    color: var(--text-2);
  }
  .row:hover .mark { background: var(--surface); }
  .thumb {
    object-fit: cover;
    border: 1px solid var(--border);
  }
  .text {
    display: flex;
    flex-direction: column;
    min-width: 0;
    gap: 0.1rem;
  }
  .title {
    color: var(--text-1);
    font-weight: 600;
    text-decoration: none;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    text-align: start;
  }
  a.title:hover,
  .title.link:hover { text-decoration: underline; }
  .title.link {
    font: inherit;
    font-weight: 600;
    background: none;
    border: 0;
    padding: 0;
    cursor: pointer;
  }
  .title:focus-visible { outline: 3px solid var(--focus-ring); outline-offset: 2px; border-radius: var(--r-sm); }
  .meta {
    color: var(--text-2);
    font-size: var(--text-sm);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .actions {
    display: flex;
    align-items: center;
    gap: var(--space-1);
  }
  .icon-only { display: inline-flex; align-items: center; }
  .block {
    grid-column: 2 / -1;
  }
</style>
