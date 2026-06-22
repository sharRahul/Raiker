<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "./api";
  import type { RuntimeMode } from "./apiTypes";

  let mode = $state<RuntimeMode | null>(null);
  let error = $state<string | null>(null);

  onMount(async () => {
    try {
      mode = await api.runtimeMode();
    } catch (e) {
      error = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  });
</script>

<h1 id="page-title">Runtime Gates</h1>
<p class="lead">Read-only runtime-mode state. Changes are made in Security Settings → Runtime Mutations (M5).</p>

{#if error}
  <p class="state-error">Runtime mode unavailable: {error}</p>
{:else if mode === null}
  <p class="state-loading">Loading runtime mode…</p>
{:else}
  <div class="card">
    <p><span class="k">Mode</span> <code>{mode.mode_name}</code></p>
    <p><span class="k">Status</span> {mode.status}</p>
    <p><span class="k">Activated by</span> {mode.activated_by || "—"}</p>
    <p><span class="k">Allowed modes</span> {mode.allowed_modes.join(", ")}</p>
  </div>
  <p class="hint">Capability gate states are shown on the Capabilities screen.</p>
{/if}

<style>
  .lead {
    color: #c2c2c9;
    max-width: 70ch;
  }
  .card {
    border: 1px solid #2a2a2e;
    border-radius: 10px;
    padding: 0.75rem 1rem;
    background: #101013;
    margin-top: 0.5rem;
  }
  .k {
    color: #8b8b93;
    text-transform: uppercase;
    font-size: 0.66rem;
    letter-spacing: 0.05em;
    margin-right: 0.4rem;
  }
  code {
    color: #cfe5ff;
  }
  .hint {
    color: #8b8b93;
    font-size: 0.82rem;
  }
  .state-error {
    color: #ef9a9a;
  }
  .state-loading {
    color: #9a9aa2;
  }
</style>
