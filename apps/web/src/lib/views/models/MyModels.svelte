<script lang="ts">
  /**
   * MODEL-04 / MODEL-15 — every model the owner has, as one inventory.
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
   * provider configuration, stop — is in the overflow. That is MODEL-15's rule,
   * and it is a rule about attention rather than about tidiness: five controls
   * repeated down forty rows is two hundred controls, and the owner has to read
   * all of them to find the one that changes what they came to change.
   *
   * The row states come from the MODEL-01 contract, so "selected" here is the
   * same fact the composer picker draws and not a second calculation.
   */
  import Icon from "../../components/Icon.svelte";
  import ProviderLogo from "../../components/ProviderLogo.svelte";
  import EmptyState from "../../components/EmptyState.svelte";
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
    onchanged?: () => void;
  } = $props();

  let openMenu = $state("");
  let query = $state("");

  const key = (profile: ModelProfile) => `${profile.profile_id}\u0000${profile.model}`;

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
    openMenu = "";
    await rememberSurfaceModel(surface, profile.profile_id, profile.model);
    onchanged?.();
  }

  const shown = $derived.by(() => {
    const needle = query.trim().toLowerCase();
    const matching = needle
      ? profiles.filter(
          (profile) =>
            profile.model.toLowerCase().includes(needle) ||
            providerName(profile.provider).toLowerCase().includes(needle),
        )
      : profiles;
    // Selected first, then what can serve, then what cannot. An inventory is
    // read top-down and the top is where the answer to "what is in force"
    // belongs.
    return [...matching].sort((left, right) => {
      const rank = (profile: ModelProfile) =>
        profile.selected ? 0 : isChoosableModel(profile) ? 1 : 2;
      return (
        rank(left) - rank(right) ||
        providerName(left.provider).localeCompare(providerName(right.provider)) ||
        left.model.localeCompare(right.model)
      );
    });
  });

  function toggleMenu(id: string) {
    openMenu = openMenu === id ? "" : id;
  }

  function onWindowClick(event: MouseEvent) {
    const target = event.target as HTMLElement | null;
    if (openMenu !== "" && target?.closest(".row-menu-wrap") === null) openMenu = "";
  }
</script>

<svelte:window onclick={onWindowClick} />

{#if profiles.length === 0}
  <EmptyState
    icon="models"
    title="No models yet"
    body="Connect a provider or set up a local runtime, and every model you add appears here."
  >
    {#snippet action()}
      <a class="btn btn-primary" href="#/models?tab=add">Add a model</a>
    {/snippet}
  </EmptyState>
{:else}
  <div class="inventory">
    <label class="filter">
      <Icon name="search" size="sm" />
      <span class="sr-only">Filter models</span>
      <input
        type="search"
        bind:value={query}
        placeholder="Filter by model or provider"
        aria-label="Filter models"
      />
    </label>

    <ul class="rows">
      {#each shown as profile (key(profile))}
        {@const rowState = rowStateOf(profile)}
        {@const action = primary(profile)}
        {@const defaults = defaultFor(profile)}
        <li>
          <div class="identity">
            <ProviderLogo provider={profile.provider} />
            <div class="names">
              <span class="model">{modelName(profile.model)}</span>
              <span class="where">
                {providerName(profile.provider)} ·
                {profile.off_machine ? "Hosted" : "Local"}
              </span>
            </div>
          </div>

          <div class="marks">
            <!-- VIS2-13 — one primary status token per row, and at most one
                 contextual one. "Selected" and the surface defaults are the
                 contextual half; readiness is the primary. -->
            <span class="state" data-tone={rowState.tone}>{rowState.label}</span>
            {#if profile.selected}<span class="mark">Selected</span>{/if}
            {#each defaults as surface (surface)}
              <span class="mark">{surface} default</span>
            {/each}
          </div>

          <div class="actions">
            {#if action !== null}
              <button
                type="button"
                class="btn btn-sm"
                class:btn-primary={action.kind === "use"}
                disabled={busy}
                onclick={action.run}
              >{action.label}</button>
            {/if}
            <div class="row-menu-wrap">
              <button
                type="button"
                class="btn btn-ghost btn-sm row-more"
                aria-haspopup="menu"
                aria-expanded={openMenu === key(profile)}
                aria-label={`More actions for ${modelName(profile.model)}`}
                onclick={() => toggleMenu(key(profile))}
              ><Icon name="more" size="sm" /></button>
              {#if openMenu === key(profile)}
                <div class="row-menu menu-surface" role="menu">
                  <button
                    type="button"
                    role="menuitem"
                    class="menu-item"
                    onclick={() => { openMenu = ""; ondetails(profile); }}
                  >Details and connection</button>
                  {#each WORK_SURFACES as surface (surface)}
                    <button
                      type="button"
                      role="menuitem"
                      class="menu-item"
                      onclick={() => void setSurfaceDefault(profile, surface)}
                    >Set as {SURFACE_LABEL[surface]} default</button>
                  {/each}
                  {#if !profile.selected && isChoosableModel(profile)}
                    <button
                      type="button"
                      role="menuitem"
                      class="menu-item"
                      onclick={() => { openMenu = ""; onuse(profile); }}
                    >Use as the global model</button>
                  {/if}
                  <button
                    type="button"
                    role="menuitem"
                    class="menu-item"
                    onclick={() => {
                      openMenu = "";
                      openModelSetup(profile, readinessForProfile(profile));
                    }}
                  >Configure provider</button>
                </div>
              {/if}
            </div>
          </div>
        </li>
      {/each}
    </ul>

    {#if shown.length === 0}
      <p class="no-match">No model matches “{query}”.</p>
    {/if}
  </div>
{/if}

<style>
  .inventory {
    display: grid;
    gap: var(--space-3);
  }
  .filter {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    max-width: 22rem;
    padding: 0.3rem 0.55rem;
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: var(--surface);
    color: var(--text-3);
  }
  .filter input {
    flex: 1;
    min-width: 0;
    border: 0;
    background: transparent;
    color: var(--text-1);
    font: inherit;
    font-size: var(--text-sm);
    outline: none;
  }
  .rows {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 2px;
  }
  .rows li {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto auto;
    align-items: center;
    gap: var(--space-3);
    padding: 0.5rem 0.6rem;
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: var(--surface);
  }
  .identity {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    min-width: 0;
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
  /* VIS2-16 — the ordinary state is plain metadata. Only a row that wants
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
  .actions {
    display: flex;
    align-items: center;
    gap: 0.25rem;
  }
  .row-menu-wrap {
    position: relative;
  }
  .row-more {
    padding: 0.25rem 0.4rem;
  }
  .row-menu {
    position: absolute;
    right: 0;
    top: calc(100% + 4px);
    z-index: 40;
    width: max-content;
    min-width: 13rem;
    display: grid;
    gap: 1px;
    padding: 0.25rem;
  }
  .no-match {
    margin: 0;
    color: var(--text-3);
    font-size: var(--text-sm);
  }
  @media (max-width: 47.9rem) {
    .rows li {
      grid-template-columns: minmax(0, 1fr) auto;
    }
    .marks {
      grid-column: 1 / -1;
      justify-content: flex-start;
    }
  }
</style>
