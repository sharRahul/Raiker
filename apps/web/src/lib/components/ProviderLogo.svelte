<script lang="ts">
  import { providerName } from "../format";

  let { provider, size = 18 }: { provider: string; size?: number } = $props();
  const label = $derived(`${providerName(provider)} logo`);
  const initials = $derived(providerName(provider).slice(0, 1).toUpperCase());
</script>

<span class="provider-logo" data-provider={provider} role="img" aria-label={label} style={`--logo-size:${size}px`}>
  {#if provider === "ollama" || provider === "ollama-cloud"}
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 8.5c0-3 2.5-5 6-5s6 2 6 5v7c0 3-2.5 5-6 5s-6-2-6-5z"/><circle cx="9.5" cy="11" r="1"/><circle cx="14.5" cy="11" r="1"/><path d="M9.5 15c1.4 1 3.6 1 5 0"/></svg>
  {:else if provider === "openai"}
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.5a4.7 4.7 0 0 1 7.8 4.9 4.7 4.7 0 0 1-1.9 8.8 4.7 4.7 0 0 1-7.8 2.8 4.7 4.7 0 0 1-5.9-6.9A4.7 4.7 0 0 1 6.1 4.3 4.7 4.7 0 0 1 12 3.5Z"/><path d="M9.2 7.4 15 10.7v6.6M8.4 16.4v-6.7l5.8-3.3"/></svg>
  {:else if provider === "anthropic"}
    <svg viewBox="0 0 24 24" aria-hidden="true"><path class="solid" d="M3.8 20 9.7 4h4.6l5.9 16h-3.5l-1.1-3H8.4l-1.1 3H3.8Zm5.8-6h4.8L12 7.4 9.6 14Z"/></svg>
  {:else if provider === "gemini"}
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 1.8 7.2L21 12l-7.2 1.8L12 21l-1.8-7.2L3 12l7.2-1.8L12 3Z"/></svg>
  {:else if provider === "huggingface"}
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5.5 10.5 4 8m14.5 2.5L20 8M6 13a6 6 0 0 0 12 0v-1a6 6 0 0 0-12 0v1Z"/><circle cx="9.5" cy="12" r=".7" class="solid"/><circle cx="14.5" cy="12" r=".7" class="solid"/><path d="M9.5 15c1.4 1 3.6 1 5 0"/></svg>
  {:else if provider === "openrouter"}
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12a7 7 0 1 0 2-5M5 5v5h5M19 19v-5h-5"/></svg>
  {:else if provider === "lm-studio" || provider === "lm-studio-remote"}
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5v14h6M13 8c1.2-1 4.5-1 5.5.6.8 1.3.1 2.5-1.8 3.1l-1.5.5c-2.1.7-2.7 2-1.7 3.3 1.1 1.5 4.3 1.5 5.5.1"/></svg>
  {:else if provider === "llama.cpp"}
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m8 7 2-3 2 3 2-3 2 3v10c0 2-2 3-4 3s-4-1-4-3V7Z"/><circle cx="10.5" cy="11" r=".7" class="solid"/><circle cx="13.5" cy="11" r=".7" class="solid"/><path d="M10.5 15h3"/></svg>
  {:else if provider === "openai-compatible"}
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 7-5 5 5 5M15 7l5 5-5 5M13.5 4 10.5 20"/></svg>
  {:else}
    <svg viewBox="0 0 24 24" aria-hidden="true"><text x="12" y="16" text-anchor="middle">{initials}</text></svg>
  {/if}
</span>

<style>
  .provider-logo { width: var(--logo-size); height: var(--logo-size); flex: 0 0 var(--logo-size); display: inline-grid; place-items: center; border-radius: 5px; background: color-mix(in srgb, var(--text-1) 10%, var(--surface)); color: var(--text-1); }
  .provider-logo[data-provider="anthropic"] { background: #d97757; color: #fff7f2; }
  .provider-logo[data-provider="ollama"], .provider-logo[data-provider="ollama-cloud"] { background: #111827; color: #fff; }
  .provider-logo[data-provider="openai"] { background: #0f766e; color: #fff; }
  .provider-logo[data-provider="gemini"] { background: #4361ee; color: #fff; }
  .provider-logo[data-provider="huggingface"] { background: #e9a400; color: #1f2937; }
  .provider-logo[data-provider="openrouter"] { background: #4b5563; color: #fff; }
  .provider-logo[data-provider="lm-studio"], .provider-logo[data-provider="lm-studio-remote"] { background: #6d28d9; color: #fff; }
  .provider-logo[data-provider="llama.cpp"] { background: #b45309; color: #fff; }
  .provider-logo[data-provider="openai-compatible"] { background: #0369a1; color: #fff; }
  svg { width: 78%; height: 78%; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
  .solid { fill: currentColor; stroke: none; }
  text { fill: currentColor; font: 800 13px system-ui, sans-serif; stroke: none; }
</style>
