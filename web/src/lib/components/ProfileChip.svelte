<script lang="ts">
  /**
   * QUI-P02 — the profile chip on a composer: Careful or Standard, for this
   * conversation. It only narrows the owner's settings (see
   * `conversationProfile.ts`); its menu says what each choice means.
   *
   * When the account's approval mode is not "ask", the menu says so and points
   * at Permissions › Advanced, where that mode is set. Careful still asks: the
   * runtime lets a turn's `ask` override an automatic mode.
   */
  import { onMount } from "svelte";
  import { api } from "../api";
  import { APPROVAL_MODES, type ApprovalMode } from "../approvalMode";
  import { CONVERSATION_PROFILES, profileLabel, type ConversationProfile } from "../conversationProfile";
  import Icon from "./Icon.svelte";

  let {
    profile = $bindable<ConversationProfile>("standard"),
    disabled = false,
    placement = "up",
    onchange,
  }: {
    profile?: ConversationProfile;
    disabled?: boolean;
    /** Which way the menu opens: up from a composer at the bottom, down from one at the top. */
    placement?: "up" | "down";
    onchange?: (profile: ConversationProfile) => void;
  } = $props();

  let open = $state(false);
  let mode = $state<ApprovalMode | null>(null);
  let root = $state<HTMLDivElement>();
  let trigger = $state<HTMLButtonElement>();

  onMount(() => {
    void (async () => {
      try {
        mode = (await api.composerApprovalMode()).approval_mode;
      } catch {
        mode = null;
      }
    })();
  });

  const relaxedMode = $derived(mode !== null && mode !== "manual" ? mode : null);
  const modeLabel = $derived(APPROVAL_MODES.find((item) => item.mode === relaxedMode)?.label ?? "");

  function choose(next: ConversationProfile) {
    profile = next;
    onchange?.(next);
    open = false;
    trigger?.focus();
  }

  $effect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (root !== undefined && !root.contains(event.target as Node)) open = false;
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        open = false;
        trigger?.focus();
      }
    };
    window.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKey);
    };
  });
</script>

<div class="profile" bind:this={root}>
  <button
    type="button"
    class="chip"
    class:careful={profile === "careful"}
    aria-expanded={open}
    aria-haspopup="dialog"
    aria-label={`How much Raiker does without asking: ${profileLabel(profile)}`}
    title="How much Raiker does without asking, in this conversation"
    {disabled}
    bind:this={trigger}
    onclick={() => (open = !open)}
  >
    <Icon name="shield" size="sm" />
    <span>{profileLabel(profile)}</span>
    <Icon name="chevron-down" size="sm" />
  </button>

  {#if open}
    <div class="panel motion-enter" class:down={placement === "down"} role="dialog" aria-label="How much Raiker does without asking">
      <p class="lead">In this conversation</p>
      <div role="radiogroup" aria-label="Profile" class="choices">
        {#each CONVERSATION_PROFILES as option (option.id)}
          <button
            type="button"
            role="radio"
            aria-checked={profile === option.id}
            class="choice"
            class:chosen={profile === option.id}
            onclick={() => choose(option.id)}
          >
            <span class="choice-head">
              <strong>{option.label}</strong>
              {#if profile === option.id}<Icon name="check" size="sm" />{/if}
            </span>
            <span class="consequence">{option.consequence}</span>
          </button>
        {/each}
      </div>
      {#if relaxedMode !== null}
        <p class="mode-note" role="note">
          Your approval mode is <strong>{modeLabel}</strong>. Careful still asks.
          <a href="#/capabilities?category=advanced">Change it in Permissions</a>
        </p>
      {/if}
      <p class="foot">A profile can only make Raiker ask more, never less.</p>
    </div>
  {/if}
</div>

<style>
  .profile {
    position: relative;
    display: inline-flex;
  }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    min-height: 28px;
    padding: 0.25rem 0.55rem;
    border: 1px solid var(--border);
    border-radius: var(--r-pill);
    background: var(--surface);
    color: var(--text-2);
    font: inherit;
    font-size: var(--text-xs);
    white-space: nowrap;
    cursor: pointer;
  }
  .chip:hover {
    color: var(--text-1);
    background: var(--sunken);
  }
  .chip.careful {
    border-color: var(--accent-border);
    color: var(--accent);
  }
  .panel {
    position: absolute;
    bottom: calc(100% + 6px);
    left: 0;
    z-index: var(--z-popover);
    width: min(21rem, 78vw);
    display: grid;
    gap: var(--space-2);
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--raised);
    box-shadow: var(--shadow-2);
  }
  .panel.down {
    bottom: auto;
    top: calc(100% + 6px);
  }
  .lead {
    margin: 0;
    font-size: var(--text-xs);
    font-weight: 650;
    color: var(--text-1);
  }
  .choices {
    display: grid;
    gap: 0.3rem;
  }
  .choice {
    display: grid;
    gap: 0.15rem;
    text-align: left;
    padding: 0.45rem 0.55rem;
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: var(--surface);
    color: var(--text-2);
    font: inherit;
    cursor: pointer;
  }
  .choice.chosen {
    border-color: var(--accent-border);
    background: var(--accent-soft);
  }
  .choice-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    color: var(--text-1);
    font-size: var(--text-sm);
  }
  .consequence,
  .mode-note,
  .foot {
    margin: 0;
    font-size: var(--text-xs);
    color: var(--text-3);
  }
  .mode-note {
    color: var(--warn-text, var(--warn));
  }
</style>
