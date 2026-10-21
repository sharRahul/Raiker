<script lang="ts">
  /**
   * QUI-L04 — layout D, the Add dialog.
   *
   * A page shows what you have; adding something new happens here. A 640 px
   * centred dialog: search, categories, one card per option, then the chosen
   * option's steps. Choosing a source comes first, and the later steps show
   * only that source, never the whole catalogue beside them.
   *
   * Rendered only while open (`{#if adding}<AddDialog … />{/if}`): it takes
   * focus on mount and gives it back to whatever opened it on close.
   *
   * Not a native `<dialog>` opened with `showModal()`. That puts it in the
   * browser's top layer, above every z-index, and a step inside it opens
   * windows of its own — a provider's sign-in, its model list, a GitHub device
   * code — which then drew *underneath* it and could not be used. It sits at
   * `--z-panel`, below the scrim layer those windows use.
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

  let dialogElement = $state<HTMLDivElement>();
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
    dialogElement?.querySelector<HTMLElement>("input, button")?.focus();
    const onKeydown = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || event.defaultPrevented) return;
      // A window opened from a step answers its own Escape first.
      const modals = document.querySelectorAll('[role="dialog"][aria-modal="true"], dialog[open]');
      if (modals.length > 0 && modals[modals.length - 1] !== dialogElement) return;
      event.preventDefault();
      if (chosen !== null) chosen = null;
      else onclose();
    };
    window.addEventListener("keydown", onKeydown);
    return () => {
      window.removeEventListener("keydown", onKeydown);
      returnFocus?.focus();
    };
  });

  function backdrop(event: MouseEvent) {
    if (event.target === event.currentTarget) onclose();
  }
</script>

<div class="add-backdrop" role="presentation" onclick={backdrop}>
<div
  class="add-dialog"
  role="dialog"
  aria-modal="true"
  tabindex="-1"
  bind:this={dialogElement}
  aria-label={title}
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
      <input type="search" bind:value={query} placeholder={searchLabel} />
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
</div>
</div>

<style>
  .add-backdrop {
    position: fixed;
    inset: 0;
    z-index: var(--z-panel);
    display: grid;
    place-items: center;
    padding: var(--space-4);
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
