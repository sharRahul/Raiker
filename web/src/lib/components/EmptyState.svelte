<script lang="ts">
  // BUG-37 — the empty state as the first thing a new owner sees, rather than a
  // centred sentence apologising for the absence of data.
  //
  // Three changes, each with a reason:
  //
  // * **The mark has depth.** A tinted disc with a soft ring and the icon at the
  //   display size, so the block has a focal point instead of being uniform grey.
  // * **The title is display type by default.** Every empty state is Raiker
  //   speaking to the owner, which is exactly what the serif face is reserved
  //   for. `serif={false}` remains for the few places an empty state sits inside
  //   a dense panel where display type would shout.
  // * **It can offer the next step.** An empty state that names what is missing
  //   and stops is a dead end; the `action` slot puts the way out in the same
  //   block as the explanation.
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
  {#if body}
    <p class="empty-body">{body}</p>
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
  /* A disc, a ring, and a very soft glow — three tokens deep, so it reads as a
     mark rather than as a grey square, and it costs nothing but a box-shadow. */
  .empty-icon {
    display: grid;
    place-items: center;
    width: 56px;
    height: 56px;
    border-radius: var(--r-pill);
    background: var(--accent-soft);
    border: 1px solid var(--accent-border);
    box-shadow: 0 0 0 6px var(--accent-soft);
    color: var(--accent);
    margin-bottom: var(--space-3);
  }
  .empty-title {
    font-weight: 650;
    color: var(--text-1);
    margin: 0;
  }
  .empty-title.serif {
    font-family: var(--font-serif);
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
