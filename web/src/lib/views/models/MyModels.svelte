<script lang="ts">
  /**
   * Every model the owner has, as one inventory.
   *
   * The page listed models inside provider cards, which put the same model in a
   * different visual container depending on who serves it: a local GGUF was a
   * runtime row with Test, Details, Select, Scan folders and Serve selected
   * beside it, while a hosted model was a catalogue entry with a keep-available
   * switch and a Use button. Two vocabularies, two layouts, one question — "what
   * can answer a turn, and which one is in force".
   *
   * One row per model, and one visible primary action, chosen by state:
   *
   *     ready and not selected      Use
   *     selected but stopped        Start
   *     configured but not usable   Fix
   *     selected and ready          nothing
   *
   * Everything else — details, connection test, the three per-surface defaults,
   * provider configuration, stop — is in the overflow. That is the one-primary-action rule,
   * and it is a rule about attention rather than about tidiness: five controls
   * repeated down forty rows is two hundred controls, and the owner has to read
   * all of them to find the one that changes what they came to change.
   *
   * The row states come from the model-decision contract, so "selected" here is the
   * same fact the composer picker draws and not a second calculation.
   */
  import ProviderLogo from "../../components/ProviderLogo.svelte";
  import EmptyState from "../../components/EmptyState.svelte";
  import ListDetail from "../../components/ListDetail.svelte";
  import ProviderUsagePanel from "./ProviderUsagePanel.svelte";
  import { providerName } from "../../format";
  import { modelName } from "../../modelPresentation";
  import { isChoosableModel, openModelSetup, readinessForProfile } from "../../modelReadiness.svelte";
  import { readinessLabel, UNPINNED_MODEL } from "../../modelReadinessLabels";
  import { WORK_SURFACES, rememberSurfaceModel, type Surface } from "../../surfaceModel.svelte";
  import type { ModelDecision, ModelProfile } from "../../apiTypes";

  let {
    profiles,
    decisions,
    busy = false,
    onuse,
    onstart,
    ondetails,
    onadd = () => {},
    onchanged,
  }: {
    profiles: ModelProfile[];
    /** Every surface's decision, so a row can say what it is the default for. */
    decisions: Record<string, ModelDecision> | null;
    busy?: boolean;
    /** Make this the global model. */
    onuse: (profile: ModelProfile) => void;
    /** Start the managed local runtime behind this profile. */
    onstart: (profile: ModelProfile) => void;
    ondetails: (profile: ModelProfile) => void;
    /** Opens the Add model dialog. */
    onadd?: () => void;
    onchanged?: () => void;
  } = $props();

  let selectedId = $state<string | null>(null);

  const key = (profile: ModelProfile) => `${profile.profile_id}\u0000${profile.model}`;

  /**
   * What to call a row.
   *
   * A profile that has not been given a model still carries the registry's
   * `<model>` placeholder, and printing it turned the inventory's most
   * prominent column into a row of `‹model›` — Raiker's own internal notation,
   * offered to the owner as the name of a thing. The provider is the true
   * answer to "what is this row": it is the account or runtime they connected,
   * and the state beside it already says a model has still to be chosen.
   */
  function rowName(profile: ModelProfile): string {
    return !profile.model || profile.model === UNPINNED_MODEL
      ? providerName(profile.provider)
      : modelName(profile.model);
  }

  const SURFACE_LABEL: Record<string, string> = {
    chat: "Chat",
    build: "Build",
    design: "Design",
  };

  /** Which Work surfaces name this exact pair as their default. */
  function defaultFor(profile: ModelProfile): string[] {
    if (decisions === null) return [];
    return WORK_SURFACES.filter((surface) => {
      const decision = decisions[surface];
      return (
        decision !== undefined &&
        decision.selected.source === "surface_default" &&
        decision.selected.profile_id === profile.profile_id &&
        decision.selected.model === profile.model
      );
    }).map((surface) => SURFACE_LABEL[surface] ?? surface);
  }

  /** Whether a managed local process is serving this profile, or null. */
  function running(profile: ModelProfile): boolean | null {
    if (decisions === null) return null;
    for (const decision of Object.values(decisions)) {
      if (
        decision.effective.profile_id === profile.profile_id &&
        decision.effective.model === profile.model
      ) {
        return decision.running;
      }
    }
    return null;
  }

  /**
   * The row's state, in the vocabulary the review fixes: Selected, Default,
   * Ready, Running, Available. Never "active", which was one word covering all
   * five and is what made the page impossible to reason about.
   */
  function rowStateOf(profile: ModelProfile): { label: string; tone: "plain" | "warn" } {
    if (!profile.model || profile.model === UNPINNED_MODEL) {
      return { label: "Choose a model", tone: "warn" };
    }
    if (!isChoosableModel(profile)) {
      return { label: readinessLabel(profile.readiness_state) ?? "Not set up", tone: "warn" };
    }
    if (running(profile) === false) return { label: "Stopped", tone: "warn" };
    return { label: readinessLabel(profile.readiness_state) ?? "Available", tone: "plain" };
  }

  /**
   * The single visible action, or null when the row needs none.
   *
   * A selected, ready model gets no button at all. That is the point: the
   * inventory should be quiet where nothing is required, so the rows that do
   * ask for something are the ones you see.
   */
  function primary(
    profile: ModelProfile,
  ): { label: string; run: () => void; kind: "use" | "start" | "fix" } | null {
    const choosable = isChoosableModel(profile);
    if (!choosable || !profile.model || profile.model === UNPINNED_MODEL) {
      return {
        label: "Fix",
        kind: "fix",
        run: () => openModelSetup(profile, readinessForProfile(profile)),
      };
    }
    if (profile.selected && running(profile) === false) {
      return { label: "Start", kind: "start", run: () => onstart(profile) };
    }
    if (profile.selected) return null;
    return { label: "Use", kind: "use", run: () => onuse(profile) };
  }

  async function setSurfaceDefault(profile: ModelProfile, surface: Surface) {
    await rememberSurfaceModel(surface, profile.profile_id, profile.model);
    onchanged?.();
  }

  // Selected first, then what can serve, then what cannot. An inventory is
  // read top-down and the top is where the answer to "what is in force"
  // belongs.
  const shown = $derived(
    [...profiles].sort((left, right) => {
      const rank = (profile: ModelProfile) =>
        profile.selected ? 0 : isChoosableModel(profile) ? 1 : 2;
      return (
        rank(left) - rank(right) ||
        providerName(left.provider).localeCompare(providerName(right.provider)) ||
        left.model.localeCompare(right.model)
      );
    }),
  );
</script>

{#if profiles.length === 0}
  <EmptyState
    icon="models"
    title="No models yet"
    body="Connect a provider or set up a local model server, and every model you add appears here."
  >
    {#snippet action()}
      <button type="button" class="btn btn-primary" onclick={onadd}>Add a model</button>
    {/snippet}
  </EmptyState>
{:else}
  <!-- QUI-L08 — My models in layout B: one row per model with its state in
       words, and the chosen model's actions and usage beside the list. -->
  <ListDetail
    items={shown}
    key={key}
    label="My models"
    matches={(profile, query) =>
      `${profile.model} ${providerName(profile.provider)}`.toLowerCase().includes(query)}
    searchLabel="Filter models"
    storageKey="models"
    autoSelectFirst={true}
    syncAddress={false}
    bind:selectedId
  >
    {#snippet row(profile)}
      {@const rowState = rowStateOf(profile)}
      <ProviderLogo provider={profile.provider} />
      <span class="names">
        <span class="model">{rowName(profile)}</span>
        <span class="where">
          {profile.off_machine ? "Hosted" : "Local"} · <span class="state" data-tone={rowState.tone}>{rowState.label}</span>{#if profile.selected} · Selected{/if}
        </span>
      </span>
    {/snippet}
    {#snippet detail(profile)}
      {@const rowState = rowStateOf(profile)}
      {@const action = primary(profile)}
      {@const defaults = defaultFor(profile)}
      <article class="model-detail" aria-label={rowName(profile)}>
        <header>
          <ProviderLogo provider={profile.provider} size={32} />
          <div>
            <h3>{rowName(profile)}</h3>
            <p class="where">
              {providerName(profile.provider)} ·
              {profile.off_machine ? `Sent to ${providerName(profile.provider)}` : "Stays on this computer"}
            </p>
          </div>
        </header>
        <p class="marks">
          <span class="state" data-tone={rowState.tone}>{rowState.label}</span>
          {#if profile.selected}<span class="mark">Selected</span>{/if}
          {#each defaults as surface (surface)}
            <span class="mark">{surface} default</span>
          {/each}
        </p>
        <div class="detail-actions">
          {#if action !== null}
            <button
              type="button"
              class="btn btn-sm"
              class:btn-primary={action.kind === "use"}
              disabled={busy}
              onclick={action.run}
            >{action.label}</button>
          {/if}
          <button type="button" class="btn btn-sm btn-ghost" onclick={() => ondetails(profile)}>
            Details and connection
          </button>
          <button
            type="button"
            class="btn btn-sm btn-ghost"
            onclick={() => openModelSetup(profile, readinessForProfile(profile))}
          >Configure provider</button>
        </div>
        <div class="defaults" role="group" aria-label={`Use ${rowName(profile)} by default in`}>
          {#each WORK_SURFACES as surface (surface)}
            <button
              type="button"
              class="btn btn-sm btn-ghost"
              disabled={busy}
              onclick={() => void setSurfaceDefault(profile, surface)}
            >Set as {SURFACE_LABEL[surface]} default</button>
          {/each}
        </div>
        <ProviderUsagePanel provider={profile.provider} />
      </article>
    {/snippet}
  </ListDetail>
{/if}

<style>
  .model-detail {
    display: grid;
    gap: var(--space-3);
  }
  .model-detail header {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }
  .model-detail h3 {
    margin: 0;
    font-size: var(--text-lg);
    overflow-wrap: anywhere;
  }
  .model-detail .where {
    margin: 0.1rem 0 0;
  }
  .detail-actions,
  .defaults {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }
  .model-detail .marks {
    justify-content: flex-start;
    margin: 0;
  }

  .names {
    display: grid;
    gap: 0.05rem;
    min-width: 0;
  }
  .model {
    font-size: var(--text-sm);
    color: var(--text-1);
    overflow-wrap: anywhere;
  }
  .where {
    font-size: var(--text-2xs);
    color: var(--text-3);
  }
  .marks {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    flex-wrap: wrap;
    justify-content: flex-end;
  }
  /* The ordinary state is plain metadata. Only a row that wants
     something from the owner is toned. */
  .state {
    font-size: var(--text-2xs);
    font-weight: 650;
    color: var(--text-2);
    white-space: nowrap;
  }
  .state[data-tone="warn"] {
    color: var(--warn);
  }
  .mark {
    padding: 0.05rem 0.4rem;
    border: 1px solid var(--border);
    border-radius: var(--r-pill);
    color: var(--text-3);
    font-size: var(--text-2xs);
    white-space: nowrap;
  }

  @media (max-width: 47.9rem) {

    .marks {
      grid-column: 1 / -1;
      justify-content: flex-start;
    }
  }
</style>
