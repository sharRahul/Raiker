<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "./api";
  import type { ModelsView } from "./apiTypes";
  import Badge from "./Badge.svelte";

  let data = $state<ModelsView | null>(null);
  let error = $state<string | null>(null);

  onMount(async () => {
    try {
      data = await api.models();
    } catch (e) {
      error = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  });
</script>

<h1 id="page-title">Models</h1>
<p class="lead">Read-only model profiles. No silent fallback to hosted providers; hosted/cloud runtime is not enabled.</p>

{#if error}
  <p class="state-error">Models unavailable: {error}</p>
{:else if data === null}
  <p class="state-loading">Loading models…</p>
{:else}
  <p class="note">Silent hosted fallback: <strong>{data.no_silent_hosted_fallback ? "disabled" : "enabled"}</strong></p>
  <ul class="models">
    {#each data.profiles as p (p.profile_id)}
      <li>
        <code class="pid">{p.profile_id}</code>
        <span class="prov">{p.provider} · {p.model}</span>
        {#if p.selected}<Badge variant="implemented" />{/if}
        {#if !p.local_only}<Badge variant="deferred" />{/if}
        <span class="meta">{p.local_only ? "local" : "remote"} · {p.endpoint_kind} · {p.default_state}</span>
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
