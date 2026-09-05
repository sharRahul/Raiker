<script lang="ts">
  import { providerName } from "../format";

  const OFFICIAL_ASSETS: Record<string, string> = {
    anthropic: "/provider-logos/anthropic.svg",
    ollama: "/provider-logos/ollama.svg",
    "ollama-cloud": "/provider-logos/ollama.svg",
    openrouter: "/provider-logos/openrouter.svg",
    huggingface: "/provider-logos/huggingface.svg",
    openai: "/provider-logos/openai.svg",
    // The ChatGPT subscription *is* OpenAI, reached through the local Codex
    // client, so it carries the mark already bundled for that provider.
    "chatgpt-codex": "/provider-logos/openai.svg",
    gemini: "/provider-logos/google.ico",
  };

  /**
   * Neutral marks for the runtimes that publish no redistributable logo.
   *
   * They used to share one anonymous square, so four different rows on the
   * model screen were identified by the same picture — which is the same as
   * having no picture at all, but takes up the space of one. These are drawn
   * from what the runtime *is*: a chip for a local weight server, stacked
   * layers for MLX's arrays, a window for LM Studio's desktop app, and a plug
   * for any OpenAI-compatible endpoint the owner points Raiker at.
   */
  const NEUTRAL_MARKS: Record<string, string> = {
    "llama.cpp": "M9 3v2M15 3v2M9 19v2M15 19v2M3 9h2M3 15h2M19 9h2M19 15h2M6 6h12v12H6z",
    mlx: "M12 3 3 7.5 12 12l9-4.5zM3 12l9 4.5L21 12M3 16.5 12 21l9-4.5",
    "lm-studio": "M4 5h16v14H4zM4 9h16M7.5 7h.01M10 7h.01",
    "openai-compatible": "M10 13.5 7.5 16a3.5 3.5 0 1 1-5-5l2.5-2.5M14 10.5 16.5 8a3.5 3.5 0 1 1 5 5L19 15.5M9 15l6-6",
  };

  let { provider, size = 18 }: { provider: string; size?: number } = $props();
  const label = $derived(`${providerName(provider)} logo`);
  const source = $derived(OFFICIAL_ASSETS[provider]);
  const mark = $derived(NEUTRAL_MARKS[provider] ?? "M5 5h14v14H5zM8.5 8.5h7v7h-7z");
</script>

<span class="provider-logo" data-provider={provider} role="img" aria-label={label} style={`--logo-size:${size}px`}>
  {#if source}
    <img src={source} alt="" />
  {:else}
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d={mark} /></svg>
  {/if}
</span>

<style>
  .provider-logo { width: var(--logo-size); height: var(--logo-size); flex: 0 0 var(--logo-size); display: inline-grid; place-items: center; border-radius: 5px; background: var(--surface); color: var(--text-1); overflow: hidden; }
  .provider-logo[data-provider="gemini"], .provider-logo[data-provider="openrouter"], .provider-logo[data-provider="huggingface"] { background: var(--brand-white); }
  img { width: 82%; height: 82%; object-fit: contain; }
  svg { width: 78%; height: 78%; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
</style>
