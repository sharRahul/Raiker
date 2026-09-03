<script lang="ts">
  /**
   * Which of a provider's models stay offered everywhere.
   *
   * Choosing a default used to be the only way a model reached a picker, so a
   * provider serving six could offer exactly one of them and swapping meant
   * coming back to this page. These switches are the owner saying which models
   * they actually work with; the default is still a separate decision, made by
   * the button beside them.
   */
  import { api } from "../../api";
  import { chatCandidates, modelName } from "../../modelPresentation";

  let {
    profileId,
    catalogue,
    chosen,
    defaultModel = null,
    onuse,
    onsaved,
  }: {
    profileId: string;
    /** What the provider published, in its own order. */
    catalogue: string[];
    /** The models currently kept available for this profile. */
    chosen: string[];
    /**
     * The model this provider currently answers with, so the row that is
     * already the default says so instead of offering to become it again.
     */
    defaultModel?: string | null;
    /**
     * Make one model this provider's default (BUG-264). Supplied by the setup
     * matrix, where this dialog replaced a dropdown: choosing *which* models are
     * kept and choosing *which one answers* were two controls asking about the
     * same list, and one of them was a `<select>` of four hundred entries.
     */
    onuse?: (model: string) => void;
    onsaved?: () => void;
  } = $props();

  let pending = $state<string[] | null>(null);
  let busy = $state(false);
  let failure = $state<string | null>(null);
  const selected = $derived(pending ?? chosen);

  /**
   * A search box, because a catalogue is not a short list (BUG-260). OpenRouter
   * publishes four hundred models and OpenAI a hundred and twenty; scrolling a
   * switch list that long to find one name is not choosing, it is hunting.
   */
  let query = $state("");

  // Opening a different provider's picker starts a new search (BUG-263). Two
  // ways it otherwise does not: the component is reused when only its props
  // change, and the browser restores a same-named field's value across a
  // navigation. Either leaves an owner looking at "53 of 424" for a provider
  // they have just opened, with a filter they did not type and cannot see the
  // origin of — which reads as the provider serving 53 models.
  let queryFor = $state<string | null>(null);
  $effect(() => {
    if (queryFor === profileId) return;
    queryFor = profileId;
    query = "";
  });

  // BUG-258 — a provider's catalogue includes endpoint families that cannot
  // answer a turn at all (embeddings, speech, images, moderation). They are not
  // choices on a screen asking where Raiker should think, and one of them being
  // *first* is what made the default an embedding model. A model already kept
  // available is always shown, whatever it is: the owner's own past choice
  // outranks this rule.
  const offered = $derived(
    Array.from(new Set([...chatCandidates(catalogue), ...selected.filter((m) => catalogue.includes(m))])),
  );
  const matches = $derived(
    query.trim() === ""
      ? offered
      : offered.filter((model) => {
          const needle = query.trim().toLowerCase();
          return (
            model.toLowerCase().includes(needle) ||
            modelName(model).toLowerCase().includes(needle)
          );
        }),
  );
  const hidden = $derived(catalogue.length - offered.length);

  async function toggle(model: string) {
    const next = selected.includes(model)
      ? selected.filter((item) => item !== model)
      : [...selected, model];
    pending = next;
    busy = true;
    failure = null;
    try {
      const result = await api.setAvailableModels(profileId, next);
      pending = result.models;
      onsaved?.();
    } catch {
      pending = null;
      failure = "That list could not be saved.";
    } finally {
      busy = false;
    }
  }
</script>

<fieldset class="available" disabled={busy}>
  <legend>Keep available</legend>
  {#if catalogue.length > 1}
    <input
      class="search"
      type="search"
      placeholder="Search models…"
      aria-label="Search models"
      autocomplete="off"
      bind:value={query}
    />
  {/if}
  <div class="list">
    {#each matches as model (model)}
      <div class="row-wrap">
        <label class="row">
          <input
            type="checkbox"
            value={model}
            checked={selected.includes(model)}
            onchange={() => void toggle(model)}
          />
          <span class="track" aria-hidden="true"><span class="knob"></span></span>
          <span class="name">{modelName(model)}</span>
        </label>
        {#if onuse}
          {#if defaultModel === model}
            <span class="is-default">Default</span>
          {:else}
            <button type="button" class="use" onclick={() => onuse?.(model)}>Use</button>
          {/if}
        {/if}
      </div>
    {/each}
  </div>
  {#if matches.length === 0}
    <p class="empty">No model matches “{query}”.</p>
  {/if}
  <p class="count">
    {matches.length} of {offered.length}{#if hidden > 0}{` · ${hidden} not chat model${hidden === 1 ? "" : "s"}`}{/if}
  </p>
  {#if failure}<p class="failure" role="alert">{failure}</p>{/if}
</fieldset>

<style>
  .available {
    margin: 0;
    padding: 0;
    border: 0;
    display: grid;
    gap: 0.3rem;
  }
  legend {
    padding: 0;
    color: var(--text-3);
    font-size: 0.68rem;
    font-weight: 750;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .search {
    min-height: 30px;
    padding: 0 0.5rem;
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: var(--surface);
    color: var(--text-1);
    font: inherit;
    font-size: 0.78rem;
  }
  .list {
    display: grid;
    gap: 0.15rem;
    max-height: 11rem;
    overflow-y: auto;
  }
  .empty, .count { margin: 0; color: var(--text-3); font-size: 0.68rem; }
  .row-wrap { display: flex; align-items: center; gap: 0.4rem; }
  .row-wrap .row { flex: 1; min-width: 0; }
  .row-wrap .name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  /* Quiet until wanted: the switch is the primary act in this list, and a
     coloured button on every line would compete with all of them at once. */
  .use {
    flex: none;
    border: 1px solid var(--border);
    border-radius: var(--r-pill);
    padding: 0.1rem 0.5rem;
    background: var(--surface);
    color: var(--text-2);
    font: inherit;
    font-size: 0.68rem;
    cursor: pointer;
  }
  .use:hover { border-color: var(--accent-border); color: var(--accent); }
  .is-default {
    flex: none;
    padding: 0.1rem 0.5rem;
    color: var(--accent);
    font-size: 0.68rem;
    font-weight: 700;
  }
  .row {
    position: relative;
    display: flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.16rem 0.1rem;
    font-size: 0.76rem;
    cursor: pointer;
  }
  /* Transparent rather than absent: the real control keeps the size of the
     switch it is drawn as, so it is a pointer target and an assertable element
     in its own right instead of a zero-by-zero box behind a picture.

     Typed, not a bare `input`. As a bare element selector this also hid the
     search box added above — 26px wide at zero opacity, present in the DOM and
     invisible on screen, which is exactly how it was reported: "there is no
     search in the pop-up windows yet". A rule that means "the switch's
     checkbox" has to say so. */
  input[type="checkbox"] {
    position: absolute;
    left: 0.1rem;
    opacity: 0;
    margin: 0;
    width: 1.65rem;
    height: 0.92rem;
    cursor: pointer;
  }
  .track {
    flex: 0 0 auto;
    width: 1.65rem;
    height: 0.92rem;
    border-radius: var(--r-pill);
    background: var(--sunken);
    border: 1px solid var(--neutral-border);
    display: inline-flex;
    align-items: center;
    padding: 0 0.1rem;
    transition: background 0.12s ease;
  }
  .knob {
    width: 0.62rem;
    height: 0.62rem;
    border-radius: 50%;
    background: var(--text-3);
    transition: transform 0.12s ease, background 0.12s ease;
  }
  input:checked + .track {
    background: var(--accent-soft);
    border-color: var(--accent-border);
  }
  input:checked + .track .knob {
    transform: translateX(0.68rem);
    background: var(--accent, var(--text-1));
  }
  input:focus-visible + .track {
    outline: 3px solid var(--focus-ring);
    outline-offset: 2px;
  }
  .name {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .failure {
    margin: 0;
    color: var(--danger-text, var(--text-2));
    font-size: 0.72rem;
  }
</style>
