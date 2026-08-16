<script lang="ts">
  import type { ModelProfile } from "../apiTypes";
  import { providerName } from "../format";
  import { modelName } from "../modelPresentation";
  import {
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
  } = $props();
  let rootEl: HTMLDivElement | undefined = $state();
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
      groups.set(profile.provider, [
        ...(groups.get(profile.provider) ?? []),
        profile,
      ]);
    }
    return [...groups].map(([provider, profiles]) => ({ provider, profiles }));
  });
  const readyChoices = (items: ModelProfile[]) =>
    items.filter((profile) => profile.ready !== false);
  const setupChoices = (items: ModelProfile[]) =>
    items.filter((profile) => profile.ready === false);
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
    if (event.key === "Escape") open = false;
  }

  function onWindowClick(event: MouseEvent) {
    if (open && rootEl && !rootEl.contains(event.target as Node)) open = false;
  }
</script>

<svelte:window onclick={onWindowClick} />

<div class="model-picker" bind:this={rootEl}>
  <button
    type="button"
    class="model-trigger"
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
    <Icon name="chevron-down" size={14} />
  </button>

  {#if open}
    <div
      class="model-menu"
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
          {#if readyChoices(group.profiles).length > 0}
            <div class="readiness-label">
              <span class="ready-dot"></span>Ready
            </div>
          {/if}
          {#each readyChoices(group.profiles) as profile (`${profile.profile_id}\u0000${profile.model}`)}
            <button
              type="button"
              class="model-choice"
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
          {#if setupChoices(group.profiles).length > 0}
            <div class="readiness-label setup-label">Needs setup</div>
          {/if}
          {#each setupChoices(group.profiles) as profile (`setup-${profile.profile_id}\u0000${profile.model}`)}
            <div class="setup-choice">
              <ProviderLogo provider={profile.provider} />
              <span class="setup-model">{modelName(profile.model)}</span>
              <button
                type="button"
                class="setup-action"
                aria-label={`Set up ${providerName(profile.provider)} for ${modelName(profile.model)}`}
                onclick={() => repair(profile)}
              >
                Set up {providerName(profile.provider)}
              </button>
            </div>
          {/each}
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .model-picker {
    position: relative;
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
  .readiness-label {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.2rem 0.48rem;
    color: var(--text-3);
    font-size: 0.65rem;
    font-weight: 750;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .ready-dot {
    width: 0.38rem;
    height: 0.38rem;
    border-radius: 50%;
    background: var(--success, #2f9e62);
  }
  .setup-label {
    margin-top: 0.18rem;
    color: var(--warn-text, var(--text-2));
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
    display: grid;
    grid-template-columns: auto minmax(5rem, 1fr) auto;
    align-items: center;
    gap: 0.5rem;
    padding: 0.4rem 0.48rem;
    border-radius: var(--r-sm);
    background: var(--sunken);
    color: var(--text-2);
  }
  .setup-choice + .setup-choice {
    margin-top: 0.18rem;
  }
  .setup-choice :global(.provider-logo) {
    width: 1.15rem;
    height: 1.15rem;
    flex-basis: 1.15rem;
  }
  .setup-model {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
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
</style>
