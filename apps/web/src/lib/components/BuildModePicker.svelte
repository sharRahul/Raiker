<script lang="ts">
  /**
   * The Build composer's posture control, as one chip and one menu.
   *
   * It used to be three buttons sitting side by side in the control bar. Three
   * always-visible buttons make a mode look like a filter — something you toggle
   * to change a view — when what it actually decides is how much of the machine
   * the next turn may touch. A single chip that names the current posture, and a
   * menu that explains each one before you choose it, states that correctly and
   * matches where every reference coding agent keeps the same control.
   *
   * Nothing about what a mode *does* changes here: `BUILD_MODES` still owns the
   * per-turn `capability_modes` map and the planning option, both of which may
   * only tighten (see buildModes.ts). Shift+Tab still cycles.
   */
  import { BUILD_MODES, type BuildMode, buildMode } from "../buildModes";
  import Icon from "./Icon.svelte";

  let {
    mode,
    onchange,
    disabled = false,
    open = $bindable(false),
  }: {
    mode: BuildMode;
    onchange: (next: BuildMode) => void;
    disabled?: boolean;
    open?: boolean;
  } = $props();

  let rootEl: HTMLDivElement | undefined = $state();
  let triggerEl: HTMLButtonElement | undefined = $state();
  const spec = $derived(buildMode(mode));
  const icon = (id: BuildMode) =>
    id === "plan" ? "tasks" : id === "edit" ? "file-edit" : "play";

  function choose(next: BuildMode) {
    open = false;
    if (next !== mode) onchange(next);
  }

  function closeOnEscape(event: KeyboardEvent) {
    if (event.key === "Escape" && open) {
      open = false;
      queueMicrotask(() => triggerEl?.focus());
    }
  }

  function onWindowClick(event: MouseEvent) {
    if (open && rootEl && !rootEl.contains(event.target as Node)) open = false;
  }
</script>

<svelte:window onclick={onWindowClick} />

<div class="build-mode" bind:this={rootEl}>
  <button
    bind:this={triggerEl}
    type="button"
    class="mode-trigger control"
    class:auto-mode={mode === "auto"}
    aria-label={`How much Raiker may do this turn: ${spec.label}`}
    aria-haspopup="menu"
    aria-expanded={open}
    title="Shift+Tab cycles Plan → Edit → Auto"
    {disabled}
    onclick={() => (open = !open)}
    onkeydown={closeOnEscape}
  >
    <Icon name={icon(mode)} size={15} />
    <span>{spec.label}</span>
    <Icon name="chevron-down" size={14} />
  </button>

  {#if open}
    <div class="mode-menu menu-surface" role="menu" aria-label="Mode" tabindex="-1" onkeydown={closeOnEscape}>
      <p class="mode-menu-title">Mode</p>
      {#each BUILD_MODES as option, index (option.id)}
        <button
          type="button"
          class="mode-choice menu-item"
          role="menuitemradio"
          aria-checked={mode === option.id}
          {disabled}
          onclick={() => choose(option.id)}
        >
          <Icon name={icon(option.id)} size={15} />
          <span>
            <strong>{option.label}</strong>
            <small>{option.summary}</small>
          </span>
          {#if mode === option.id}
            <Icon name="check" size={15} label="Selected mode" />
          {:else}
            <kbd>{index + 1}</kbd>
          {/if}
        </button>
      {/each}
      <p class="mode-menu-note">
        A mode applies to this conversation's turns only. It can tighten what a
        turn may do and never widen it — raising a standing permission stays on
        the Permissions page.
      </p>
    </div>
  {/if}
</div>

<style>
  .build-mode {
    position: relative;
  }
  .mode-trigger,
  .mode-choice {
    font: inherit;
  }
  .mode-trigger {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    border: 1px solid var(--neutral-border);
    border-radius: var(--r-pill);
    padding: 0.2rem 0.45rem;
    background: var(--surface);
    color: var(--text-2);
    font-size: 0.76rem;
    font-weight: 650;
    cursor: pointer;
  }
  .mode-trigger:hover:not(:disabled) {
    border-color: var(--accent-border);
    color: var(--text-1);
  }
  /* Auto is the only posture that adds no restriction of its own, so it is the
     only one that earns a colour. Plan and Edit both tighten; they stay quiet. */
  .mode-trigger.auto-mode {
    border-color: var(--accent-border);
    background: var(--accent-soft);
    color: var(--accent);
  }
  .mode-trigger:disabled {
    opacity: 0.62;
    cursor: wait;
  }
  .mode-menu {
    position: absolute;
    z-index: 4;
    left: 0;
    bottom: calc(100% + 0.38rem);
    width: max-content;
    min-width: 15rem;
    max-width: min(22rem, calc(100vw - 2rem));
    padding: 0.26rem;
    border: 1px solid var(--neutral-border);
    border-radius: var(--r-md);
    background: var(--surface);
    box-shadow: var(--shadow-2);
  }
  .mode-menu-title {
    margin: 0.2rem 0.48rem 0.3rem;
    color: var(--text-3);
    font-size: 0.65rem;
    font-weight: 750;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }
  .mode-choice {
    width: 100%;
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
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
  .mode-choice:hover:not(:disabled),
  .mode-choice[aria-checked="true"] {
    background: var(--accent-soft);
    color: var(--text-1);
  }
  .mode-choice strong {
    display: block;
    color: var(--text-1);
    font-size: 0.82rem;
  }
  .mode-choice small {
    display: block;
    color: var(--text-3);
    font-size: 0.68rem;
    line-height: 1.3;
  }
  kbd {
    color: var(--text-3);
    font-family: var(--font-mono);
    font-size: 0.66rem;
  }
  .mode-menu-note {
    margin: 0.3rem 0.48rem 0.15rem;
    padding-top: 0.35rem;
    border-top: 1px solid var(--border);
    color: var(--text-3);
    font-size: 0.66rem;
    line-height: 1.35;
  }
</style>
