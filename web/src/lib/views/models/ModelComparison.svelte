<script lang="ts">
  /**
   * UX-MODEL-04 — the models an owner has, side by side.
   *
   * Every column comes from `comparisonRows`, which is where the one rule lives:
   * an unknown fact reads Unknown, never a guessed default. The table is the
   * decision aid; choosing still happens through the inventory's Use action, so
   * there is one way to set a model and this is not a second one.
   */
  import ProviderLogo from "../../components/ProviderLogo.svelte";
  import EmptyState from "../../components/EmptyState.svelte";
  import { providerName } from "../../format";
  import { modelName } from "../../modelPresentation";
  import { comparisonRows, UNKNOWN } from "../../modelComparison";
  import type { ModelProfile } from "../../apiTypes";

  let { profiles }: { profiles: ModelProfile[] } = $props();

  const rows = $derived(comparisonRows(profiles));
</script>

{#if rows.length === 0}
  <EmptyState
    icon="models"
    title="Nothing to compare yet"
    body="Add a model and it appears here beside the others."
  />
{:else}
  <!-- Focusable so a keyboard can scroll the table at narrow widths; a
       scrollable region nobody can reach is an axe failure. -->
  <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
  <div class="scroll" role="region" aria-label="Model comparison" tabindex="0">
    <table class="compare">
      <caption class="sr-only">
        Your models compared by where they run, context, tools, vision, estimated
        cost and availability
      </caption>
      <thead>
        <tr>
          <th scope="col">Model</th>
          <th scope="col">Runs</th>
          <th scope="col">Context</th>
          <th scope="col">Tools</th>
          <th scope="col">Vision</th>
          <th scope="col">Estimated cost</th>
          <th scope="col">Availability</th>
        </tr>
      </thead>
      <tbody>
        {#each rows as row (row.key)}
          <tr>
            <th scope="row">
              <span class="model">
                <ProviderLogo provider={row.profile.provider} />
                <span class="model-text">
                  <span class="model-name">{modelName(row.profile.model)}</span>
                  <span class="provider">{providerName(row.profile.provider)}</span>
                </span>
              </span>
            </th>
            <td>
              {row.locality}
              {#if row.leavesDevice === true}
                <span class="note">Prompts leave this device</span>
              {:else if row.leavesDevice === false}
                <span class="note">Stays on this device</span>
              {/if}
            </td>
            <td class:unknown={row.context === UNKNOWN}>{row.context}</td>
            <td class:unknown={row.tools === UNKNOWN}>{row.tools}</td>
            <td class:unknown={row.vision === UNKNOWN}>{row.vision}</td>
            <td class:unknown={row.cost === UNKNOWN}>{row.cost}</td>
            <td><span class="availability" data-ready={row.ready}>{row.availability}</span></td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  <p class="foot">
    Unknown means no source states it — Raiker does not guess a price, a window
    or a capability. Rates are list prices per million tokens; your bill is on
    Usage.
  </p>
{/if}

<style>
  /* The table scrolls inside its own region so a narrow window never scrolls
     the whole page sideways. */
  .scroll {
    overflow-x: auto;
    border: 1px solid var(--border);
    border-radius: var(--r-md);
  }
  .compare {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--text-sm);
    min-width: 44rem;
  }
  th,
  td {
    text-align: left;
    padding: 0.5rem 0.65rem;
    vertical-align: top;
    border-bottom: 1px solid var(--border);
  }
  thead th {
    font-size: var(--text-2xs);
    font-weight: 650;
    color: var(--text-3);
    text-transform: uppercase;
    letter-spacing: 0.03em;
    background: var(--sunken);
  }
  tbody tr:last-child th,
  tbody tr:last-child td {
    border-bottom: 0;
  }
  tbody th {
    font-weight: 400;
  }
  .model {
    display: flex;
    align-items: center;
    gap: 0.45rem;
  }
  .model-text {
    display: grid;
  }
  .model-name {
    color: var(--text-1);
    font-weight: 600;
    overflow-wrap: anywhere;
  }
  .provider,
  .note {
    display: block;
    font-size: var(--text-2xs);
    color: var(--text-3);
  }
  td {
    color: var(--text-2);
  }
  td.unknown {
    color: var(--text-3);
    font-style: italic;
  }
  .availability[data-ready="false"] {
    color: var(--warn);
  }
  .foot {
    margin: var(--space-2) 0 0;
    font-size: var(--text-xs);
    color: var(--text-3);
  }
</style>
