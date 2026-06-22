<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "./api";
  import type { CapabilityGate } from "./apiTypes";
  import Badge from "./Badge.svelte";
  import DisabledCapabilityExplainer from "./DisabledCapabilityExplainer.svelte";
  import { gateBadge, groupByPhase, isDisabled } from "./capabilityModel";

  let gates = $state<CapabilityGate[] | null>(null);
  let error = $state<string | null>(null);
  let expanded = $state<Record<string, boolean>>({});

  const groups = $derived(gates ? groupByPhase(gates) : []);

  onMount(async () => {
    try {
      gates = await api.capabilityGates();
    } catch (e) {
      error = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  });

  function toggle(cap: string) {
    expanded = { ...expanded, [cap]: !expanded[cap] };
  }
</script>

<h1 id="page-title">Capabilities</h1>
<p class="lead">Read-only view of all capability gates. Enabling happens in Security Settings → Runtime Mutations (M5).</p>

{#if error}
  <p class="state-error">Capabilities unavailable: {error}</p>
{:else if gates === null}
  <p class="state-loading">Loading capabilities…</p>
{:else if gates.length === 0}
  <p class="state-empty">No capabilities reported.</p>
{:else}
  {#each groups as group (group.phase)}
    <section class="phase">
      <h2>Phase {group.phase}</h2>
      <ul class="cap-list">
        {#each group.gates as gate (gate.capability)}
          <li>
            <div class="cap-row">
              <code class="cap-name">{gate.capability}</code>
              <Badge variant={gateBadge(gate)} />
              <span class="cap-state">{gate.state}</span>
              {#if isDisabled(gate)}
                <button type="button" class="why" onclick={() => toggle(gate.capability)}>
                  {expanded[gate.capability] ? "Hide" : "Why?"}
                </button>
                <a class="enable-link" href="#/settings">Enable in Security Settings →</a>
              {/if}
            </div>
            {#if isDisabled(gate) && expanded[gate.capability]}
              <DisabledCapabilityExplainer {gate} />
            {/if}
          </li>
        {/each}
      </ul>
    </section>
  {/each}
{/if}

<style>
  .lead {
    color: #c2c2c9;
    max-width: 70ch;
  }
  .phase {
    margin-top: 1rem;
  }
  .cap-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }
  .cap-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex-wrap: wrap;
  }
  .cap-name {
    min-width: 18rem;
    color: #cfe5ff;
  }
  .cap-state {
    color: #8b8b93;
    font-size: 0.78rem;
  }
  .why,
  .enable-link {
    font-size: 0.78rem;
  }
  .why {
    background: none;
    border: 1px solid #3a3a40;
    border-radius: 5px;
    color: #c8c8cf;
    cursor: pointer;
    padding: 0.05rem 0.4rem;
  }
  .why:focus-visible,
  .enable-link:focus-visible {
    outline: 2px solid #6aa9ff;
    outline-offset: 1px;
  }
  .enable-link {
    color: #9cc7ec;
  }
  .state-error {
    color: #ef9a9a;
  }
  .state-loading,
  .state-empty {
    color: #9a9aa2;
  }
</style>
