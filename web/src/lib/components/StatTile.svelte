<script lang="ts">
  /**
   * One readiness fact, and the evidence behind it.
   *
   * A status card must never be an opaque green dot: every tile carries a
   * value, a plain-language explanation, and a link to the record that proves
   * it. `tone` is presentation only — the server decides what the value is.
   */
  import Icon from "./Icon.svelte";
  import type { IconName } from "../icons";

  let {
    label,
    value,
    detail,
    tone = "neutral",
    icon = null,
    href = null,
    linkLabel = "See evidence",
  }: {
    label: string;
    value: string | number;
    detail: string;
    tone?: "neutral" | "ok" | "warn" | "danger" | "accent";
    icon?: IconName | null;
    href?: string | null;
    linkLabel?: string;
  } = $props();
</script>

<!-- Quiet UI — the label, the number and the link are the tile; the sentence
     explaining it is for screen readers and the tooltip. -->
<article class="tile" data-tone={tone} title={detail}>
  <p class="label">
    {#if icon}<Icon name={icon} size="sm" />{/if}
    {label}
  </p>
  <strong class="value">{value}</strong>
  <p class="detail sr-only">{detail}</p>
  {#if href}<a class="evidence" {href}>{linkLabel}</a>{/if}
</article>

<style>
  .tile {
    display: grid;
    align-content: start;
    gap: 0.15rem;
    padding: var(--space-4);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--surface);
    box-shadow: var(--shadow-1);
  }
  .tile[data-tone="ok"] { border-color: var(--ok-border); }
  .tile[data-tone="warn"] { border-color: var(--warn-border); }
  .tile[data-tone="danger"] { border-color: var(--danger-border); }
  .tile[data-tone="accent"] { border-color: var(--accent-border); }
  .label {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    margin: 0;
    font-size: var(--text-xs);
    font-weight: 700;
    color: var(--text-3);
  }
  .value {
    font-size: var(--text-display);
    line-height: 1.15;
    font-variant-numeric: tabular-nums;
  }
  .tile[data-tone="ok"] .value { color: var(--ok); }
  .tile[data-tone="warn"] .value { color: var(--warn); }
  .tile[data-tone="danger"] .value { color: var(--danger); }
  .detail {
    margin: 0.15rem 0 0;
    color: var(--text-2);
    font-size: var(--text-sm);
  }
  .evidence {
    margin-top: 0.35rem;
    font-size: var(--text-sm);
    font-weight: 600;
  }
</style>
