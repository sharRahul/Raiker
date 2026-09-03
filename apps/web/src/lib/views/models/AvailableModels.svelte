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
  import { modelName } from "../../modelPresentation";

  let {
    profileId,
    catalogue,
    chosen,
    onsaved,
  }: {
    profileId: string;
    /** What the provider published, in its own order. */
    catalogue: string[];
    /** The models currently kept available for this profile. */
    chosen: string[];
    onsaved?: () => void;
  } = $props();

  let pending = $state<string[] | null>(null);
  let busy = $state(false);
  let failure = $state<string | null>(null);
  const selected = $derived(pending ?? chosen);

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
  <div class="list">
    {#each catalogue as model (model)}
      <label class="row">
        <input
          type="checkbox"
          checked={selected.includes(model)}
          onchange={() => void toggle(model)}
        />
        <span class="track" aria-hidden="true"><span class="knob"></span></span>
        <span class="name">{modelName(model)}</span>
      </label>
    {/each}
  </div>
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
  .list {
    display: grid;
    gap: 0.15rem;
    max-height: 11rem;
    overflow-y: auto;
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
     in its own right instead of a zero-by-zero box behind a picture. */
  input {
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
