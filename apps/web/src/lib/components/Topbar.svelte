<script lang="ts">
  import type { ModelsView } from "../apiTypes";
  import Icon from "./Icon.svelte";
  import ModelChip from "./ModelChip.svelte";
  import StopSwitch from "./StopSwitch.svelte";
  import ThemeToggle from "./ThemeToggle.svelte";
  import { humanize } from "../format";

  let {
    title,
    hint,
    principal,
    runtimeMode,
    ready,
    connecting = false,
    models = null,
  }: {
    title: string;
    hint: string;
    principal: string;
    runtimeMode: string;
    ready: boolean;
    connecting?: boolean;
    models?: ModelsView | null;
  } = $props();
</script>

<header class="topbar">
  <div class="page-id">
    <h1 class="page-title">{title}</h1>
    <p class="page-hint">{hint}</p>
  </div>

  <div class="status" role="status" aria-live="polite">
    {#if connecting}
      <span class="pill pill-muted">Connecting…</span>
    {:else}
      <ModelChip {models} />
      <span class="pill" class:pill-ok={ready} class:pill-warn={!ready} title="Local runtime readiness">
        <span class="dot" aria-hidden="true"></span>
        {ready ? "Runtime ready" : "Runtime not ready"}
      </span>
      <span class="pill pill-muted" title="Active runtime mode">
        <Icon name="shield" size={13} />
        {humanize(runtimeMode)}
      </span>
      <span class="pill pill-muted mono" title="Acting principal">{principal}</span>
    {/if}
  </div>

  <div class="controls">
    <ThemeToggle />
    <StopSwitch />
  </div>
</header>

<style>
  .topbar {
    height: var(--topbar-h);
    display: flex;
    align-items: center;
    gap: var(--space-4);
    padding: 0 var(--space-5);
    border-bottom: 1px solid var(--border);
    background: var(--surface);
    flex-shrink: 0;
  }
  .page-id {
    min-width: 0;
  }
  .page-title {
    font-size: 1rem;
    margin: 0;
    line-height: 1.2;
  }
  .page-hint {
    font-size: 0.72rem;
    color: var(--text-3);
    margin: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .status {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    margin-left: auto;
    flex-wrap: nowrap;
  }
  .pill {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.74rem;
    font-weight: 600;
    padding: 0.18rem 0.6rem;
    border-radius: var(--r-pill);
    border: 1px solid var(--neutral-border);
    background: var(--neutral-soft);
    color: var(--text-2);
    white-space: nowrap;
  }
  .pill-ok {
    border-color: var(--ok-border);
    background: var(--ok-soft);
    color: var(--ok);
  }
  .pill-warn {
    border-color: var(--warn-border);
    background: var(--warn-soft);
    color: var(--warn);
  }
  .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: currentColor;
  }
  .controls {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  @media (max-width: 900px) {
    .pill.mono,
    .page-hint {
      display: none;
    }
  }
</style>
