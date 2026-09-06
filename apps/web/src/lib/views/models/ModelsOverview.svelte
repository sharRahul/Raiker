<script lang="ts">
  /**
   * MODEL-03 — what the Models page should say before it says anything else.
   *
   * The page opened on six equal tabs — Local, Hosted, Hugging Face, Activity,
   * Routing, Pricing — which is a filing system for the data rather than an
   * answer to why anyone came. An owner arriving here is nearly always asking
   * one of five questions, and all five were reachable only by choosing a tab
   * whose name is about *where the rows are stored*:
   *
   *   1. What model is running my work?
   *   2. Will it actually run?
   *   3. If not, what one thing fixes it?
   *   4. What do Chat, Build and Design each default to?
   *   5. Where do I go when I want to change something deliberately?
   *
   * This panel answers 1–4 above the fold and leaves 5 to the tabs. Everything
   * it renders comes from `/api/model-decisions` (MODEL-01), so it cannot
   * disagree with the composer picker about which model is in force — before
   * that contract existed, the page and the composer assembled separate answers
   * from the same five stores and agreed by coincidence.
   *
   * MODEL-13 — health is exception-led. A healthy provider gets no card and no
   * Test button: a wall of green cards each offering a check is a page that
   * reports "nothing is wrong" in the most expensive way available, and it
   * trains the owner to ignore the one card that is not green. Only what needs
   * attention appears, and each entry carries the one action that resolves it.
   */
  import Icon from "../../components/Icon.svelte";
  import ProviderLogo from "../../components/ProviderLogo.svelte";
  import PageState from "../../components/PageState.svelte";
  import { modelDecisions } from "../../surfaceModel.svelte";
  import { providerName } from "../../format";
  import { modelName } from "../../modelPresentation";
  import { isChoosableModel } from "../../modelReadiness.svelte";
  import type { ModelDecision, ModelProfile, ModelsView } from "../../apiTypes";

  let {
    models,
    /** Opens the tab that owns a fix, so a remedy is never a dead end. */
    onopen,
  }: {
    models: ModelsView | null;
    onopen: (tab: string) => void;
  } = $props();

  let decisions = $state<Record<string, ModelDecision> | null>(null);
  /** False until the first read answers, so "loading" and "unreadable"
   *  stay two different states rather than both being `decisions === null`. */
  let read = $state(false);

  /**
   * The Work modes, in product order, and the two surfaces that capture a model
   * onto the thing they create rather than holding a live default.
   *
   * MODEL-11's rule is enforced by this shape: `Default`, `Selected`,
   * `Effective` and `Fallback` are four different words for four different
   * facts, and the page used to call all of them "active".
   */
  const WORK = [
    { id: "chat", label: "Chat", hint: "Conversation" },
    { id: "build", label: "Build", hint: "Code and agent work" },
    { id: "design", label: "Design", hint: "Images" },
  ] as const;
  const CAPTURED = [
    { id: "tasks", label: "Tasks" },
    { id: "schedule", label: "Schedule" },
  ] as const;

  async function load() {
    decisions = await modelDecisions();
    read = true;
  }

  function decisionFor(surface: string): ModelDecision | null {
    return decisions?.[surface] ?? null;
  }

  /** The profile behind a decision, for its provider mark. */
  function profileFor(decision: ModelDecision | null): ModelProfile | null {
    if (decision === null || models === null) return null;
    return (
      models.profiles.find(
        (profile) =>
          profile.profile_id === decision.selected.profile_id &&
          profile.model === decision.selected.model,
      ) ??
      models.profiles.find((profile) => profile.profile_id === decision.selected.profile_id) ??
      null
    );
  }

  /**
   * One line per surface, in the four-word vocabulary MODEL-11 insists on.
   *
   * `Default` is what the surface starts on. `Effective` is what will really
   * answer. They are the same in the ordinary case and the row says nothing
   * extra; when they are not, the row says which and why, because a page that
   * silently prints the fallback under the heading "Default" is how an owner
   * comes to believe their choice was not saved.
   */
  const workRows = $derived(
    WORK.map((surface) => {
      const decision = decisionFor(surface.id);
      return {
        ...surface,
        decision,
        profile: profileFor(decision),
        displaced:
          decision !== null && decision.effective.reason === "fallback"
            ? decision.effective
            : null,
      };
    }),
  );

  /**
   * What needs a person. Built from the decisions rather than from a separate
   * health sweep, so the list cannot claim a problem the model contract does
   * not have — and cannot miss one it does.
   */
  const attention = $derived(
    workRows
      .filter((row) => row.decision !== null && row.decision.problem !== null)
      .map((row) => ({
        surface: row.label,
        model: row.decision!.selected.model,
        problem: row.decision!.problem!,
        // A local model that is selected and merely stopped is started from
        // Runtime; anything else is a connection or a catalogue, which is
        // where "Add model" and the provider list live.
        tab: row.decision!.running === false ? "runtime" : "models",
      })),
  );

  /**
   * Models that could serve right now and are not already the answer anywhere.
   *
   * The point of the section is a decision the owner can make in one click when
   * something is wrong; listing what is already in use would be restating the
   * rows above it.
   */
  const alternatives = $derived.by(() => {
    if (models === null) return [];
    const inUse = new Set(
      workRows
        .flatMap((row) => [row.decision?.selected, row.decision?.effective])
        .filter((choice) => choice !== undefined)
        .map((choice) => `${choice!.profile_id}\u0000${choice!.model}`),
    );
    return models.profiles
      .filter(
        (profile) =>
          isChoosableModel(profile) &&
          !inUse.has(`${profile.profile_id}\u0000${profile.model}`),
      )
      .slice(0, 6);
  });

  $effect(() => {
    // Re-read whenever the page reloads its models, so choosing a model on
    // another tab is reflected here without a navigation.
    void models;
    void load();
  });
</script>

<div class="overview">
  {#if read && decisions === null}
    <PageState
      state="error"
      title="Couldn't read which model is in force"
      detail="The page below still works. Nothing was changed."
    />
  {:else if !read}
    <PageState state="loading" title="Reading your model setup…" />
  {:else}
    <!-- MODEL-13 — exceptions only. When this section is absent, that is the
         report: there is nothing to fix. -->
    {#if attention.length > 0}
      <section class="card attention" aria-labelledby="attention-h">
        <h3 id="attention-h">Needs attention</h3>
        <ul>
          {#each attention as item (item.surface)}
            <li>
              <div class="attention-copy">
                <p class="attention-what">
                  <strong>{item.surface}</strong> · {modelName(item.model)}
                </p>
                <p class="attention-why">{item.problem.summary}</p>
                <p class="attention-fix">{item.problem.remediation}</p>
              </div>
              <button
                type="button"
                class="btn btn-sm"
                onclick={() => onopen(item.tab)}
              >Fix</button>
            </li>
          {/each}
        </ul>
      </section>
    {/if}

    <section class="card work" aria-labelledby="work-h">
      <div class="card-head">
        <h3 id="work-h">What powers your work</h3>
        <button type="button" class="btn btn-ghost btn-sm" onclick={() => onopen("runtime")}>
          Edit defaults
        </button>
      </div>
      <ul class="work-rows">
        {#each workRows as row (row.id)}
          <li>
            <div class="surface">
              <span class="surface-name">{row.label}</span>
              <span class="surface-hint">{row.hint}</span>
            </div>
            <div class="choice">
              {#if row.decision === null || row.decision.selected.model === ""}
                <span class="unset">No model yet</span>
              {:else}
                <span class="choice-name">
                  {#if row.profile}<ProviderLogo provider={row.profile.provider} />{/if}
                  {modelName(row.decision.selected.model)}
                </span>
                <span class="choice-where">
                  {row.profile ? providerName(row.profile.provider) : "Unknown provider"}
                  {#if row.decision.selected.source === "surface_default"}
                    · chosen for {row.label}
                  {:else if row.decision.selected.source === "global_default"}
                    · your global choice
                  {:else}
                    · Raiker's default
                  {/if}
                </span>
                {#if row.displaced !== null}
                  <!-- MODEL-01's invariant, rendered: the choice stays, and the
                       model that will really answer is named beside it rather
                       than quietly replacing it. -->
                  <span class="displaced">
                    Using {modelName(row.displaced.model)} for now
                  </span>
                {/if}
              {/if}
            </div>
            <span class="state" data-state={row.decision?.ready ? "ready" : "blocked"}>
              {row.decision?.ready ? "Ready" : "Not ready"}
            </span>
          </li>
        {/each}
      </ul>
      <p class="captured">
        {#each CAPTURED as surface, index (surface.id)}
          {index > 0 ? " and " : ""}{surface.label}
        {/each}
        capture the model chosen when the work is created, so a run that fires
        next week uses the model it was scheduled with.
      </p>
    </section>

    {#if alternatives.length > 0}
      <section class="card alternatives" aria-labelledby="alternatives-h">
        <div class="card-head">
          <h3 id="alternatives-h">Ready alternatives</h3>
          <button type="button" class="btn btn-ghost btn-sm" onclick={() => onopen("models")}>
            All models
          </button>
        </div>
        <ul class="alt-rows">
          {#each alternatives as profile (`${profile.profile_id}\u0000${profile.model}`)}
            <li>
              <ProviderLogo provider={profile.provider} />
              <span class="alt-name">{modelName(profile.model)}</span>
              <span class="alt-where">{providerName(profile.provider)}</span>
            </li>
          {/each}
        </ul>
      </section>
    {:else if models !== null && models.profiles.length > 0}
      <p class="none-spare">
        <Icon name="info" size="sm" />
        Every model you have set up is already in use above.
      </p>
    {/if}
  {/if}
</div>

<style>
  .overview {
    display: grid;
    gap: var(--space-4);
  }
  .card-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-3);
  }
  .card-head h3,
  .attention h3 {
    margin: 0;
  }
  /* MODEL-13 — the one section allowed a tone, because it is the one that is
     absent when nothing is wrong. */
  .attention {
    border-color: var(--warn-border);
    background: var(--warn-soft);
  }
  .attention ul {
    list-style: none;
    margin: var(--space-3) 0 0;
    padding: 0;
    display: grid;
    gap: var(--space-3);
  }
  .attention li {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-3);
  }
  .attention-copy {
    display: grid;
    gap: 0.1rem;
    min-width: 0;
  }
  .attention-what {
    margin: 0;
    font-size: var(--text-sm);
    color: var(--text-1);
  }
  .attention-why,
  .attention-fix {
    margin: 0;
    font-size: var(--text-xs);
    color: var(--text-2);
  }
  .work-rows,
  .alt-rows {
    list-style: none;
    margin: var(--space-3) 0 0;
    padding: 0;
    display: grid;
    gap: 2px;
  }
  .work-rows li {
    display: grid;
    grid-template-columns: minmax(6rem, 9rem) minmax(0, 1fr) auto;
    align-items: center;
    gap: var(--space-3);
    padding: 0.5rem 0.55rem;
    border-radius: var(--r-sm);
  }
  .work-rows li:nth-child(odd) {
    background: var(--sunken);
  }
  .surface {
    display: grid;
    gap: 0.05rem;
    min-width: 0;
  }
  .surface-name {
    font-size: var(--text-sm);
    font-weight: 650;
    color: var(--text-1);
  }
  .surface-hint {
    font-size: var(--text-2xs);
    color: var(--text-3);
  }
  .choice {
    display: grid;
    gap: 0.05rem;
    min-width: 0;
  }
  .choice-name {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    font-size: var(--text-sm);
    color: var(--text-1);
    min-width: 0;
    overflow-wrap: anywhere;
  }
  .choice-where,
  .unset {
    font-size: var(--text-2xs);
    color: var(--text-3);
  }
  .displaced {
    font-size: var(--text-2xs);
    color: var(--warn);
    font-weight: 650;
  }
  /* VIS2-16 — ready is the resting state and stays plain metadata; the one that
     needs a person keeps the tone. */
  .state {
    flex: none;
    font-size: var(--text-2xs);
    font-weight: 650;
    color: var(--text-2);
    white-space: nowrap;
  }
  .state[data-state="blocked"] {
    color: var(--warn);
  }
  .captured {
    margin: var(--space-3) 0 0;
    font-size: var(--text-xs);
    color: var(--text-3);
  }
  .alt-rows li {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.35rem 0.55rem;
    font-size: var(--text-sm);
    color: var(--text-1);
  }
  .alt-where {
    color: var(--text-3);
    font-size: var(--text-xs);
  }
  .none-spare {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    margin: 0;
    color: var(--text-3);
    font-size: var(--text-sm);
  }
  @media (max-width: 47.9rem) {
    .work-rows li {
      grid-template-columns: minmax(0, 1fr) auto;
    }
    .surface {
      grid-column: 1 / -1;
    }
  }
</style>
