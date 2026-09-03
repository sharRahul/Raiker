<script lang="ts">
  import type { ModelProfile } from "../apiTypes";
  import { providerName } from "../format";
  import { modelName } from "../modelPresentation";
  import {
    isChoosableModel,
    openModelSetup,
    readinessForProfile,
  } from "../modelReadiness.svelte";
  import ProviderLogo from "./ProviderLogo.svelte";
  import Icon from "./Icon.svelte";

  let {
    profiles,
    selectedProfile = null,
    value = $bindable(""),
    profileId = $bindable(""),
    model = $bindable(""),
    disabled = false,
    onchosen,
    open = $bindable(false),
    efforts = [],
    effort = $bindable(""),
  }: {
    profiles: ModelProfile[];
    selectedProfile?: ModelProfile | null;
    value?: string;
    profileId?: string;
    model?: string;
    disabled?: boolean;
    /**
     * A deliberate pick, so the surface can remember it. Not fired for the
     * programmatic pre-selection a surface performs on mount, and not fired
     * when the owner returns to the global default — that is the absence of a
     * preference, not a new one.
     */
    onchosen?: (profileId: string, model: string) => void;
    /**
     * B19 — bindable so `/model` in the composer can open the same menu the
     * trigger opens. The slash command is a shortcut to this control, not a
     * second way of choosing a model.
     */
    open?: boolean;
    /**
     * The effort values *this* model publishes. Empty for a model that does not
     * take one, and the Effort section is then absent rather than disabled —
     * offering a thinking budget to a model that has none is a promise the
     * request cannot keep.
     */
    efforts?: readonly string[];
    /**
     * The chosen effort, or "" for "send none". Thinking off and effort "" are
     * the same wire fact, so they are the same piece of state.
     */
    effort?: string;
  } = $props();
  let rootEl: HTMLDivElement | undefined = $state();
  let triggerEl: HTMLButtonElement | undefined = $state();
  let effortOpen = $state(false);
  // The last named effort, kept so switching Thinking off and on again returns
  // the owner to the level they picked instead of silently to the first one.
  let lastEffort = $state("");
  $effect(() => {
    if (effort !== "") lastEffort = effort;
  });
  const thinking = $derived(effort !== "");
  const effortLabel = $derived(
    effort === "" ? "" : effort.charAt(0).toUpperCase() + effort.slice(1),
  );

  function chooseEffort(next: string) {
    effort = next;
  }

  function toggleThinking() {
    // Off means "ask for nothing", which is exactly the empty effort. On restores
    // the owner's last level, or the model's middle value when they have none.
    if (thinking) {
      effort = "";
      return;
    }
    const fallback = efforts.includes(lastEffort)
      ? lastEffort
      : (efforts[Math.floor(efforts.length / 2)] ?? efforts[0] ?? "");
    effort = fallback;
  }
  const sameChoice = (left: ModelProfile, right: ModelProfile) =>
    left.profile_id === right.profile_id && left.model === right.model;
  const choices = $derived(
    selectedProfile === null
      ? profiles
      : [
          selectedProfile,
          ...profiles.filter(
            (profile) => !sameChoice(profile, selectedProfile),
          ),
        ],
  );
  const providerGroups = $derived.by(() => {
    const groups = new Map<string, ModelProfile[]>();
    for (const profile of choices) {
      // A provider with nothing choosable is not a choice, so it does not open
      // a group here; setting one up is one action at the end of the menu.
      if (!isChoosableModel(profile)) continue;
      groups.set(profile.provider, [
        ...(groups.get(profile.provider) ?? []),
        profile,
      ]);
    }
    return [...groups].map(([provider, profiles]) => ({ provider, profiles }));
  });
  /**
   * The first published-but-unready profile, or null when every provider is
   * usable.
   *
   * This menu used to list each unready profile by name, so a fresh install
   * offered “Local GGUF”, “Local GGUF 2”, “Local GGUF 3” and “Local GGUF 4”:
   * four rows for one runtime that is not running, none of which could be
   * chosen. A picker should offer what can be picked, and setting a provider
   * up is one action rather than one action per slot.
   */
  const firstUnconfigured = $derived(
    choices.find((profile) => !isChoosableModel(profile)) ?? null,
  );
  const activeProfileId = $derived(profileId || value);
  const active = $derived(
    profiles.find(
      (profile) =>
        profile.profile_id === activeProfileId &&
        (!model || profile.model === model),
    ) ?? selectedProfile,
  );
  const label = $derived(active ? modelName(active.model) : "Not selected");

  function select(profile: ModelProfile) {
    const selectsDefault =
      selectedProfile !== null && sameChoice(profile, selectedProfile);
    value = selectsDefault ? "" : profile.profile_id;
    profileId = selectsDefault ? "" : profile.profile_id;
    model = selectsDefault ? "" : profile.model;
    open = false;
    if (!selectsDefault) onchosen?.(profile.profile_id, profile.model);
  }

  function repair(profile: ModelProfile) {
    openModelSetup(profile, readinessForProfile(profile));
    open = false;
  }

  function closeOnEscape(event: KeyboardEvent) {
    if (event.key === "Escape") {
      open = false;
      effortOpen = false;
      queueMicrotask(() => triggerEl?.focus());
    }
  }

  function onWindowClick(event: MouseEvent) {
    if (open && rootEl && !rootEl.contains(event.target as Node)) {
      open = false;
      effortOpen = false;
    }
  }
</script>

<svelte:window onclick={onWindowClick} />

<div class="model-picker" bind:this={rootEl}>
  <button
    bind:this={triggerEl}
    type="button"
    class="model-trigger control"
    aria-label={`Model for this turn: ${label}`}
    aria-haspopup="menu"
    aria-expanded={open}
    title="Model for this turn"
    {disabled}
    onclick={() => (open = !open)}
    onkeydown={closeOnEscape}
  >
    {#if active}<ProviderLogo provider={active.provider} />{/if}
    <span>{label}</span>
    {#if effortLabel !== ""}<span class="model-effort">{effortLabel}</span>{/if}
    <Icon name="chevron-down" size={14} />
  </button>

  {#if open}
    <div
      class="model-menu menu-surface"
      role="menu"
      aria-label="Models"
      tabindex="-1"
      onkeydown={closeOnEscape}
    >
      {#each providerGroups as group (group.provider)}
        <div
          class="model-provider-group"
          role="group"
          aria-label={`${providerName(group.provider)} models`}
        >
          <div class="model-provider-header">
            <ProviderLogo provider={group.provider} />
            <span>{providerName(group.provider)}</span>
          </div>
          {#each group.profiles as profile (`${profile.profile_id}\u0000${profile.model}`)}
            <button
              type="button"
              class="model-choice menu-item"
              role="menuitemradio"
              aria-checked={active?.profile_id === profile.profile_id &&
                active?.model === profile.model}
              {disabled}
              onclick={() => select(profile)}
            >
              <ProviderLogo provider={profile.provider} />
              <span>{modelName(profile.model)}</span>
              {#if active?.profile_id === profile.profile_id && active?.model === profile.model}<Icon
                  name="check"
                  size={15}
                  label="Selected model"
                />{/if}
            </button>
          {/each}
        </div>
      {/each}

      {#if firstUnconfigured !== null}
        <div class="setup-choice">
          <button
            type="button"
            class="setup-action"
            onclick={() => repair(firstUnconfigured)}
          >
            Set up another model
          </button>
        </div>
      {/if}

      {#if efforts.length > 0}
        <!-- The thinking budget belongs to the model, so it lives inside the
             model menu rather than beside it as a second dropdown. Thinking off
             and "no effort named" are the same request, so they are one control:
             the toggle governs whether an effort is sent at all, and the levels
             say which one. -->
        <div class="effort-section" role="group" aria-label="Effort">
          <button
            type="button"
            class="effort-row"
            aria-expanded={effortOpen}
            onclick={() => (effortOpen = !effortOpen)}
          >
            <span>Effort</span>
            <span class="effort-value">{effort === "" ? "None" : effortLabel}</span>
            <Icon name={effortOpen ? "chevron-down" : "chevron-right"} size={14} />
          </button>
          {#if effortOpen}
            <p class="effort-note">
              Higher effort asks this model to think longer before it answers. It
              costs more tokens and takes longer.
            </p>
            {#each efforts as level (level)}
              <button
                type="button"
                class="effort-choice"
                role="menuitemradio"
                aria-checked={effort === level}
                {disabled}
                onclick={() => chooseEffort(level)}
              >
                <span>{level.charAt(0).toUpperCase() + level.slice(1)}</span>
                {#if effort === level}<Icon name="check" size={15} label="Selected effort" />{/if}
              </button>
            {/each}
            <button
              type="button"
              class="effort-toggle"
              role="switch"
              aria-checked={thinking}
              {disabled}
              onclick={toggleThinking}
            >
              <span>
                <strong>Thinking</strong>
                <small>{thinking ? "An effort rides with the prompt." : "No effort is sent."}</small>
              </span>
              <span class="switch" data-on={thinking}></span>
            </button>
          {/if}
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .model-picker {
    position: relative;
    /* The menu is positioned against this box, so the box has to be the
       trigger's size. As a plain block it stretched to whatever column it was
       dropped into — in the task form, the whole width of the panel — and
       `right: 0; bottom: 100%` then opened the menu in the far corner of that
       column instead of above the button. */
    display: inline-flex;
    width: fit-content;
    max-width: 100%;
  }
  .model-trigger,
  .model-choice {
    font: inherit;
  }
  .model-trigger {
    min-width: 9.5rem;
    display: inline-flex;
    align-items: center;
    gap: 0.42rem;
    border: 1px solid var(--neutral-border);
    border-radius: var(--r-pill);
    padding: 0.22rem 0.46rem;
    background: var(--surface);
    color: var(--text-2);
    font-size: 0.76rem;
    font-weight: 650;
    cursor: pointer;
  }
  .model-trigger:hover:not(:disabled) {
    color: var(--text-1);
    border-color: var(--accent-border);
  }
  .model-trigger:disabled {
    opacity: 0.62;
    cursor: wait;
  }
  .model-trigger span {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .model-trigger :global(svg) {
    margin-left: auto;
  }
  .model-menu {
    position: absolute;
    z-index: 4;
    right: 0;
    bottom: calc(100% + 0.38rem);
    width: max-content;
    min-width: 12rem;
    max-width: min(20rem, calc(100vw - 2rem));
    padding: 0.26rem;
    border: 1px solid var(--neutral-border);
    border-radius: var(--r-md);
    background: var(--surface);
    box-shadow: var(--shadow-2);
  }
  .model-provider-group + .model-provider-group {
    margin-top: 0.28rem;
    padding-top: 0.28rem;
    border-top: 1px solid var(--border);
  }
  .model-provider-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.3rem 0.48rem 0.24rem;
    color: var(--text-1);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.03em;
  }
  .model-provider-header :global(.provider-logo) {
    width: 1.05rem;
    height: 1.05rem;
    flex-basis: 1.05rem;
  }
  .model-choice {
    width: 100%;
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) 1rem;
    align-items: center;
    gap: 0.5rem;
    padding: 0.42rem 0.48rem;
    border: 0;
    border-radius: var(--r-sm);
    background: transparent;
    color: var(--text-2);
    text-align: left;
    cursor: pointer;
  }
  .model-choice:hover:not(:disabled),
  .model-choice[aria-checked="true"] {
    background: var(--accent-soft);
    color: var(--text-1);
  }
  .model-choice:disabled {
    cursor: wait;
  }
  .model-choice > span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .model-choice :global(.provider-logo) {
    width: 1.15rem;
    height: 1.15rem;
    flex-basis: 1.15rem;
  }
  .setup-choice {
    display: flex;
    justify-content: center;
    padding: 0.4rem 0.48rem;
    border-radius: var(--r-sm);
    background: var(--sunken);
    color: var(--text-2);
  }
  .setup-action {
    border: 1px solid var(--warn-border, var(--neutral-border));
    border-radius: var(--r-pill);
    padding: 0.2rem 0.48rem;
    background: var(--surface);
    color: var(--text-1);
    font: inherit;
    font-size: 0.68rem;
    font-weight: 750;
    cursor: pointer;
  }
  .setup-action:hover {
    border-color: var(--accent-border);
    background: var(--accent-soft);
  }
  /* The effort reads as the model's qualifier rather than a second value, so it
     sits in the trigger at the muted weight the reference composers use. */
  .model-effort {
    color: var(--text-3);
    font-weight: 500;
  }
  .effort-section {
    margin-top: 0.28rem;
    padding-top: 0.28rem;
    border-top: 1px solid var(--border);
  }
  .effort-row,
  .effort-choice,
  .effort-toggle {
    width: 100%;
    font: inherit;
    border: 0;
    border-radius: var(--r-sm);
    background: transparent;
    color: var(--text-2);
    text-align: left;
    cursor: pointer;
  }
  .effort-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto auto;
    align-items: center;
    gap: 0.5rem;
    padding: 0.42rem 0.48rem;
    font-weight: 650;
  }
  .effort-row:hover,
  .effort-choice:hover:not(:disabled),
  .effort-toggle:hover:not(:disabled) {
    background: var(--accent-soft);
    color: var(--text-1);
  }
  .effort-value {
    color: var(--text-3);
    font-weight: 500;
  }
  .effort-note {
    margin: 0.1rem 0.48rem 0.35rem;
    color: var(--text-3);
    font-size: 0.68rem;
    line-height: 1.35;
  }
  .effort-choice {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 1rem;
    align-items: center;
    gap: 0.5rem;
    padding: 0.36rem 0.48rem 0.36rem 0.9rem;
  }
  .effort-choice[aria-checked="true"] {
    background: var(--accent-soft);
    color: var(--text-1);
  }
  .effort-toggle {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: 0.6rem;
    margin-top: 0.2rem;
    padding: 0.42rem 0.48rem;
    border-top: 1px solid var(--border);
    border-radius: 0;
  }
  .effort-toggle small {
    display: block;
    color: var(--text-3);
    font-size: 0.66rem;
  }
  .switch {
    width: 1.85rem;
    height: 1.05rem;
    border-radius: var(--r-pill);
    background: var(--neutral-border);
    position: relative;
    transition: background var(--motion-fast) var(--ease);
  }
  .switch::after {
    content: "";
    position: absolute;
    top: 0.15rem;
    left: 0.15rem;
    width: 0.75rem;
    height: 0.75rem;
    border-radius: 50%;
    background: var(--surface);
    transition: transform var(--motion-fast) var(--ease);
  }
  .switch[data-on="true"] {
    background: var(--accent);
  }
  .switch[data-on="true"]::after {
    transform: translateX(0.8rem);
  }
  @media (prefers-reduced-motion: reduce) {
    .switch,
    .switch::after {
      transition: none;
    }
  }
</style>
