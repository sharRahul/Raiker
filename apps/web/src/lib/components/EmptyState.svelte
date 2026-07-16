<script lang="ts">
  import Icon from "./Icon.svelte";
  import type { IconName } from "../icons";

  let {
    icon = "spark",
    title,
    body = null,
    serif = false,
  }: { icon?: IconName; title: string; body?: string | null; serif?: boolean } = $props();
</script>

<div class="empty">
  <span class="empty-icon"><Icon name={icon} size={22} /></span>
  <p class="empty-title" class:serif={serif}>{title}</p>
  {#if body}
    <p class="empty-body">{body}</p>
  {/if}
</div>

<style>
  .empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 0.25rem;
    padding: var(--space-6) var(--space-4);
    color: var(--text-2);
  }
  .empty-icon {
    display: grid;
    place-items: center;
    width: 44px;
    height: 44px;
    border-radius: var(--r-pill);
    background: var(--accent-soft);
    color: var(--accent);
    margin-bottom: 0.35rem;
  }
  .empty-title {
    font-weight: 650;
    color: var(--text-1);
    margin: 0;
  }
  .empty-title.serif {
    font-family: var(--font-serif);
    font-weight: 500;
    font-size: 1.35rem;
    letter-spacing: -0.005em;
  }
  .empty-body {
    font-size: 0.85rem;
    max-width: 42ch;
    margin: 0;
  }
</style>
