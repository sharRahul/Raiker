<script lang="ts">
  /**
   * QUI-L04 — layout D, the Add dialog.
   *
   * A page shows what you have; adding something new happens here. A 640 px
   * centred dialog: search, categories, one card per option, then the chosen
   * option's steps. Choosing a source comes first, and the later steps show
   * only that source, never the whole catalogue beside them.
   *
   * Rendered only while open (`{#if adding}<AddDialog … />{/if}`), so it opens
   * as a modal on mount and gives focus back to whatever opened it on close.
   */
  import { onMount, type Snippet } from "svelte";
  import Icon from "./Icon.svelte";
  import type { AddOption } from "../addDialog";


  let {
    title,
    options,
    chosen = $bindable(null),
    searchLabel = "Search",
    onclose,
    card,
    steps,
  }: {
    title: string;
    options: AddOption[];
    chosen?: string | null;
    searchLabel?: string;
    onclose: () => void;
    /** Optional richer card body; the name, description and note otherwise. */
    card?: Snippet<[AddOption]>;
    /** The chosen option's steps. */
    steps: Snippet<[AddOption]>;
  } = $props();

  let dialogElement = $state<HTMLDialogElement>();
  let query = $state("");
  let category = $state("All");

  const categories = $derived(["All", ...new Set(options.map((option) => option.category))]);
  const visible = $derived(
    options.filter((option) => {
      const words = query.trim().toLowerCase();
      return (
        (category === "All" || option.category === category) &&
        (words === "" ||
          `${option.name} ${option.description} ${option.category}`.toLowerCase().includes(words))
      );
    }),
  );
  const chosenOption = $derived(options.find((option) => option.id === chosen) ?? null);

  onMount(() => {
    const returnFocus =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    if (dialogElement) {
      if (typeof dialogElement.showModal === "function") dialogElement.showModal();
      else dialogElement.setAttribute("open", "");
    }
    return () => returnFocus?.focus();
  });

  function cancel(event: Event) {
    event.preventDefault();
    if (chosen !== null) chosen = null;
    else onclose();
  }

  function backdrop(event: MouseEvent) {
    if (event.target === event.currentTarget) onclose();
  }
</script>

<dialog
  class="add-dialog"
  bind:this={dialogElement}
  aria-labelledby="add-dialog-title"
  oncancel={cancel}
  onclick={backdrop}
>
  <header>
    {#if chosenOption !== null}
      <button type="button" class="btn btn-ghost btn-sm" onclick={() => (chosen = null)}>
        <Icon name="chevron-left" size="sm" /> Back
      </button>
    {/if}
    <h2 id="add-dialog-title">{chosenOption?.name ?? title}</h2>
    <button type="button" class="btn btn-ghost btn-sm close" aria-label="Close" onclick={onclose}>
      <Icon name="x" size="sm" />
    </button>
  </header>

  {#if chosenOption === null}
    <label class="add-search">
      <Icon name="search" size="sm" />
      <span class="sr-only">{searchLabel}</span>
      <!-- svelte-ignore a11y_autofocus -->
      <input type="search" bind:value={query} placeholder={searchLabel} autofocus />
    </label>
    {#if categories.length > 2}
      <div class="chip-row" role="group" aria-label="Categories">
        {#each categories as item (item)}
          <button
            type="button"
            class="chip"
            aria-pressed={category === item}
            onclick={() => (category = item)}>{item}</button
          >
        {/each}
      </div>
    {/if}
    <ul class="add-options" aria-label="Options">
      {#each visible as option (option.id)}
        <li>
          <button
            type="button"
            class="add-option"
            disabled={option.disabled}
            onclick={() => (chosen = option.id)}
          >
            {#if card}
              {@render card(option)}
            {:else}
              <span class="option-name">
                {option.name}
                {#if option.note}<small>{option.note}</small>{/if}
              </span>
              <span class="option-description">{option.description}</span>
            {/if}
          </button>
        </li>
      {:else}
        <li class="no-match">Nothing matches “{query}”.</li>
      {/each}
    </ul>
  {:else}
    <div class="add-steps">
      {@render steps(chosenOption)}
    </div>
  {/if}
</dialog>

<style>
  .add-dialog::backdrop {
    background: var(--overlay);
  }
  .add-dialog {
    color: var(--text-1);
    width: min(640px, calc(100vw - 2rem));
    max-height: min(85vh, 52rem);
    overflow-y: auto;
    padding: var(--space-5);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    background: var(--surface);
    box-shadow: var(--shadow-2);
  }
  header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-3);
  }
  header h2 {
    flex: 1;
    margin: 0;
    font-size: var(--text-lg);
  }
  .add-search {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: 0 var(--space-3);
    min-height: var(--control-normal);
    border: 1px solid var(--border-strong);
    border-radius: var(--r-sm);
    background: var(--surface);
    color: var(--text-3);
  }
  .add-search input {
    flex: 1;
    min-width: 0;
    border: 0;
    outline: 0;
    background: transparent;
    color: var(--text-1);
    font: inherit;
  }
  .chip-row {
    margin-top: var(--space-3);
  }
  .add-options {
    list-style: none;
    margin: var(--space-3) 0 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-2);
  }
  .add-option {
    display: grid;
    gap: 0.2rem;
    width: 100%;
    min-height: 72px;
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--surface);
    color: inherit;
    text-align: left;
    cursor: pointer;
  }
  .add-option:hover:not(:disabled) {
    background: var(--sunken);
    border-color: var(--border-strong);
  }
  .add-option:disabled {
    cursor: not-allowed;
    opacity: 0.7;
  }
  .option-name {
    font-weight: 650;
  }
  .option-name small {
    margin-left: var(--space-2);
    color: var(--text-3);
    font-size: var(--text-xs);
    font-weight: 550;
  }
  .option-description {
    color: var(--text-2);
    font-size: var(--text-sm);
  }
  .no-match {
    grid-column: 1 / -1;
    padding: var(--space-4);
    color: var(--text-3);
    text-align: center;
  }
  .add-steps {
    display: grid;
    gap: var(--space-3);
  }
  @media (max-width: 640px) {
    .add-options {
      grid-template-columns: 1fr;
    }
  }
</style>
