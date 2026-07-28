<script lang="ts">
  import { providerName } from "../format";

  let { provider, size = 18 }: { provider: string; size?: number } = $props();
  const label = $derived(`${providerName(provider)} logo`);
  const initials = $derived(provider === "anthropic" ? "AI" : provider === "openai" ? "O" : provider === "ollama" ? "O" : providerName(provider).slice(0, 1).toUpperCase());
</script>

<span class:anthropic={provider === "anthropic"} class:ollama={provider === "ollama"} class:openai={provider === "openai"} class="provider-logo" role="img" aria-label={label} style={`--logo-size:${size}px`}>
  {#if provider === "ollama"}
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 8.5c0-3 2.5-5 6-5s6 2 6 5v7c0 3-2.5 5-6 5s-6-2-6-5z"/><circle cx="9.5" cy="11" r="1"/><circle cx="14.5" cy="11" r="1"/><path d="M9.5 15c1.4 1 3.6 1 5 0"/></svg>
  {:else if provider === "openai"}
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.5a4.7 4.7 0 0 1 7.8 4.9 4.7 4.7 0 0 1-1.9 8.8 4.7 4.7 0 0 1-7.8 2.8 4.7 4.7 0 0 1-5.9-6.9A4.7 4.7 0 0 1 6.1 4.3 4.7 4.7 0 0 1 12 3.5Z"/><path d="M9.2 7.4 15 10.7v6.6M8.4 16.4v-6.7l5.8-3.3"/></svg>
  {:else}
    <span>{initials}</span>
  {/if}
</span>

<style>
  .provider-logo { width: var(--logo-size); height: var(--logo-size); flex: 0 0 var(--logo-size); display: inline-grid; place-items: center; border-radius: 5px; background: color-mix(in srgb, var(--text-1) 10%, var(--surface)); color: var(--text-1); font-size: calc(var(--logo-size) * .46); font-weight: 800; letter-spacing: -.08em; line-height: 1; }
  .provider-logo.anthropic { background: #d97757; color: #fff7f2; }
  .provider-logo.ollama { background: #111827; color: #fff; }
  .provider-logo.openai { background: #0f766e; color: #fff; }
  svg { width: 78%; height: 78%; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
</style>
