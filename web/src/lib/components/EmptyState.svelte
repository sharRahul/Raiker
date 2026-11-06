<script lang="ts">
  // BUG-37 — the empty state as the first thing a new owner sees, rather than a
  // centred sentence apologising for the absence of data.
  //
  // The icon, short title and next action carry this state. The legacy `serif`
  // prop selects the larger title style; QUI-V02 uses Inter for both styles.
  import Icon from "./Icon.svelte";
  import type { IconName } from "../icons";
  import type { Snippet } from "svelte";

  let {
    icon = "spark",
    title,
    compactTitle = null,
    body = null,
    serif = true,
    action = undefined,
  }: {
    icon?: IconName;
    title: string;
    compactTitle?: string | null;
    body?: string | null;
    serif?: boolean;
    action?: Snippet;
  } = $props();
</script>

<div class="empty motion-enter">
  <span class="empty-icon" aria-hidden="true"><Icon name={icon} size="xl" /></span>
  <p class="empty-title" class:serif>
    <span class:wide-title={compactTitle !== null}>{title}</span>
    {#if compactTitle !== null}<span class="compact-title">{compactTitle}</span>{/if}
  </p>
  <!-- Quiet UI — the title and the action carry an empty state; the sentence
       under them is kept for screen readers only. -->
  {#if body}
    <p class="empty-body sr-only">{body}</p>
  {/if}
  {#if action}
    <div class="empty-action">{@render action()}</div>
  {/if}
</div>

<style>
  .empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 0.3rem;
    padding: var(--space-6) var(--space-4);
    color: var(--text-2);
  }
  .empty-icon {
    display: grid;
    place-items: center;
    width: 40px;
    height: 40px;
    color: var(--text-2);
    margin-bottom: var(--space-3);
  }
  .empty-title {
    font-weight: 650;
    color: var(--text-1);
    margin: 0;
  }
  .empty-title.serif {
    font-weight: 500;
    font-size: var(--text-xl);
    letter-spacing: var(--tracking-tight);
  }
  .compact-title { display: none; }
  @media (max-width: 63.9rem) {
    .wide-title { display: none; }
    .compact-title { display: inline; }
  }
  .empty-body {
    font-size: var(--text-sm);
    max-width: 42ch;
    margin: 0;
  }
  .empty-action {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: var(--space-2);
    margin-top: var(--space-3);
  }
</style>
