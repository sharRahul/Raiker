<script lang="ts">
  import type { ModelProfile } from "../apiTypes";
  import { modelName } from "../modelPresentation";
  import ProviderLogo from "./ProviderLogo.svelte";
  import Icon from "./Icon.svelte";

  let {
    profiles,
    selectedProfile = null,
    value = $bindable(""),
    disabled = false,
  }: {
    profiles: ModelProfile[];
    selectedProfile?: ModelProfile | null;
    value?: string;
    disabled?: boolean;
  } = $props();

  let open = $state(false);
  const choices = $derived(selectedProfile === null ? profiles : [selectedProfile, ...profiles.filter((profile) => profile.profile_id !== selectedProfile.profile_id)]);
  const active = $derived(profiles.find((profile) => profile.profile_id === value) ?? selectedProfile);
  const label = $derived(active ? modelName(active.model) : "Not selected");

  function select(profileId: string) {
    value = profileId === selectedProfile?.profile_id ? "" : profileId;
    open = false;
  }

  function closeOnEscape(event: KeyboardEvent) {
    if (event.key === "Escape") open = false;
  }
</script>

<div class="model-picker">
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
    <div class="model-menu" role="menu" aria-label="Models" tabindex="-1" onkeydown={closeOnEscape}>
      {#each choices as profile (profile.profile_id)}
        <button
          type="button"
          class="model-choice"
          role="menuitemradio"
          aria-checked={active?.profile_id === profile.profile_id}
          disabled={disabled}
          onclick={() => select(profile.profile_id)}
        >
          <ProviderLogo provider={profile.provider} />
          <span>{modelName(profile.model)}</span>
          {#if active?.profile_id === profile.profile_id}<Icon name="check" size={15} label="Selected model" />{/if}
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .model-picker { position: relative; }
  .model-trigger, .model-choice { font: inherit; }
  .model-trigger { min-width: 9.5rem; display: inline-flex; align-items: center; gap: .42rem; border: 1px solid var(--neutral-border); border-radius: var(--r-pill); padding: .22rem .46rem; background: var(--surface); color: var(--text-2); font-size: .76rem; font-weight: 650; cursor: pointer; }
  .model-trigger:hover:not(:disabled) { color: var(--text-1); border-color: var(--accent-border); }
  .model-trigger:disabled { opacity: .62; cursor: wait; }
  .model-trigger span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .model-trigger :global(svg) { margin-left: auto; }
  .model-menu { position: absolute; z-index: 4; right: 0; bottom: calc(100% + .38rem); width: max-content; min-width: 12rem; max-width: min(20rem, calc(100vw - 2rem)); padding: .26rem; border: 1px solid var(--neutral-border); border-radius: var(--r-md); background: var(--surface); box-shadow: var(--shadow-2); }
  .model-choice { width: 100%; display: grid; grid-template-columns: 1.15rem minmax(0, 1fr) 1rem; align-items: center; gap: .5rem; padding: .42rem .48rem; border: 0; border-radius: var(--r-sm); background: transparent; color: var(--text-2); text-align: left; cursor: pointer; }
  .model-choice:hover:not(:disabled), .model-choice[aria-checked="true"] { background: var(--accent-soft); color: var(--text-1); }
  .model-choice:disabled { cursor: wait; }
  .model-choice > span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .model-choice :global(.provider-logo) { width: 1.15rem; height: 1.15rem; flex-basis: 1.15rem; }
</style>
