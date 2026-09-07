<script lang="ts">
  /**
   * MODEL-11 — Default, Selected, Effective and Fallback, told apart.
   *
   * The page called all four "active". That single word is why the review could
   * not describe the bug precisely and why an owner could not either: a model
   * that was chosen but unreachable, one that was reachable but not chosen, and
   * one that a fallback had quietly substituted all read the same, so "my model
   * keeps changing" and "my model never saved" were indistinguishable reports
   * about entirely different states.
   *
   *   Default    where this surface's picker starts. Persisted. May be
   *              unavailable, and stays visible when it is.
   *   Selected   the owner's choice for the scope in hand — here, the same
   *              thing as the surface default.
   *   Effective  what a turn started now would really use, after the fallback
   *              sequence is walked.
   *   Fallback   the ordered list the runtime tries when the first choice
   *              cannot serve. Edited below this table, not in it.
   *
   * Every fact comes from `/api/model-decisions` (MODEL-01), so this table and
   * the composer picker cannot disagree; before that contract they were two
   * separate calculations over the same five stores.
   */
  import PageState from "../../components/PageState.svelte";
  import ProviderLogo from "../../components/ProviderLogo.svelte";
  import { modelDecisions } from "../../surfaceModel.svelte";
  import { providerName } from "../../format";
  import { modelName } from "../../modelPresentation";
  import type { ModelDecision, ModelProfile, ModelsView } from "../../apiTypes";

  let { models }: { models: ModelsView | null } = $props();

  let decisions = $state<Record<string, ModelDecision> | null>(null);
  /** False until the first read answers, so "loading" and "unreadable"
   *  stay two different states rather than both being `decisions === null`. */
  let read = $state(false);

  const ROWS = [
    { id: "chat", label: "Chat" },
    { id: "build", label: "Build" },
    { id: "design", label: "Design" },
    { id: "tasks", label: "Tasks" },
    { id: "schedule", label: "Schedule" },
  ] as const;

  function profileFor(profileId: string, model: string): ModelProfile | null {
    if (models === null) return null;
    return (
      models.profiles.find((p) => p.profile_id === profileId && p.model === model) ??
      models.profiles.find((p) => p.profile_id === profileId) ??
      null
    );
  }

  const rows = $derived(
    ROWS.map((surface) => {
      const decision = decisions?.[surface.id] ?? null;
      return {
        ...surface,
        decision,
        profile: decision ? profileFor(decision.selected.profile_id, decision.selected.model) : null,
        // Only when the two differ. A table that prints the same model in two
        // columns on every row has taught the reader that the columns mean the
        // same thing, which is exactly the confusion being fixed.
        effective:
          decision !== null && decision.effective.reason === "fallback"
            ? decision.effective
            : null,
      };
    }),
  );

  $effect(() => {
    void models;
    void (async () => {
      decisions = await modelDecisions();
      read = true;
    })();
  });
</script>

<section class="card work-defaults" aria-labelledby="work-defaults-h">
  <div class="card-head">
    <h2 id="work-defaults-h">Work defaults</h2>
  </div>
  <p class="sub">
    Where each surface's model picker starts. A default is a preference, never a
    permission: the turn still names its exact profile and model, and the
    readiness gate judges that pair on its own evidence.
  </p>

  {#if read && decisions === null}
    <PageState
      state="error"
      title="Couldn't read the work defaults"
      detail="Nothing was changed. The fallback sequence below is still editable."
    />
  {:else if !read}
    <PageState state="loading" title="Reading your defaults…" />
  {:else}
    <table>
      <thead>
        <tr>
          <th scope="col">Surface</th>
          <th scope="col">Default</th>
          <th scope="col">Effective now</th>
        </tr>
      </thead>
      <tbody>
        {#each rows as row (row.id)}
          <tr>
            <th scope="row">{row.label}</th>
            <td>
              {#if row.decision === null || row.decision.selected.model === ""}
                <span class="none">Not set</span>
              {:else}
                <span class="pair">
                  {#if row.profile}<ProviderLogo provider={row.profile.provider} />{/if}
                  <span class="pair-name">{modelName(row.decision.selected.model)}</span>
                </span>
                <span class="pair-where">
                  {row.profile ? providerName(row.profile.provider) : "Unknown provider"}
                  {#if row.decision.selected.source !== "surface_default"}
                    · inherited
                  {/if}
                </span>
              {/if}
            </td>
            <td>
              {#if row.effective !== null}
                <!-- The whole reason this column exists: the runtime is using
                     something other than the choice on its left, and saying so
                     is the difference between a fallback and a lost setting. -->
                <span class="displaced">{modelName(row.effective.model)}</span>
                <span class="pair-where">fallback — the default cannot serve</span>
              {:else if row.decision?.ready}
                <span class="same">Same as default</span>
              {:else if row.decision !== null}
                <span class="displaced">Nothing ready</span>
                {#if row.decision.problem}
                  <span class="pair-where">{row.decision.problem.summary}</span>
                {/if}
              {:else}
                <span class="none">—</span>
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
    <p class="sub captured-note">
      Tasks and Schedule capture the model onto the work they create, so a run
      that fires next week uses the model it was scheduled with rather than
      whatever is selected by then.
    </p>
  {/if}
</section>

<style>
  .card-head h2 {
    margin: 0;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    margin-top: var(--space-3);
  }
  th,
  td {
    text-align: left;
    vertical-align: top;
    padding: 0.45rem 0.5rem;
    border-bottom: 1px solid var(--border);
  }
  thead th {
    color: var(--text-2);
    font-size: var(--text-xs);
    font-weight: 650;
  }
  tbody th {
    font-size: var(--text-sm);
    font-weight: 650;
    color: var(--text-1);
    white-space: nowrap;
  }
  td {
    font-size: var(--text-sm);
    color: var(--text-1);
  }
  .pair {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    min-width: 0;
  }
  .pair-name {
    overflow-wrap: anywhere;
  }
  .pair-where,
  .none,
  .same {
    display: block;
    color: var(--text-3);
    font-size: var(--text-2xs);
  }
  /* The one toned cell, because it is the one that is not the ordinary case. */
  .displaced {
    color: var(--warn);
    font-weight: 650;
  }
  .captured-note {
    margin-top: var(--space-3);
  }
  @media (max-width: 47.9rem) {
    thead {
      display: none;
    }
    tbody tr {
      display: grid;
      gap: 0.15rem;
      padding: 0.4rem 0;
      border-bottom: 1px solid var(--border);
    }
    th,
    td {
      border-bottom: 0;
      padding: 0 0.1rem;
    }
  }
</style>
