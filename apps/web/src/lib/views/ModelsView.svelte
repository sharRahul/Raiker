<script lang="ts">
  import { onMount } from "svelte";
  import Badge from "../components/Badge.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import { api, ApiError } from "../api";
  import type { ModelsView as ModelsData, ProviderModelList } from "../apiTypes";
  import { capabilityLabel } from "../capabilityModel";
  import { humanize, providerName } from "../format";

  // The shell owns a models snapshot for the topbar chip; it passes onchanged
  // so a selection here is reflected there without a full page reload.
  let { onchanged }: { onchanged?: () => void } = $props();

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
      advisorChoice = models.advisor_profile_id ?? "";
    } catch (e) {
      models = null;
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }

  // ── Model selection (per provider card) ──────────────────────────────
  // One picker open at a time. The model list comes from the provider itself,
  // on demand; when the catalogue is unavailable the user can type a model id.
  let pickerFor = $state<string | null>(null);
  let pickerList = $state<ProviderModelList | null>(null);
  let pickerLoading = $state(false);
  let pickerChoice = $state("");
  let selecting = $state(false);
  let selectError = $state<string | null>(null);

  async function openPicker(profileId: string) {
    if (pickerFor === profileId) {
      closePicker();
      return;
    }
    pickerFor = profileId;
    pickerList = null;
    pickerChoice = "";
    selectError = null;
    pickerLoading = true;
    try {
      pickerList = await api.providerModels(profileId);
    } catch {
      pickerList = null; // manual entry still works
    } finally {
      pickerLoading = false;
    }
  }

  function closePicker() {
    pickerFor = null;
    pickerList = null;
    pickerChoice = "";
    selectError = null;
  }

  async function select(profileId: string, model = "") {
    selecting = true;
    selectError = null;
    try {
      await api.selectModel(profileId, model.trim() || undefined);
      closePicker();
      await load();
      onchanged?.();
    } catch (e) {
      selectError =
        e instanceof ApiError
          ? `Could not select (${e.status}${e.reasonCode ? `: ${e.reasonCode}` : ""})`
          : "Could not select";
    } finally {
      selecting = false;
    }
  }

  // ── Advisor model (web-app task 2) ───────────────────────────────────
  // The profile a local model may consult through the governed consult_advisor
  // tool. Choosing one grants nothing: the consult is gated by the
  // advisor_model_runtime capability, its decision mode, and provider policy.
  let advisorChoice = $state("");
  let advisorSaving = $state(false);
  let advisorError = $state<string | null>(null);
  let advisorSaved = $state(false);

  // Only profiles with a concrete model can advise (fail-closed server-side too).
  const advisorCandidates = $derived(
    (models?.profiles ?? []).filter((p) => p.model !== "<model>"),
  );
  const advisorDirty = $derived(
    models !== null && advisorChoice !== (models.advisor_profile_id ?? ""),
  );

  async function saveAdvisor() {
    advisorSaving = true;
    advisorError = null;
    advisorSaved = false;
    try {
      const result = await api.setModelAdvisor(advisorChoice || null);
      if (models !== null) {
        models = { ...models, advisor_profile_id: result.advisor_profile_id };
      }
      advisorChoice = result.advisor_profile_id ?? "";
      advisorSaved = true;
    } catch (e) {
      advisorError =
        e instanceof ApiError
          ? `Could not save (${e.status}${e.reasonCode ? `: ${e.reasonCode}` : ""})`
          : "Could not save";
    } finally {
      advisorSaving = false;
    }
  }

  function pickerNote(list: ProviderModelList): string {
    switch (list.status) {
      case "policy_denied":
        return "Model list denied by provider policy — enable the provider's gate first. You can still type a model id.";
      case "unsupported":
        return "This provider does not support model listing — type a model id.";
      default:
        return "Provider unreachable — type a model id if you know it.";
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
    or hosted — and there is never a silent fallback between them. Select a provider here (and,
    where the provider serves several, the exact model), per prompt in Chat → Options, or in the
    terminal client (<code>/model use …</code>).
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

          <div class="select-row">
            {#if !p.selected && p.model !== "<model>"}
              <button
                type="button"
                class="btn btn-sm"
                onclick={() => void select(p.profile_id)}
                disabled={selecting}
              >
                Select
              </button>
            {/if}
            <button
              type="button"
              class="btn btn-ghost btn-sm"
              onclick={() => void openPicker(p.profile_id)}
              aria-expanded={pickerFor === p.profile_id}
            >
              {p.model === "<model>" ? "Choose model…" : "Change model…"}
            </button>
          </div>

          {#if pickerFor === p.profile_id}
            <div class="picker">
              {#if pickerLoading}
                <p class="picker-note" role="status">Loading models from {providerName(p.provider)}…</p>
              {:else}
                {#if pickerList !== null && pickerList.status === "available" && pickerList.models.length > 0}
                  <select class="picker-select" bind:value={pickerChoice} aria-label="Available models">
                    <option value="">Pick a model…</option>
                    {#each pickerList.models as m (m)}
                      <option value={m}>{m}</option>
                    {/each}
                  </select>
                {:else}
                  {#if pickerList !== null}
                    <p class="picker-note">{pickerNote(pickerList)}</p>
                  {:else}
                    <p class="picker-note">Model list unavailable — type a model id.</p>
                  {/if}
                  <input
                    class="picker-input"
                    type="text"
                    placeholder="model id"
                    bind:value={pickerChoice}
                    aria-label="Model id"
                  />
                {/if}
                <div class="picker-actions">
                  <button
                    type="button"
                    class="btn btn-primary btn-sm"
                    onclick={() => void select(p.profile_id, pickerChoice)}
                    disabled={selecting || pickerChoice.trim() === ""}
                  >
                    {selecting ? "Selecting…" : "Use model"}
                  </button>
                  <button type="button" class="btn btn-ghost btn-sm" onclick={closePicker}>
                    Cancel
                  </button>
                </div>
                {#if selectError}
                  <p class="error picker-error" role="alert">{selectError}</p>
                {/if}
              {/if}
            </div>
          {/if}
        </article>
      {/each}
    </div>
    {#if selectError && pickerFor === null}
      <p class="error" role="alert">{selectError}</p>
    {/if}
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

  <section class="card advisor" aria-labelledby="advisor-h">
    <h2 id="advisor-h">Advisor model</h2>
    <p class="sub">
      When you run a local model, it can consult one advisor — typically a hosted model — through
      the governed <code>consult_advisor</code> tool. Picking an advisor grants nothing on its own:
      the consult is gated by the <code>advisor_model_runtime</code> capability, its decision mode
      (default <strong>ask</strong>, which withholds the consult), and the provider's own policy
      (hosted gate, egress allowlist, API key) at call time. The advisor's answer is always treated
      as untrusted data, and the question/answer never enter the audit log — only lengths do.
    </p>
    <div class="advisor-row">
      <select bind:value={advisorChoice} aria-label="Advisor model profile">
        <option value="">No advisor</option>
        {#each advisorCandidates as p (p.profile_id)}
          <option value={p.profile_id}>{providerName(p.provider)} — {p.model}</option>
        {/each}
      </select>
      <button
        type="button"
        class="btn btn-primary btn-sm"
        onclick={saveAdvisor}
        disabled={!advisorDirty || advisorSaving}
      >
        {advisorSaving ? "Saving…" : "Save advisor"}
      </button>
      {#if advisorError}
        <span class="error" role="alert">{advisorError}</span>
      {:else if advisorSaved && !advisorDirty}
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
  .select-row {
    display: flex;
    gap: 0.4rem;
    margin-top: 0.6rem;
  }
  .picker {
    margin-top: 0.55rem;
    border-top: 1px dashed var(--border);
    padding-top: 0.55rem;
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
  }
  .picker-select,
  .picker-input {
    padding: 0.35rem 0.5rem;
    border-radius: var(--r-md);
    border: 1px solid var(--neutral-border);
    background: var(--surface-1);
    color: var(--text-1);
    max-width: 100%;
  }
  .picker-note {
    font-size: 0.76rem;
    color: var(--text-3);
    margin: 0;
  }
  .picker-actions {
    display: flex;
    gap: 0.4rem;
  }
  .picker-error {
    font-size: 0.78rem;
    margin: 0;
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
  .advisor {
    margin-top: var(--space-4);
  }
  .advisor .sub {
    margin-bottom: var(--space-3);
  }
  .advisor-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex-wrap: wrap;
  }
  .advisor-row select {
    padding: 0.35rem 0.5rem;
    border-radius: var(--r-md);
    border: 1px solid var(--neutral-border);
    background: var(--surface-1);
    color: var(--text-1);
    max-width: 22rem;
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
