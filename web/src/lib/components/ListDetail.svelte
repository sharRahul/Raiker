<script lang="ts" generics="T">
  /**
   * QUI-L02 — layout B, list and detail.
   *
   * A list of same-height rows on the left and the selected item on the right,
   * at most 680 px wide. Long lists never become long pages: the list scrolls
   * inside its own column and the page stays one screen.
   *
   * * Up and Down move the selection, Home and End jump to the ends, and Enter
   *   opens the selected row (moves focus into the detail).
   * * The selection is part of the address (`?item=`), so a row can be linked.
   * * An empty list hides its search field: there is nothing to search.
   * * The split between the two can be dragged, or moved with the arrow keys on
   *   its handle, and never squeezes the list below one readable row (180 px)
   *   or the detail below 320 px.
   */
  import type { Snippet } from "svelte";
  import Icon from "./Icon.svelte";
  import {
    LIST_MIN_PX,
    clampListWidth,
    hashWithItem,
    itemFromHash,
    stepSelection,
  } from "../listDetail";

  let {
    items,
    key,
    label,
    matches = undefined,
    searchLabel = "Search",
    storageKey = undefined,
    syncAddress = true,
    autoSelectFirst = false,
    selectedId = $bindable(null),
    row,
    detail,
    empty,
    nothingSelected,
  }: {
    items: T[];
    key: (item: T) => string;
    /** Accessible name of the list. */
    label: string;
    /** When given, the list offers a search field and keeps the rows it accepts. */
    matches?: (item: T, query: string) => boolean;
    searchLabel?: string;
    /** Where the dragged split is remembered, per list. */
    storageKey?: string;
    /** Write the selection into the address (`?item=`) and read it back. */
    syncAddress?: boolean;
    /** Show the first row's detail until the owner picks one. */
    autoSelectFirst?: boolean;
    selectedId?: string | null;
    row: Snippet<[T, boolean]>;
    detail: Snippet<[T]>;
    empty?: Snippet;
    nothingSelected?: Snippet;
  } = $props();

  let query = $state("");
  let listElement = $state<HTMLUListElement>();
  let detailElement = $state<HTMLElement>();
  let container = $state<HTMLDivElement>();
  let listWidth = $state<number | null>(readWidth());
  /** The list's drawn width, so the separator always says where it is. */
  let drawnListWidth = $state(0);
  let listColumn = $state<HTMLDivElement>();
  $effect(() => {
    void listWidth;
    if (listColumn === undefined || typeof window === "undefined") return;
    const measure = () => (drawnListWidth = listColumn?.getBoundingClientRect().width ?? 0);
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  });

  const visible = $derived(
    matches === undefined || query.trim() === ""
      ? items
      : items.filter((item) => matches(item, query.trim().toLowerCase())),
  );
  const ids = $derived(visible.map((item) => key(item)));
  const selected = $derived(
    (selectedId === null ? null : (items.find((item) => key(item) === selectedId) ?? null)) ??
      (autoSelectFirst ? (visible[0] ?? null) : null),
  );
  const shownId = $derived(selected === null ? null : key(selected));

  function readWidth(): number | null {
    if (storageKey === undefined || typeof localStorage === "undefined") return null;
    try {
      const saved = Number(localStorage.getItem(`raiker.split.${storageKey}`));
      return Number.isFinite(saved) && saved > 0 ? saved : null;
    } catch {
      return null;
    }
  }

  function saveWidth(width: number) {
    listWidth = width;
    if (storageKey === undefined) return;
    try {
      localStorage.setItem(`raiker.split.${storageKey}`, String(width));
    } catch {
      // A width that is not remembered is still applied.
    }
  }

  // The address is the selection's source of truth when it names a row.
  $effect(() => {
    if (!syncAddress || typeof window === "undefined") return;
    const read = () => {
      const fromHash = itemFromHash(window.location.hash);
      if (fromHash !== null) selectedId = fromHash;
    };
    read();
    window.addEventListener("hashchange", read);
    return () => window.removeEventListener("hashchange", read);
  });

  function select(id: string | null) {
    selectedId = id;
    if (!syncAddress || typeof window === "undefined") return;
    const next = hashWithItem(window.location.hash, id);
    if (next !== window.location.hash) history.replaceState(history.state, "", next);
  }

  function focusRow(id: string | null) {
    if (id === null) return;
    queueMicrotask(() => {
      listElement
        ?.querySelector<HTMLElement>(`[data-item-id="${CSS.escape(id)}"]`)
        ?.focus();
    });
  }

  function onListKeydown(event: KeyboardEvent) {
    let next: string | null;
    if (event.key === "ArrowDown") next = stepSelection(ids, shownId, 1);
    else if (event.key === "ArrowUp") next = stepSelection(ids, shownId, -1);
    else if (event.key === "Home") next = ids[0] ?? null;
    else if (event.key === "End") next = ids[ids.length - 1] ?? null;
    else if (event.key === "Enter" && shownId !== null) {
      event.preventDefault();
      detailElement?.focus();
      return;
    } else return;
    event.preventDefault();
    select(next);
    focusRow(next);
  }

  function onHandleKeydown(event: KeyboardEvent) {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const current = listWidth ?? listElement?.getBoundingClientRect().width ?? 280;
    const width = container?.getBoundingClientRect().width ?? 1000;
    saveWidth(clampListWidth(current + (event.key === "ArrowRight" ? 16 : -16), width));
  }

  function startDrag(event: PointerEvent) {
    if (container === undefined) return;
    event.preventDefault();
    const box = container.getBoundingClientRect();
    const move = (moved: PointerEvent) =>
      saveWidth(clampListWidth(moved.clientX - box.left, box.width));
    const stop = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
  }
</script>

<div
  class="list-detail"
  bind:this={container}
  style:grid-template-columns={listWidth === null ? undefined : `${listWidth}px auto minmax(20rem, 1fr)`}
>
  <div class="list-column" bind:this={listColumn}>
    {#if matches !== undefined && items.length > 0}
      <label class="list-search">
        <Icon name="search" size="sm" />
        <span class="sr-only">{searchLabel}</span>
        <input type="search" bind:value={query} placeholder={searchLabel} />
      </label>
    {/if}
    {#if items.length === 0}
      {#if empty}{@render empty()}{/if}
    {:else}
      <ul
        class="list-rows"
        role="listbox"
        aria-label={label}
        bind:this={listElement}
        onkeydown={onListKeydown}
      >
        {#each visible as item (key(item))}
          {@const id = key(item)}
          {@const isSelected = id === shownId}
          <li
            role="option"
            aria-selected={isSelected}
            data-item-id={id}
            tabindex={isSelected || (shownId === null && id === ids[0]) ? 0 : -1}
            class="list-row"
            class:selected={isSelected}
            onclick={() => select(id)}
            onkeydown={(event) => {
              if (event.key === " ") {
                event.preventDefault();
                select(id);
              }
            }}
          >
            {@render row(item, isSelected)}
          </li>
        {:else}
          <li class="no-match" role="presentation">Nothing matches “{query}”.</li>
        {/each}
      </ul>
    {/if}
  </div>
  {#if items.length > 0}
    <!-- A focusable separator is the ARIA window-splitter pattern: it takes the
         arrow keys and the pointer, and says how wide the list is. -->
    <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <div
      class="split-handle"
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize the list"
      aria-valuenow={listWidth ?? Math.round(drawnListWidth)}
      aria-valuemin={LIST_MIN_PX}
      tabindex="0"
      onpointerdown={startDrag}
      onkeydown={onHandleKeydown}
    ></div>
    <section class="detail-column" tabindex="-1" bind:this={detailElement} aria-label="Selected item">
      {#if selected !== null}
        {@render detail(selected)}
      {:else if nothingSelected}
        {@render nothingSelected()}
      {:else}
        <p class="nothing-selected">Choose an item to see it here.</p>
      {/if}
    </section>
  {/if}
</div>

<style>
  .list-detail {
    display: grid;
    grid-template-columns: minmax(15rem, 22rem) auto minmax(20rem, 1fr);
    align-items: start;
    gap: 0;
    min-height: 0;
  }
  .list-column {
    display: grid;
    gap: var(--space-2);
    min-width: 0;
  }
  .list-search {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: 0 var(--space-3);
    min-height: var(--control-normal);
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: var(--surface);
    color: var(--text-3);
  }
  /* The frame is the field: focus marks the frame, not a second box inside it. */
  .list-search:focus-within {
    outline: 2px solid var(--focus-ring);
    outline-offset: 1px;
  }
  .list-search input,
  .list-search input:focus-visible {
    box-shadow: none;
    min-height: 0;
    padding: 0;
  }
  .list-search input {
    flex: 1;
    min-width: 0;
    border: 0;
    outline: 0;
    background: transparent;
    color: var(--text-1);
    font: inherit;
  }
  .list-rows {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 2px;
    max-height: calc(var(--content-h, 80vh) - 8rem);
    overflow-y: auto;
  }
  .list-row {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    min-height: 56px;
    max-height: 72px;
    padding: var(--space-2) var(--space-3);
    border-radius: var(--r-sm);
    color: var(--text-1);
    cursor: pointer;
  }
  .list-row:hover {
    background: var(--sunken);
  }
  .list-row.selected {
    background: var(--accent-soft);
  }
  .list-row:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: -2px;
  }
  .no-match {
    padding: var(--space-3);
    color: var(--text-3);
    font-size: var(--text-sm);
  }
  .split-handle {
    width: 9px;
    align-self: stretch;
    margin: 0 var(--space-2);
    cursor: col-resize;
    background: linear-gradient(var(--border), var(--border)) center / 1px 100% no-repeat;
  }
  .split-handle:hover,
  .split-handle:focus-visible {
    background: linear-gradient(var(--accent), var(--accent)) center / 3px 100% no-repeat;
    outline: none;
  }
  .detail-column {
    min-width: 0;
    max-width: 680px;
    padding: 0 var(--space-2);
  }
  .detail-column:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: 2px;
  }
  .nothing-selected {
    margin: var(--space-4) 0;
    color: var(--text-3);
  }
  @media (max-width: 720px) {
    .list-detail {
      grid-template-columns: 1fr;
    }
    .split-handle {
      display: none;
    }
  }
</style>
