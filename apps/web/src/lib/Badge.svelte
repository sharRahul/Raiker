<script lang="ts">
  import { BADGES } from "./badges";
  import type { BadgeVariant } from "./types";

  let { variant }: { variant: BadgeVariant } = $props();
  const meta = $derived(BADGES[variant]);
</script>

<span class="badge {meta.tone}" title={meta.description}>
  <span class="badge-symbol" aria-hidden="true">{meta.symbol}</span>
  <span class="badge-label">{meta.label}</span>
</span>

<style>
  .badge {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    padding: 0.1rem 0.5rem;
    border-radius: 999px;
    border: 1px solid var(--badge-border, #444);
    font-size: 0.78rem;
    line-height: 1.4;
    white-space: nowrap;
  }
  .badge-symbol {
    font-weight: 700;
  }
  .tone-safe,
  .tone-ok {
    --badge-border: #2f7d3a;
    background: #11251a;
    color: #9be0a8;
  }
  .tone-info {
    --badge-border: #2d5a82;
    background: #0f1f2e;
    color: #9cc7ec;
  }
  .tone-warn {
    --badge-border: #8a6d1f;
    background: #2a2310;
    color: #e6c66a;
  }
  .tone-danger {
    --badge-border: #8a2f2f;
    background: #2a1212;
    color: #ef9a9a;
  }
  .tone-muted {
    --badge-border: #4a4a4a;
    background: #1c1c1f;
    color: #b0b0b6;
  }
</style>
