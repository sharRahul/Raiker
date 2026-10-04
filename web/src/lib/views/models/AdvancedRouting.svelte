<script lang="ts">
  /**
   * UX-MODEL-01 — Advanced routing, out of the Models page into the one
   * component that owns its two state machines: the fallback sequence being
   * edited, and the advisor being chosen and checked.
   *
   * Moved, not changed. The page still decides when an edit is reset — a full
   * read bumps `revision`, which is what used to overwrite these two fields
   * inside the page's own `load()`; the page's quiet re-read does not, so an
   * owner half-way through reordering the sequence keeps their order. What this
   * component saves it compares against the last answer it was given or got
   * back, exactly as the page compared against its own patched snapshot.
   */
  import Icon from "../../components/Icon.svelte";
  import GuideLink from "../../components/GuideLink.svelte";
  import { api, ApiError } from "../../api";
  import type { ModelProfile, ModelsView as ModelsData } from "../../apiTypes";
  import { providerName } from "../../format";
  import { modelName } from "../../modelPresentation";
  import { readinessLabel, UNPINNED_MODEL } from "../../modelReadinessLabels";

  let {
    models,
    revision,
    onreload,
  }: {
    models: ModelsData;
    /** Bumped by the page on every full read; resets the edits here. */
    revision: number;
    /** Ask the page for a full read, after a save whose readiness changed. */
    onreload: () => Promise<void>;
  } = $props();

  // Editable copy of the user-owned fallback sequence (ordered profile ids),
  // and the last sequence the server confirmed, which `dirty` compares with.
  let sequence = $state<string[]>([]);
  let confirmedSequence = $state<string[]>([]);
  let saving = $state(false);
  let saveError = $state<string | null>(null);
  let saved = $state(false);
  let addChoice = $state("");

  // ── Advisor model ──────────────────────────────────────────────────
  let advisorChoice = $state("");
  let confirmedAdvisor = $state("");
  let advisorSaving = $state(false);
  let advisorError = $state<string | null>(null);
  let advisorSaved = $state(false);

  $effect(() => {
    void revision;
    sequence = [...models.fallback_sequence];
    confirmedSequence = [...models.fallback_sequence];
    advisorChoice = models.advisor_profile_id ?? "";
    confirmedAdvisor = models.advisor_profile_id ?? "";
  });

  const advisorCandidates = $derived(models.profiles.filter((p) => p.model !== "<model>"));
  const advisorDirty = $derived(advisorChoice !== confirmedAdvisor);

  // FIXED-160 — the runtime's own request limiter is not a broken page.
  const THROTTLED =
    "Too many requests in the last minute. Raiker throttled this check; wait a moment and try again.";
  const throttled = (e: unknown) => e instanceof ApiError && e.status === 429;

  // BUG-82 — the advisor gets the same readiness chip and repair sentence a
  // provider card gets, because it is a second model this runtime really calls.
  let advisorChecking = $state(false);
  let advisorCheckNote = $state<string | null>(null);
  const advisorChip = $derived(
    models.advisor_profile_id ? readinessLabel(models.advisor_readiness_state) : null,
  );

  async function checkAdvisor() {
    if (!models.advisor_profile_id || !models.advisor_model) return;
    advisorChecking = true;
    advisorCheckNote = null;
    try {
      const readiness = await api.checkModelReadiness(
        models.advisor_profile_id,
        models.advisor_model,
      );
      advisorCheckNote = readiness.remediation
        ? `${readiness.summary} ${readiness.remediation}`
        : readiness.summary;
      await onreload();
    } catch (e) {
      advisorCheckNote = throttled(e) ? THROTTLED : "Raiker could not check the advisor model.";
    } finally {
      advisorChecking = false;
    }
  }

  async function saveAdvisor() {
    advisorSaving = true;
    advisorError = null;
    advisorSaved = false;
    advisorCheckNote = null;
    try {
      const result = await api.setModelAdvisor(advisorChoice || null);
      advisorChoice = result.advisor_profile_id ?? "";
      confirmedAdvisor = advisorChoice;
      advisorSaved = true;
      // A new choice has its own readiness; re-read so the chip describes the
      // model now selected rather than the one it replaced.
      await onreload();
    } catch (e) {
      advisorError =
        e instanceof ApiError
          ? `Could not save (${e.status}${e.reasonCode ? `: ${e.reasonCode}` : ""})`
          : "Could not save";
    } finally {
      advisorSaving = false;
    }
  }

  const addable = $derived(models.profiles.filter((p) => !sequence.includes(p.profile_id)));
  const dirty = $derived(JSON.stringify(sequence) !== JSON.stringify(confirmedSequence));

  /** The page's own rule: a model string that is a choice, on a profile that has it. */
  function namesAModel(profile: ModelProfile): boolean {
    return profile.model !== UNPINNED_MODEL && profile.configured !== false;
  }

  function profileLabel(id: string): string {
    const p = models.profiles.find((x) => x.profile_id === id);
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
      confirmedSequence = [...result.fallback_sequence];
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
</script>

<details class="advanced-routing">
  <summary>
    <span>
      <strong>Advanced routing</strong>
      <small>What runs when the selected model cannot, and the advisor a local model may consult.</small>
    </span>
    <Icon name="chevron-down" size="md" />
  </summary>

  <section class="card fallback" aria-labelledby="fallback-h">
    <h2 id="fallback-h">Model fallback sequence</h2>

    {#if sequence.length === 0}
      <p class="fallback-empty">
        No fallback configured. The turn fails closed if the selected
        provider is unavailable.
      </p>
    {:else}
      <ol class="fallback-list">
        {#each sequence as id, i (id)}
          <li class="fallback-item">
            <span class="rank">{i + 1}</span>
            <span class="fallback-name">
              {profileLabel(id)}
            </span>
            <span class="fallback-actions">
              <button
                type="button"
                class="btn btn-ghost btn-sm"
                onclick={() => move(i, -1)}
                disabled={i === 0}
                aria-label="Move up">↑</button
              >
              <button
                type="button"
                class="btn btn-ghost btn-sm"
                onclick={() => move(i, 1)}
                disabled={i === sequence.length - 1}
                aria-label="Move down">↓</button
              >
              <button
                type="button"
                class="btn btn-ghost btn-sm"
                onclick={() => remove(i)}
                aria-label="Remove">Remove</button
              >
            </span>
          </li>
        {/each}
      </ol>
    {/if}

    <div class="fallback-add">
      <select bind:value={addChoice} aria-label="Add a fallback backend">
        <option value="">Add a backend…</option>
        {#each addable as p (p.profile_id)}
          <option value={p.profile_id}
            >{providerName(p.provider)}{namesAModel(p)
              ? ` (${modelName(p.model)})`
              : " (no model)"}</option
          >
        {/each}
      </select>
      <button
        type="button"
        class="btn btn-sm"
        onclick={add}
        disabled={addChoice === ""}>Add</button
      >
    </div>

    <div class="fallback-save">
      <button
        type="button"
        class="btn btn-primary btn-sm"
        onclick={save}
        disabled={!dirty || saving}
      >
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
      A local model can consult one advisor through the governed
      <code>consult_advisor</code> tool. Picking one grants nothing: every
      consult is still gated at call time.
      <GuideLink section="connecting-a-model" label="How an advisor is governed" />
    </p>
    <div class="advisor-row">
      <select bind:value={advisorChoice} aria-label="Advisor model profile">
        <option value="">No advisor</option>
        {#each advisorCandidates as p (p.profile_id)}
          <option value={p.profile_id}
            >{providerName(p.provider)} — {modelName(p.model)}</option
          >
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
    <!-- BUG-82 — what the last check of the *exact* advisor model found, and
         the one control that repairs it. Without this an owner could pin an
         advisor with no credential, no credit or no running runtime and see
         nothing wrong until a consult failed mid-turn. -->
    {#if models.advisor_profile_id}
      <div class="advisor-readiness">
        {#if advisorChip}
          <span
            class="chip"
            class:chip-ok={models.advisor_readiness_state === "ready"}
            class:chip-warn={models.advisor_readiness_state !== "ready"}
            data-testid="advisor-readiness-chip"
            title={models.advisor_readiness_summary ?? undefined}>{advisorChip}</span
          >
        {/if}
        <span class="advisor-model-name">{modelName(models.advisor_model ?? "")}</span>
        <button
          type="button"
          class="btn btn-ghost btn-sm"
          onclick={checkAdvisor}
          disabled={advisorChecking || !models.advisor_model}
        >
          {advisorChecking ? "Checking…" : "Check advisor"}
        </button>
      </div>
      {#if advisorCheckNote}
        <p class="sub" role="status">{advisorCheckNote}</p>
      {:else if models.advisor_readiness_state !== "ready" && models.advisor_readiness_remediation}
        <p class="sub" role="status">
          {models.advisor_readiness_summary} {models.advisor_readiness_remediation}
        </p>
      {/if}
    {/if}
  </section>
</details>

<style>
  /* REM-MODEL-02 — the advanced-routing disclosure, in the same shape Memory's
     "Advanced memory management" already uses, so a second idiom for "this is
     the tuning" does not appear on a second page. */
  .advanced-routing { border:1px solid var(--border); border-radius:var(--r-lg); background:var(--raised); }
  .advanced-routing > summary {
    display:flex; align-items:center; justify-content:space-between; gap:var(--space-3);
    padding:var(--space-3) var(--space-4); cursor:pointer; color:var(--text-1);
  }
  .advanced-routing > summary span { display:grid; gap:2px; min-width:0; }
  .advanced-routing > summary small { color:var(--text-3); font-size:var(--text-xs); }
  .advanced-routing[open] > summary { border-bottom:1px solid var(--border); }
  .advanced-routing[open] > summary :global(svg) { transform:rotate(180deg); }
  .advanced-routing > :global(section.card) { border:0; border-radius:0; background:transparent; }

  .fallback {
    margin-top: var(--space-4);
  }
  .fallback-empty {
    color: var(--text-3);
    font-size: var(--text-sm);
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
    max-width: 22rem;
    font-size: var(--text-sm);
  }
  .ok-note {
    color: var(--ok);
    font-size: var(--text-sm);
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
  /* BUG-82 — the advisor's readiness sits directly under its selector, in the
     same chip vocabulary a provider card uses, so the two models this runtime
     runs are reported the same way. */
  .advisor-readiness {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex-wrap: wrap;
    margin-top: 0.6rem;
  }
  .advisor-model-name {
    font-family: var(--font-mono, monospace);
    font-size: var(--text-sm);
    color: var(--text-2);
  }
  .advisor-row select {
    max-width: 22rem;
    font-size: var(--text-sm);
  }
  .sub {
    color: var(--text-3);
    font-size: var(--text-sm);
    margin: 0;
  }
</style>
