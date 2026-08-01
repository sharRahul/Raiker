<script lang="ts">
  /**
   * Models → Pricing (BUG-21).
   *
   * The registry made visible. Every claim the product makes about what a turn
   * cost traces back to one row here, so this panel states all of it rather than
   * summarising: which exact model the rate belongs to, which source supplied
   * it, when it took effect, each rate component separately, when the provider
   * was last synchronised and when it is next due, whether that reading is
   * stale, and every earlier rate the model has had.
   *
   * Overrides are administrator work. A non-gate-manager sees the registry
   * read-only — the form is not offered at all, rather than offered and refused
   * on submit.
   */
  import { api, ApiError } from "../api";
  import type { ModelPricingEntry, ModelPricingView } from "../apiTypes";
  import Icon from "./Icon.svelte";
  import { relativeTime } from "../format";

  let view = $state<ModelPricingView | null>(null);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let refreshing = $state(false);
  let notice = $state<string | null>(null);

  let expanded = $state<string | null>(null);
  let editing = $state<string | null>(null);
  let form = $state({
    input: "",
    output: "",
    cacheWrite: "",
    cacheRead: "",
    currency: "USD",
    effectiveFrom: "",
    reason: "",
  });
  let formError = $state<string | null>(null);
  let saving = $state(false);

  function key(entry: ModelPricingEntry): string {
    return `${entry.provider}::${entry.model}`;
  }

  async function load() {
    loading = true;
    loadError = null;
    try {
      // Normalised on arrival. Pricing is one panel on a page that also carries
      // model selection, the fallback sequence, and gate posture — a malformed
      // or truncated pricing response must degrade to "could not read the
      // registry" rather than taking the whole Models page down with it.
      const raw = await api.modelPricing();
      view = {
        entries: (Array.isArray(raw?.entries) ? raw.entries : []).map((entry) => ({
          ...entry,
          history: Array.isArray(entry?.history) ? entry.history : [],
        })),
        sync: Array.isArray(raw?.sync) ? raw.sync : [],
        can_override: raw?.can_override === true,
      };
    } catch {
      loadError = "Could not read the price registry.";
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    void load();
  });

  async function refresh() {
    refreshing = true;
    notice = null;
    try {
      const result = await api.refreshModelPricing();
      notice =
        result.changes_written === 0
          ? "Refreshed — no rate has changed."
          : `Refreshed — ${result.changes_written} rate${result.changes_written === 1 ? "" : "s"} updated.`;
      await load();
    } catch {
      notice = "The refresh did not complete. The last known good rates are still in effect.";
    } finally {
      refreshing = false;
    }
  }

  function startEdit(entry: ModelPricingEntry) {
    editing = key(entry);
    formError = null;
    form = {
      input: entry.input_per_mtok ?? "",
      output: entry.output_per_mtok ?? "",
      cacheWrite: entry.cache_write_per_mtok ?? "",
      cacheRead: entry.cache_read_per_mtok ?? "",
      currency: entry.currency ?? "USD",
      effectiveFrom: "",
      reason: "",
    };
  }

  async function saveOverride(entry: ModelPricingEntry) {
    if (entry.profile_id === null) {
      formError = "This model has no profile to attach an override to.";
      return;
    }
    if (form.input.trim() === "" || form.output.trim() === "") {
      formError = "Input and output rates are both required.";
      return;
    }
    if (form.reason.trim() === "") {
      formError = "A reason is required — an override is recorded against you.";
      return;
    }
    saving = true;
    formError = null;
    try {
      await api.setModelPrice(entry.profile_id, {
        model: entry.model,
        input_per_mtok: form.input.trim(),
        output_per_mtok: form.output.trim(),
        cache_write_per_mtok: form.cacheWrite.trim() || null,
        cache_read_per_mtok: form.cacheRead.trim() || null,
        currency: form.currency.trim() || "USD",
        effective_from: form.effectiveFrom.trim() || null,
        reason: form.reason.trim(),
      });
      editing = null;
      notice = `Override recorded for ${entry.model}.`;
      await load();
    } catch (error) {
      if (error instanceof ApiError && error.reasonCode === "model_price_invalid") {
        formError = "A rate was not a valid non-negative number.";
      } else if (error instanceof ApiError && error.reasonCode === "not_authorized_gate_manager") {
        formError = "Setting a price needs the runtime gate-manager role.";
      } else {
        formError = "The override was not accepted.";
      }
    } finally {
      saving = false;
    }
  }

  async function clearOverride(entry: ModelPricingEntry) {
    if (entry.profile_id === null) return;
    saving = true;
    try {
      await api.setModelPrice(entry.profile_id, { model: entry.model });
      notice = `Override cleared for ${entry.model}. It is back on its published rate.`;
      editing = null;
      await load();
    } catch {
      formError = "The override could not be cleared.";
    } finally {
      saving = false;
    }
  }

  const SOURCE_LABELS: Record<string, string> = {
    owner: "Administrator override",
    provider: "Published by the provider",
    config: "Reviewed documentation",
  };

  function rate(value: string | null, currency: string | null): string {
    return value === null ? "—" : `${currency ?? "USD"} ${value}`;
  }
</script>

<section class="card pricing" aria-labelledby="pricing-h">
  <div class="pricing-head">
    <div>
      <h2 id="pricing-h">Pricing</h2>
      <p class="sub">
        Every cost figure in Raiker comes from one of these rows. Rates are effective-dated and
        append-only: correcting a price records a new rate rather than rewriting the old one, so
        what a turn cost on the day it ran stays reproducible. A model with no exact rate reports
        <strong>Unknown</strong> rather than zero.
      </p>
    </div>
    <button
      type="button"
      class="btn btn-ghost btn-sm"
      onclick={() => void refresh()}
      disabled={refreshing}
    >
      <Icon name="refresh" size={14} />
      {refreshing ? "Refreshing…" : "Refresh now"}
    </button>
  </div>

  {#if notice}<p class="ok-note" role="status">{notice}</p>{/if}

  {#if loading}
    <p class="sub" role="status">Reading the price registry…</p>
  {:else if loadError !== null}
    <p class="error" role="alert">{loadError}</p>
  {:else if view !== null}
    {#if view.sync.length > 0}
      <ul class="sync" aria-label="Provider synchronisation">
        {#each view.sync as state (state.provider)}
          <li class:stale={state.stale}>
            <span class="sync-provider">{state.provider}</span>
            {#if state.stale}
              <span class="badge badge-warn">Stale</span>
            {:else}
              <span class="badge badge-ok">Current</span>
            {/if}
            <span class="sync-fact">
              {state.last_success_at
                ? `Last refresh ${relativeTime(state.last_success_at)}`
                : "Never refreshed"}
            </span>
            <span class="sync-fact">
              {state.next_refresh_at
                ? `Next due ${relativeTime(state.next_refresh_at)}`
                : "Due now"}
              · every {state.interval_hours}h
            </span>
            {#if state.last_error}
              <span class="sync-error">
                Last attempt failed ({state.last_error}) — the previous rates are still in effect.
              </span>
            {/if}
          </li>
        {/each}
      </ul>
    {/if}

    {#if view.entries.length === 0}
      <p class="sub">No model has a recorded rate yet. Refresh, or connect a provider that publishes one.</p>
    {:else}
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Model</th>
              <th scope="col">Source</th>
              <th scope="col">Input</th>
              <th scope="col">Output</th>
              <th scope="col">Cache write</th>
              <th scope="col">Cache read</th>
              <th scope="col">Effective</th>
              <th scope="col"><span class="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody>
            {#each view.entries as entry (key(entry))}
              <tr>
                <th scope="row">
                  <code>{entry.model}</code>
                  <span class="provider">{entry.provider}</span>
                </th>
                <td>
                  <span class="source" class:owner={entry.source === "owner"}>
                    {SOURCE_LABELS[entry.source ?? ""] ?? "Unknown"}
                  </span>
                  {#if entry.reviewed_at}
                    <span class="review-fact">Reviewed {entry.reviewed_at}</span>
                    <span class="review-fact">Review due {entry.review_due_at}</span>
                    <span class="review-state" class:overdue={entry.review_status === "overdue"}>
                      Review {entry.review_status}
                    </span>
                  {/if}
                </td>
                <td class="num">{rate(entry.input_per_mtok, entry.currency)}</td>
                <td class="num">{rate(entry.output_per_mtok, entry.currency)}</td>
                <td class="num">{rate(entry.cache_write_per_mtok, entry.currency)}</td>
                <td class="num">{rate(entry.cache_read_per_mtok, entry.currency)}</td>
                <td>{entry.effective_from?.slice(0, 10) ?? entry.as_of ?? "—"}</td>
                <td class="actions">
                  <button
                    type="button"
                    class="btn btn-ghost btn-sm"
                    aria-expanded={expanded === key(entry)}
                    onclick={() => (expanded = expanded === key(entry) ? null : key(entry))}
                  >History ({entry.history.length})</button>
                  {#if view.can_override}
                    <button type="button" class="btn btn-ghost btn-sm" onclick={() => startEdit(entry)}>
                      {entry.has_owner_override ? "Edit override" : "Override"}
                    </button>
                  {/if}
                </td>
              </tr>
              {#if expanded === key(entry)}
                <tr class="expansion">
                  <td colspan="8">
                    <h3>Price history — {entry.model}</h3>
                    <ol class="history">
                      {#each entry.history as row (row.source + row.effective_from + row.recorded_at)}
                        <li>
                          <span class="history-date">{row.effective_from.slice(0, 10)}</span>
                          <span class="history-source">{SOURCE_LABELS[row.source] ?? row.source}</span>
                          <span class="history-rates">
                            in {row.currency} {row.input_per_mtok} · out {row.currency} {row.output_per_mtok}
                            {#if row.cache_write_per_mtok} · cache write {row.cache_write_per_mtok}{/if}
                            {#if row.cache_read_per_mtok} · cache read {row.cache_read_per_mtok}{/if}
                          </span>
                          {#if row.reason}<span class="history-reason">{row.reason}</span>{/if}
                          {#if row.recorded_by}<span class="history-by">set by {row.recorded_by}</span>{/if}
                        </li>
                      {/each}
                    </ol>
                  </td>
                </tr>
              {/if}
              {#if editing === key(entry)}
                <tr class="expansion">
                  <td colspan="8">
                    <h3>Administrator override — {entry.model}</h3>
                    <p class="sub">
                      An override outranks both the published and documented rate and re-prices
                      history immediately, because cost is derived at read time. It is recorded
                      against you, with your reason, in the registry and the event log.
                    </p>
                    <div class="fields">
                      <label>Input / Mtok<input bind:value={form.input} inputmode="decimal" /></label>
                      <label>Output / Mtok<input bind:value={form.output} inputmode="decimal" /></label>
                      <label>Cache write / Mtok<input bind:value={form.cacheWrite} inputmode="decimal" placeholder="optional" /></label>
                      <label>Cache read / Mtok<input bind:value={form.cacheRead} inputmode="decimal" placeholder="optional" /></label>
                      <label>Currency<input bind:value={form.currency} /></label>
                      <label>Effective from<input bind:value={form.effectiveFrom} placeholder="YYYY-MM-DD (optional)" /></label>
                      <label class="wide">Reason<input bind:value={form.reason} placeholder="Why this rate applies" /></label>
                    </div>
                    {#if formError}<p class="error" role="alert">{formError}</p>{/if}
                    <div class="form-actions">
                      <button
                        type="button"
                        class="btn btn-primary btn-sm"
                        disabled={saving}
                        onclick={() => void saveOverride(entry)}
                      >{saving ? "Saving…" : "Record override"}</button>
                      {#if entry.has_owner_override}
                        <button
                          type="button"
                          class="btn btn-ghost btn-sm"
                          disabled={saving}
                          onclick={() => void clearOverride(entry)}
                        >Clear override</button>
                      {/if}
                      <button type="button" class="btn btn-ghost btn-sm" onclick={() => (editing = null)}>Cancel</button>
                    </div>
                  </td>
                </tr>
              {/if}
            {/each}
          </tbody>
        </table>
      </div>
    {/if}

    {#if !view.can_override}
      <p class="sub">
        Prices are shown read-only. Recording an override needs the runtime gate-manager role.
      </p>
    {/if}
  {/if}
</section>

<style>
  .pricing { display: grid; gap: var(--space-3); }
  .pricing-head { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); flex-wrap: wrap; }
  .pricing-head h2 { margin: 0 0 .25rem; }
  .sub { color: var(--text-2); font-size: .84rem; margin: 0; max-width: 68ch; line-height: 1.5; }
  .ok-note { color: var(--ok); font-size: .82rem; margin: 0; font-weight: 600; }
  .error { color: var(--danger); font-size: .82rem; margin: 0; }

  .sync { list-style: none; margin: 0; padding: 0; display: grid; gap: .4rem; }
  .sync li {
    display: flex; align-items: center; gap: .6rem; flex-wrap: wrap;
    padding: .45rem .7rem; border: 1px solid var(--border);
    border-radius: var(--r-md); background: var(--sunken); font-size: .78rem;
  }
  .sync li.stale { border-color: var(--warn-border); background: var(--warn-soft); }
  .sync-provider { font-weight: 700; }
  .sync-fact { color: var(--text-3); }
  .sync-error { color: var(--warn); width: 100%; }
  .badge { border-radius: 999px; padding: .05rem .45rem; font-size: .68rem; font-weight: 700; }
  .badge-ok { background: var(--ok-soft); color: var(--ok); }
  .badge-warn { background: var(--warn-soft); color: var(--warn); }

  /* A wide table is allowed to scroll inside itself rather than widening the
     page — the rate components matter more than fitting on one screen. */
  .table-wrap { overflow-x: auto; }
  table { border-collapse: collapse; width: 100%; font-size: .8rem; }
  th, td { border-bottom: 1px solid var(--border); padding: .45rem .6rem; text-align: left; vertical-align: top; }
  thead th { color: var(--text-3); font-size: .72rem; text-transform: uppercase; letter-spacing: .04em; }
  tbody th { font-weight: 600; }
  tbody th code { display: block; overflow-wrap: anywhere; }
  .provider { color: var(--text-3); font-size: .72rem; }
  .num { font-variant-numeric: tabular-nums; white-space: nowrap; }
  .source { color: var(--text-2); }
  .source.owner { color: var(--accent); font-weight: 650; }
  .review-fact, .review-state { display:block; margin-top:.18rem; color:var(--text-3); font-size:.7rem; white-space:nowrap; }
  .review-state { color:var(--ok); font-weight:650; }
  .review-state.overdue { color:var(--warn); }
  .actions { display: flex; gap: .25rem; flex-wrap: wrap; }

  .expansion td { background: var(--sunken); }
  .expansion h3 { margin: 0 0 .35rem; font-size: .84rem; }
  .history { list-style: none; margin: .4rem 0 0; padding: 0; display: grid; gap: .35rem; }
  .history li { display: flex; gap: .6rem; flex-wrap: wrap; font-size: .76rem; }
  .history-date { font-variant-numeric: tabular-nums; font-weight: 650; }
  .history-source { color: var(--accent); }
  .history-rates { color: var(--text-2); }
  .history-reason, .history-by { color: var(--text-3); }

  .fields { display: grid; grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr)); gap: .6rem; margin: .6rem 0; }
  .fields label { display: grid; gap: .15rem; font-size: .76rem; color: var(--text-2); }
  .fields .wide { grid-column: 1 / -1; }
  .fields input {
    font: inherit; font-size: .82rem; padding: .3rem .45rem;
    border: 1px solid var(--border-strong); border-radius: var(--r-sm);
    background: var(--surface); color: var(--text-1);
  }
  .form-actions { display: flex; gap: var(--space-2); flex-wrap: wrap; }
</style>
