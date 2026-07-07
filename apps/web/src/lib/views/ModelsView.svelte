<script lang="ts">
  import { onMount } from "svelte";
  import Badge from "../components/Badge.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import { api, ApiError } from "../api";
  import type { ModelsView as ModelsData } from "../apiTypes";
  import { capabilityLabel } from "../capabilityModel";
  import { humanize } from "../format";

  let models = $state<ModelsData | null>(null);
  let loadError = $state<string | null>(null);

  async function load() {
    loadError = null;
    try {
      models = await api.models();
    } catch (e) {
      models = null;
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }

  function endpointLabel(kind: string): string {
    switch (kind) {
      case "local_process":
      case "local":
        return "Local";
      case "private_network":
        return "Home-lab";
      case "remote_hosted":
        return "Hosted";
      default:
        return kind;
    }
  }

  onMount(load);
</script>

<div class="head-row">
  <p class="page-lead">
    The model profiles Raiker can talk to. The choice of backend belongs to you — local, home-lab,
    or hosted — and there is never a silent fallback between them. Selection happens in the terminal
    client (<code>/model use …</code>) or per prompt in Chat → Options.
  </p>
  <button type="button" class="btn btn-ghost btn-sm" onclick={load} aria-label="Refresh models">
    <Icon name="refresh" size={15} />
    Refresh
  </button>
</div>

{#if loadError}
  <p class="error" role="alert">Unavailable: {loadError}</p>
{:else if models === null}
  <p class="loading">Loading…</p>
{:else}
  {#if models.profiles.length === 0}
    <div class="card">
      <EmptyState icon="models" title="No model profiles configured" body="Add profiles in config/model-profiles.json." />
    </div>
  {:else}
    <div class="profile-grid">
      {#each models.profiles as p (p.profile_id)}
        <article class="card profile" class:selected={p.selected}>
          <div class="profile-head">
            <h2 class="profile-id mono">{p.profile_id}</h2>
            {#if p.selected}
              <Badge variant="active" label="selected" />
            {/if}
          </div>
          <p class="profile-model">
            {p.provider} · <code>{p.model}</code>
          </p>
          <div class="chips">
            <span class="chip">{endpointLabel(p.endpoint_kind)}</span>
            {#if p.local_only}
              <span class="chip chip-ok">Local-only</span>
            {/if}
            {#if p.requires_network}
              <span class="chip chip-warn">Needs network</span>
            {/if}
            {#if p.requires_egress_policy}
              <span class="chip chip-warn">Egress-gated</span>
            {/if}
            {#if p.requires_budget_policy}
              <span class="chip chip-warn">Budget-gated</span>
            {/if}
            {#if p.runtime_gate}
              <span class="chip" title="Runtime gate that must be enabled">
                {capabilityLabel(p.runtime_gate)}
              </span>
            {/if}
          </div>
        </article>
      {/each}
    </div>
  {/if}

  <section class="card gate-status" aria-labelledby="model-gates-h">
    <h2 id="model-gates-h">Off-machine provider posture</h2>
    <dl class="gates">
      <div>
        <dt>Hosted model gate</dt>
        <dd>{humanize(models.hosted_model_gate_state)}</dd>
      </div>
      <div>
        <dt>Private-network gate</dt>
        <dd>{humanize(models.private_network_model_gate_state)}</dd>
      </div>
      <div>
        <dt>Egress allowlist</dt>
        <dd><code>{models.model_egress_allowlist_configured ? "configured" : "not configured"}</code></dd>
      </div>
      <div>
        <dt>Off-machine profiles</dt>
        <dd><code>{models.remote_profile_count}</code></dd>
      </div>
    </dl>
    <p class="sub">
      Read-only status. Allowlist values and API keys are never displayed. Hosted providers fail
      closed unless the runtime gate, threat-model acknowledgement, confirmation token, egress
      allowlist, and provider key are all present{models.no_silent_hosted_fallback
        ? " — and there is no silent fallback to hosted models"
        : ""}.
    </p>
  </section>
{/if}

<style>
  .head-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-4);
  }
  .profile-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(18rem, 1fr));
    gap: var(--space-4);
  }
  .profile.selected {
    border-color: var(--accent-border);
    box-shadow: 0 0 0 1px var(--accent-border), var(--shadow-1);
  }
  .profile-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }
  .profile-id {
    font-size: 0.92rem;
    margin: 0;
    overflow-wrap: anywhere;
  }
  .profile-model {
    color: var(--text-2);
    font-size: 0.84rem;
    margin: 0.3rem 0 0.6rem;
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
  }
  .chip {
    font-size: 0.72rem;
    font-weight: 600;
    border-radius: var(--r-pill);
    border: 1px solid var(--neutral-border);
    background: var(--neutral-soft);
    color: var(--text-2);
    padding: 0.08rem 0.55rem;
  }
  .chip-ok {
    border-color: var(--ok-border);
    background: var(--ok-soft);
    color: var(--ok);
  }
  .chip-warn {
    border-color: var(--warn-border);
    background: var(--warn-soft);
    color: var(--warn);
  }
  .gate-status {
    margin-top: var(--space-4);
  }
  .gates {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
    gap: 0.5rem 1rem;
    margin: 0 0 var(--space-3);
  }
  .gates dt {
    font-size: 0.72rem;
    font-weight: 650;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-3);
  }
  .gates dd {
    margin: 0.1rem 0 0;
  }
  .sub {
    color: var(--text-3);
    font-size: 0.8rem;
    margin: 0;
  }
  .error {
    color: var(--danger);
  }
  .loading {
    color: var(--text-2);
  }
</style>
