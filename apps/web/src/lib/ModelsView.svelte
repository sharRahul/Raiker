<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "./api";
  import type { ModelsView } from "./apiTypes";
  import Badge from "./Badge.svelte";

  let data = $state<ModelsView | null>(null);
  let error = $state<string | null>(null);

  function gateStateLabel(state: string): string {
    return state === "enabled_runtime" || state === "enabled_policy_gated"
      ? state
      : `${state} (fail-closed)`;
  }

  onMount(async () => {
    try {
      data = await api.models();
    } catch (e) {
      error = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  });
</script>

<h1 id="page-title">Models</h1>
<p class="lead">
  Read-only model profiles. No silent fallback to hosted providers; hosted/cloud runtime is
  governed by capability gates.
</p>

{#if error}
  <p class="state-error">Models unavailable: {error}</p>
{:else if data === null}
  <p class="state-loading">Loading models...</p>
{:else}
  <section class="runtime-summary" aria-labelledby="model-runtime-h">
    <h2 id="model-runtime-h">Model Runtime Gates</h2>
    <dl>
      <div>
        <dt>Hosted model runtime</dt>
        <dd>{gateStateLabel(data.hosted_model_gate_state)}</dd>
      </div>
      <div>
        <dt>Private-network model runtime</dt>
        <dd>{gateStateLabel(data.private_network_model_gate_state)}</dd>
      </div>
      <div>
        <dt>Egress allowlist</dt>
        <dd>{data.model_egress_allowlist_configured ? "configured" : "not configured"}</dd>
      </div>
      <div>
        <dt>Off-machine profiles</dt>
        <dd>{data.remote_profile_count}</dd>
      </div>
    </dl>
    <p class="note">
      Silent hosted fallback:
      <strong>{data.no_silent_hosted_fallback ? "disabled" : "enabled"}</strong>.
      Allowlist values and API keys are never shown here.
    </p>
  </section>

  <ul class="models">
    {#each data.profiles as p (p.profile_id)}
      <li class:remote={p.off_machine}>
        <code class="pid">{p.profile_id}</code>
        <span class="prov">{p.provider} / {p.model}</span>
        {#if p.selected}<Badge variant="implemented" />{/if}
        {#if p.off_machine}<Badge variant="approval-required" />{/if}
        <span class="meta">
          {p.local_only ? "local" : "remote"} / {p.endpoint_kind} / {p.default_state}
          {#if p.runtime_gate} / gate: {p.runtime_gate}{/if}
          {#if p.requires_egress_policy} / egress policy{/if}
          {#if p.requires_budget_policy} / budget policy{/if}
        </span>
      </li>
    {/each}
  </ul>
{/if}

<style>
  .lead {
    color: #c2c2c9;
    max-width: 70ch;
  }
  .note {
    color: #b6b6bd;
  }
  .runtime-summary {
    border: 1px solid #2a2a2e;
    border-radius: 10px;
    padding: 0.85rem 1rem;
    background: #101013;
    margin: 1rem 0;
  }
  .runtime-summary h2 {
    margin: 0 0 0.65rem;
    font-size: 0.95rem;
  }
  .runtime-summary dl {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
    gap: 0.55rem;
    margin: 0;
  }
  .runtime-summary dt {
    color: #8b8b93;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .runtime-summary dd {
    margin: 0.15rem 0 0;
    color: #d6d6dc;
    font-family: ui-monospace, monospace;
    font-size: 0.82rem;
  }
  .models {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  .models li {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex-wrap: wrap;
    border-left: 2px solid transparent;
    padding-left: 0.45rem;
  }
  .models li.remote {
    border-left-color: #8a6d1f;
  }
  .pid {
    color: #cfe5ff;
    min-width: 18rem;
  }
  .prov,
  .meta {
    color: #8b8b93;
    font-size: 0.8rem;
  }
  .state-error {
    color: #ef9a9a;
  }
  .state-loading {
    color: #9a9aa2;
  }
</style>
