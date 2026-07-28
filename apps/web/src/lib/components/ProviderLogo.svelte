<script lang="ts">
  import { providerName } from "../format";

  const OFFICIAL_ASSETS: Record<string, string> = {
    anthropic: "/provider-logos/anthropic.svg",
    ollama: "/provider-logos/ollama.svg",
    "ollama-cloud": "/provider-logos/ollama.svg",
    openrouter: "/provider-logos/openrouter.svg",
    huggingface: "/provider-logos/huggingface.svg",
    openai: "/provider-logos/openai.svg",
    gemini: "/provider-logos/google.ico",
  };

  let { provider, size = 18 }: { provider: string; size?: number } = $props();
  const label = $derived(`${providerName(provider)} logo`);
  const source = $derived(OFFICIAL_ASSETS[provider]);
</script>

<span class="provider-logo" data-provider={provider} role="img" aria-label={label} style={`--logo-size:${size}px`}>
  {#if source}
    <img src={source} alt="" />
  {:else}
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5h14v14H5zM8.5 8.5h7v7h-7z"/></svg>
  {/if}
</span>

<style>
  .provider-logo { width: var(--logo-size); height: var(--logo-size); flex: 0 0 var(--logo-size); display: inline-grid; place-items: center; border-radius: 5px; background: var(--surface); color: var(--text-1); overflow: hidden; }
  .provider-logo[data-provider="gemini"], .provider-logo[data-provider="openrouter"], .provider-logo[data-provider="huggingface"] { background: #fff; }
  img { width: 82%; height: 82%; object-fit: contain; }
  svg { width: 78%; height: 78%; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
</style>
