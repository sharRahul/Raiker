<script lang="ts">
  import { onMount } from "svelte";
  import { api } from "../api";
  import { APPROVAL_MODES, type ApprovalMode } from "../approvalMode";
  import Icon from "./Icon.svelte";

  let mode = $state<ApprovalMode>("manual");
  let confirmedMode = $state<ApprovalMode>("manual");
  let open = $state(false);
  let busy = $state(false);
  let error = $state<string | null>(null);
  let selectionVersion = 0;
  let rootEl: HTMLDivElement | undefined = $state();
  let triggerEl: HTMLButtonElement | undefined = $state();

  onMount(async () => {
    const initialSelectionVersion = selectionVersion;
    try {
      const saved = await api.composerApprovalMode();
      if (selectionVersion !== initialSelectionVersion) return;
      mode = saved.approval_mode;
      confirmedMode = saved.approval_mode;
    } catch {
      if (selectionVersion !== initialSelectionVersion) return;
      error = "Approval mode unavailable.";
    }
  });

  function descriptor(value: ApprovalMode) {
    return APPROVAL_MODES.find((option) => option.mode === value) ?? APPROVAL_MODES[0];
  }

  async function select(next: ApprovalMode) {
    if (busy || next === mode) return;

    selectionVersion += 1;
    const previous = confirmedMode;
    busy = true;
    error = null;
    mode = next;
    try {
      const saved = await api.setComposerApprovalMode(next);
      mode = saved.approval_mode;
      confirmedMode = saved.approval_mode;
      open = false;
    } catch {
      mode = previous;
      error = "Approval mode was not saved.";
    } finally {
      busy = false;
    }
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

<div class="approval-mode-control" bind:this={rootEl}>
  <button
    bind:this={triggerEl}
    type="button"
    class="approval-trigger control"
    class:skip-mode={mode === "skip"}
    aria-label={`Approval mode: ${descriptor(mode).label}`}
    aria-haspopup="menu"
    aria-expanded={open}
    onclick={() => (open = !open)}
    onkeydown={closeOnEscape}
  >
    <Icon name={descriptor(mode).icon} size="md" />
    <span>{descriptor(mode).label}</span>
    <Icon name="chevron-down" size="sm" />
  </button>

  {#if open}
    <div class="approval-menu menu-surface" role="menu" aria-label="Approval mode" tabindex="-1" onkeydown={closeOnEscape}>
      {#each APPROVAL_MODES as option (option.mode)}
        <button
          type="button"
          class="approval-choice menu-item"
          role="menuitemradio"
          aria-checked={mode === option.mode}
          disabled={busy}
          onclick={() => void select(option.mode)}
        >
          <Icon name={option.icon} size="md" />
          <span class="choice-copy">
            <span class="choice-label">{option.menuLabel ?? option.label}</span>
            <!-- Four postures is one more than a label alone can carry: "Skip"
                 and "Decline, don't ask" both mean "stop asking me", and they do
                 opposite things. The line under each says which. -->
            <span class="choice-detail">{option.detail}</span>
          </span>
          {#if mode === option.mode}<Icon name="check" size="md" label="Selected approval mode" />{/if}
        </button>
      {/each}
    </div>
  {/if}

  {#if error}<span role="status">{error}</span>{/if}
</div>

<style>
  .approval-mode-control { position: relative; display: flex; align-items: center; gap: .35rem; }
  .approval-trigger, .approval-choice { font: inherit; }
  .approval-trigger { display: inline-flex; align-items: center; gap: .3rem; border: 1px solid var(--neutral-border); background: var(--surface); color: var(--text-2); font-size: .76rem; font-weight: 600; padding: .2rem .45rem; border-radius: var(--r-pill); cursor: pointer; }
  .approval-trigger:hover { border-color: var(--accent-border); color: var(--text-1); }
  .approval-trigger.skip-mode { border-color: var(--warn-border); background: var(--warn-soft); color: var(--warn); }
  .approval-trigger.skip-mode:hover { border-color: var(--warn); color: var(--warn); }
  /* Opens **upward**. This control lives in the composer bar, which is pinned to
     the bottom of the viewport in both Chat and Build, so a menu dropped below
     the trigger is clipped by the fold — the last option was unreachable without
     scrolling a page that does not scroll. Anchoring to the trigger's top edge
     puts the whole menu on screen at every height. `left: 0` keeps it inside the
     viewport at 390px, where the trigger sits near the left edge and a
     right-anchored menu ran off the other side. */
  .approval-menu { position: absolute; z-index: 2; bottom: calc(100% + .3rem); left: 0; min-width: 17rem; max-width: min(22rem, calc(100vw - 2rem)); padding: .25rem; border: 1px solid var(--neutral-border); border-radius: var(--r-md); background: var(--surface); box-shadow: 0 -.4rem 1.2rem color-mix(in srgb, var(--text-1) 14%, transparent); }
  .approval-choice { width: 100%; display: grid; grid-template-columns: 1rem 1fr 1rem; align-items: start; gap: .45rem; padding: .4rem .45rem; border: 0; border-radius: var(--r-sm); background: transparent; color: var(--text-2); text-align: left; cursor: pointer; }
  .choice-copy { display: grid; gap: .1rem; min-width: 0; }
  .choice-label { font-weight: 600; }
  .choice-detail { color: var(--text-3); font-size: .72rem; line-height: 1.35; }
  .approval-choice:hover:not(:disabled) .choice-detail { color: var(--text-2); }
  .approval-choice:hover:not(:disabled) { background: var(--surface-raised); color: var(--text-1); }
  .approval-choice:disabled { opacity: .6; cursor: wait; }
  [role="status"] { color: var(--danger); font-size: .74rem; }
</style>
