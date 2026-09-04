<script lang="ts">
  import { formatContextUsage } from "../contextPresentation";
  import type { ContextUsage } from "../apiTypes";

  let {
    usedTokens = null,
    contextWindowTokens = null,
    usage = null,
  }: {
    usedTokens?: number | null;
    contextWindowTokens?: number | null;
    usage?: ContextUsage | null;
  } = $props();

  const effectiveUsed = $derived(
    usage?.usage_source === "provider" && usage.used_tokens !== null
      ? usage.used_tokens
      : usedTokens,
  );
  const effectiveWindow = $derived(usage?.context_window_tokens ?? contextWindowTokens);

  const percent = $derived(
    effectiveUsed !== null && effectiveUsed !== undefined && effectiveWindow
      ? formatContextUsage(effectiveUsed, effectiveWindow).percent
      : null,
  );

  const R = 7;
  const C = 2 * Math.PI * R;
  const dash = $derived(percent !== null ? (C * percent) / 100 : 0);
</script>

<svg
  class="context-ring"
  width="16"
  height="16"
  viewBox="0 0 16 16"
  fill="none"
  aria-hidden="true"
>
  <circle cx="8" cy="8" r={R} stroke="var(--neutral-border)" stroke-width="2" />
  {#if percent !== null}
    <circle
      cx="8"
      cy="8"
      r={R}
      stroke={percent > 80 ? "var(--warn)" : "var(--accent)"}
      stroke-width="2"
      stroke-linecap="round"
      stroke-dasharray={`${dash} ${C}`}
      transform="rotate(-90 8 8)"
    />
  {:else}
    <!-- Nothing is known about this model's capacity, so the ring has no arc to
         draw. Without this it renders as a bare grey circle beside Send: a
         control with no content and no explanation, which is what a fresh
         install now sees every time (FIXED-365 stopped it selecting a model it
         cannot serve). The dash says "no measurement", which is true, and is
         what the popover behind it goes on to explain. -->
    <line
      x1="5"
      y1="8"
      x2="11"
      y2="8"
      stroke="var(--text-3)"
      stroke-width="1.6"
      stroke-linecap="round"
    />
  {/if}
</svg>

<style>
  .context-ring { display: block; flex-shrink: 0; }
</style>
