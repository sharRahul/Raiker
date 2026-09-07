<script lang="ts">
  // One-glance model truth for the global chrome: which profile is active and
  // whether it stays on this machine. Pure render of GET /api/models — no
  // client-side policy, links to the Models view for detail and changes.
  import type { ModelsView } from "../apiTypes";
  import { humanize, providerName } from "../format";

  let { models }: { models: ModelsView | null } = $props();

  const current = $derived.by(() => {
    if (models === null) return null;
    return (
      models.profiles.find((p) => p.selected) ??
      models.profiles.find((p) => p.profile_id === models.current_profile_id) ??
      null
    );
  });

  const egressOpen = $derived(models?.model_egress_allowlist_configured ?? false);

  function endpointLabel(kind: string): string {
    switch (kind) {
      case "local_process":
      case "local": return "Local";
      case "private_network": return "Home-lab";
      case "remote_hosted": return "Hosted";
      default: return humanize(kind);
    }
  }
</script>

{#if models !== null}
  {#if current === null}
    <a class="chip chip-muted" href="#/models" title="Open Models to choose a profile">
      <span class="glyph" aria-hidden="true">◌</span>
      No model selected
    </a>
  {:else if current.off_machine}
    <a
      class="chip"
      class:chip-info={egressOpen}
      class:chip-warn={!egressOpen}
      href="#/models"
      title={`${providerName(current.provider)} · ${current.model} · ${endpointLabel(current.endpoint_kind)}`}
    >
      <span class="glyph" aria-hidden="true">▲</span>
      Hosted · {providerName(current.provider)}
      <span class="egress">{egressOpen ? "egress open" : "egress closed"}</span>
    </a>
  {:else}
    <a
      class="chip chip-local"
      href="#/models"
      title={`${providerName(current.provider)} · ${current.model} · ${endpointLabel(current.endpoint_kind)}`}
    >
      <span class="glyph" aria-hidden="true">●</span>
      Local · {providerName(current.provider)}
    </a>
  {/if}
{/if}

<style>
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: var(--text-xs);
    font-weight: 600;
    padding: 0.18rem 0.6rem;
    border-radius: var(--r-pill);
    border: 1px solid var(--neutral-border);
    background: var(--neutral-soft);
    color: var(--text-2);
    white-space: nowrap;
    text-decoration: none;
  }
  .chip:hover {
    text-decoration: none;
    border-color: var(--border-strong);
  }
  .chip-local {
    border-color: var(--accent-border);
    background: var(--accent-soft);
    color: var(--accent);
  }
  .chip-info {
    border-color: var(--info-border);
    background: var(--info-soft);
    color: var(--info);
  }
  .chip-warn {
    border-color: var(--warn-border);
    background: var(--warn-soft);
    color: var(--warn);
  }
  .chip-muted {
    color: var(--text-3);
  }
  .glyph {
    font-size: var(--text-2xs);
    line-height: 1;
  }
  .egress {
    font-weight: 500;
    opacity: 0.85;
    border-left: 1px solid currentColor;
    padding-left: 0.35rem;
    margin-left: 0.05rem;
  }
</style>
