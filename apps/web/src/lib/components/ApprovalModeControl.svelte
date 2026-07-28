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
    if (event.key === "Escape") open = false;
  }
</script>

<div class="approval-mode-control">
  <button
    type="button"
    class="approval-trigger"
    class:skip-mode={mode === "skip"}
    aria-label={`Approval mode: ${descriptor(mode).label}`}
    aria-haspopup="menu"
    aria-expanded={open}
    onclick={() => (open = !open)}
    onkeydown={closeOnEscape}
  >
    <Icon name={descriptor(mode).icon} size={16} />
    <span>{descriptor(mode).label}</span>
    <Icon name="chevron-down" size={14} />
  </button>

  {#if open}
    <div class="approval-menu" role="menu" aria-label="Approval mode" tabindex="-1" onkeydown={closeOnEscape}>
      {#each APPROVAL_MODES as option (option.mode)}
        <button
          type="button"
          class="approval-choice"
          role="menuitemradio"
          aria-checked={mode === option.mode}
          disabled={busy}
          onclick={() => void select(option.mode)}
        >
          <Icon name={option.icon} size={16} />
          <span>{option.label}</span>
          {#if mode === option.mode}<Icon name="check" size={16} label="Selected approval mode" />{/if}
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
  .approval-menu { position: absolute; z-index: 2; top: calc(100% + .3rem); right: 0; min-width: 13rem; padding: .25rem; border: 1px solid var(--neutral-border); border-radius: var(--r-md); background: var(--surface); box-shadow: 0 .4rem 1.2rem color-mix(in srgb, var(--text-1) 14%, transparent); }
  .approval-choice { width: 100%; display: grid; grid-template-columns: 1rem 1fr 1rem; align-items: center; gap: .45rem; padding: .4rem .45rem; border: 0; border-radius: var(--r-sm); background: transparent; color: var(--text-2); text-align: left; cursor: pointer; }
  .approval-choice:hover:not(:disabled) { background: var(--surface-raised); color: var(--text-1); }
  .approval-choice:disabled { opacity: .6; cursor: wait; }
  [role="status"] { color: var(--danger, #b3292f); font-size: .74rem; }
</style>
