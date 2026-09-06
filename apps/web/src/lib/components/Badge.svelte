<script lang="ts">
  import { BADGES } from "../badges";
  import type { BadgeVariant } from "../types";

  // `label` overrides the variant's default text (e.g. show the raw backend status
  // "running" on an `active` badge) while keeping the shape + tone cues.
  let { variant, label = null }: { variant: BadgeVariant; label?: string | null } = $props();
  const meta = $derived(BADGES[variant]);
</script>

<span class="badge {meta.tone}" title={meta.description}>
  <span class="badge-symbol" aria-hidden="true">{meta.symbol}</span>
  <span class="badge-label">{label ?? meta.label}</span>
</span>

<style>
  .badge {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    padding: 0.08rem 0.55rem;
    border-radius: var(--r-pill);
    border: 1px solid var(--badge-border);
    background: var(--badge-bg);
    color: var(--badge-fg);
    font-size: var(--text-xs);
    font-weight: 600;
    line-height: 1.5;
    white-space: nowrap;
  }
  .badge-symbol {
    font-weight: 700;
  }
  /* `tone-safe` went with VIS-15: nothing carries it any more, and a tone with
     no user is a colour waiting to be reached for. */
  .tone-ok {
    --badge-border: var(--ok-border);
    --badge-bg: var(--ok-soft);
    --badge-fg: var(--ok);
  }
  .tone-info {
    --badge-border: var(--info-border);
    --badge-bg: var(--info-soft);
    --badge-fg: var(--info);
  }
  .tone-warn {
    --badge-border: var(--warn-border);
    --badge-bg: var(--warn-soft);
    --badge-fg: var(--warn);
  }
  .tone-danger {
    --badge-border: var(--danger-border);
    --badge-bg: var(--danger-soft);
    --badge-fg: var(--danger);
  }
  .tone-muted {
    --badge-border: var(--neutral-border);
    --badge-bg: var(--neutral-soft);
    --badge-fg: var(--text-2);
  }
  .tone-accent {
    --badge-border: var(--accent-border);
    --badge-bg: var(--accent-soft);
    --badge-fg: var(--accent);
  }
</style>
