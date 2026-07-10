<script lang="ts">
  import { onMount } from "svelte";
  import Badge from "../components/Badge.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import { api, ApiError } from "../api";
  import type { ModelsView as ModelsData } from "../apiTypes";
  import { capabilityLabel } from "../capabilityModel";
  import { humanize, providerName } from "../format";

  let models = $state<ModelsData | null>(null);
  let loadError = $state<string | null>(null);

  // Editable copy of the user-owned fallback sequence (ordered profile ids).
  let sequence = $state<string[]>([]);
  let saving = $state(false);
  let saveError = $state<string | null>(null);
  let saved = $state(false);
  let addChoice = $state("");

  async function load() {
    loadError = null;
    try {
      models = await api.models();
      sequence = [...models.fallback_sequence];
    } catch (e) {
      models = null;
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }

  // Non-test profiles not already in the sequence — the choices you can add.
  const addable = $derived(
    (models?.profiles ?? []).filter((p) => !sequence.includes(p.profile_id)),
  );

  const dirty = $derived(
    models !== null && JSON.stringify(sequence) !== JSON.stringify(models.fallback_sequence),
  );

  function profileLabel(id: string): string {
    const p = models?.profiles.find((x) => x.profile_id === id);
    return p ? providerName(p.provider) : id;
  }

  function move(index: number, delta: number) {
    const next = index + delta;
    if (next < 0 || next >= sequence.length) return;
    const copy = [...sequence];
    [copy[index], copy[next]] = [copy[next], copy[index]];
    sequence = copy;
    saved = false;
  }

  function remove(index: number) {
    sequence = sequence.filter((_, i) => i !== index);
    saved = false;
  }

  function add() {
    if (addChoice === "" || sequence.includes(addChoice)) return;
    sequence = [...sequence, addChoice];
    addChoice = "";
    saved = false;
  }

  async function save() {
    saving = true;
    saveError = null;
    saved = false;
    try {
      const result = await api.setModelFallback(sequence);
      sequence = [...result.fallback_sequence];
      if (models !== null) models = { ...models, fallback_sequence: result.fallback_sequence };
      saved = true;
    } catch (e) {
      saveError =
        e instanceof ApiError
          ? `Could not save (${e.status}${e.reasonCode ? `: ${e.reasonCode}` : ""})`
          : "Could not save";
    } finally {
      saving = false;
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
            <h2 class="profile-name">{providerName(p.provider)}</h2>
            {#if p.selected}
              <Badge variant="active" label="selected" />
            {/if}
          </div>
          <p class="profile-model">
            {#if p.model === "<model>"}
              <span class="model-unpinned">model chosen at selection</span>
            {:else}
              <code>{p.model}</code>
            {/if}
            · <code class="profile-ref" title="Profile id">{p.profile_id}</code>
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
            {#if p.prompt_cache_ttl}
              <span class="chip chip-ok" title="Prompt caching cuts cost and latency by reusing the stable prompt prefix">
                Cache {p.prompt_cache_ttl}
              </span>
            {/if}
          </div>
        </article>
      {/each}
    </div>
  {/if}

  <section class="card fallback" aria-labelledby="fallback-h">
    <h2 id="fallback-h">Model fallback sequence</h2>
    <p class="sub">
      If the selected provider is unavailable — no network, a timeout, a non-responsive host, or a
      policy denial — Raiker tries these backends in order, top to bottom. Point it at your local
      runtimes (llama.cpp, Ollama, LM Studio, vLLM) so a turn never dead-ends when a hosted API is
      down. Each candidate is still gated by provider policy: listing a hosted provider here never
      grants access on its own.
    </p>

    {#if sequence.length === 0}
      <p class="fallback-empty">No fallback configured. The turn fails closed if the selected provider is unavailable.</p>
    {:else}
      <ol class="fallback-list">
        {#each sequence as id, i (id)}
          <li class="fallback-item">
            <span class="rank">{i + 1}</span>
            <span class="fallback-name">
              {profileLabel(id)}
              <code class="profile-ref">{id}</code>
            </span>
            <span class="fallback-actions">
              <button type="button" class="btn btn-ghost btn-sm" onclick={() => move(i, -1)} disabled={i === 0} aria-label="Move up">↑</button>
              <button type="button" class="btn btn-ghost btn-sm" onclick={() => move(i, 1)} disabled={i === sequence.length - 1} aria-label="Move down">↓</button>
              <button type="button" class="btn btn-ghost btn-sm" onclick={() => remove(i)} aria-label="Remove">Remove</button>
            </span>
          </li>
        {/each}
      </ol>
    {/if}

    <div class="fallback-add">
      <select bind:value={addChoice} aria-label="Add a fallback backend">
        <option value="">Add a backend…</option>
        {#each addable as p (p.profile_id)}
          <option value={p.profile_id}>{providerName(p.provider)} — {p.profile_id}</option>
        {/each}
      </select>
      <button type="button" class="btn btn-sm" onclick={add} disabled={addChoice === ""}>Add</button>
    </div>

    <div class="fallback-save">
      <button type="button" class="btn btn-primary btn-sm" onclick={save} disabled={!dirty || saving}>
        {saving ? "Saving…" : "Save sequence"}
      </button>
      {#if saveError}
        <span class="error" role="alert">{saveError}</span>
      {:else if saved && !dirty}
        <span class="ok-note">Saved.</span>
      {/if}
    </div>
  </section>

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
  .profile-name {
    font-size: 1rem;
    margin: 0;
    overflow-wrap: anywhere;
  }
  .profile-model {
    color: var(--text-2);
    font-size: 0.84rem;
    margin: 0.3rem 0 0.6rem;
    overflow-wrap: anywhere;
  }
  .model-unpinned {
    color: var(--text-3);
    font-style: italic;
  }
  .profile-ref {
    color: var(--text-3);
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
  .fallback {
    margin-top: var(--space-4);
  }
  .fallback-empty {
    color: var(--text-3);
    font-size: 0.84rem;
    margin: 0.5rem 0;
  }
  .fallback-list {
    list-style: none;
    margin: var(--space-3) 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  .fallback-item {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    border: 1px solid var(--neutral-border);
    border-radius: var(--r-md);
    background: var(--neutral-soft);
    padding: 0.4rem 0.6rem;
  }
  .rank {
    font-weight: 700;
    color: var(--text-3);
    min-width: 1.2rem;
    text-align: center;
  }
  .fallback-name {
    flex: 1;
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    flex-wrap: wrap;
    font-weight: 600;
    overflow-wrap: anywhere;
  }
  .fallback-actions {
    display: flex;
    gap: 0.25rem;
  }
  .fallback-add,
  .fallback-save {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin-top: var(--space-3);
    flex-wrap: wrap;
  }
  .fallback-add select {
    padding: 0.35rem 0.5rem;
    border-radius: var(--r-md);
    border: 1px solid var(--neutral-border);
    background: var(--surface-1);
    color: var(--text-1);
    max-width: 22rem;
  }
  .ok-note {
    color: var(--ok);
    font-size: 0.82rem;
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
