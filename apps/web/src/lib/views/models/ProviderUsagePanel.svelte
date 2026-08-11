<script lang="ts">
  import { onMount } from "svelte";
  import { api } from "../../api";
  import type { ProviderWeeklyUsage, ProviderWeeklyUsageView } from "../../apiTypes";
  import ProviderLogo from "../../components/ProviderLogo.svelte";
  import { providerName } from "../../format";

  let usage = $state<ProviderWeeklyUsageView | null>(null);
  let loading = $state(true);
  let refreshing = $state(false);
  let error = $state<string | null>(null);
  let editingFor = $state<string | null>(null);
  let budgetDraft = $state("");
  let savingBudget = $state(false);

  onMount(() => void load(false));

  async function load(refreshNative: boolean) {
    error = null;
    if (refreshNative) refreshing = true;
    else loading = true;
    try {
      usage = await api.weeklyModelUsage(refreshNative);
    } catch {
      error = "Raiker could not load provider usage. Check the runtime, then try again.";
    } finally {
      loading = false;
      refreshing = false;
    }
  }

  function editBudget(row: ProviderWeeklyUsage) {
    editingFor = row.profile_id;
    budgetDraft = row.owner_budget?.toString() ?? "";
  }

  async function saveBudget(row: ProviderWeeklyUsage) {
    const trimmed = budgetDraft.trim();
    const next = trimmed === "" ? null : Number(trimmed);
    if (next !== null && (!Number.isInteger(next) || next <= 0)) {
      error = "Weekly token budget must be a positive whole number.";
      return;
    }
    savingBudget = true;
    error = null;
    try {
      await api.setWeeklyModelBudget(row.profile_id, next);
      editingFor = null;
      await load(false);
    } catch {
      error = "Raiker could not save this weekly budget.";
    } finally {
      savingBudget = false;
    }
  }

  function number(value: number): string {
    return new Intl.NumberFormat().format(value);
  }

  function budgetPercent(row: ProviderWeeklyUsage): number {
    if (!row.owner_budget) return 0;
    return Math.min(100, (row.observed.total_tokens / row.owner_budget) * 100);
  }

  function metricValue(value: string, unit: string): string {
    const parsed = Number(value);
    if (unit === "USD" && Number.isFinite(parsed)) {
      return new Intl.NumberFormat(undefined, {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 4,
      }).format(parsed);
    }
    return `${Number.isFinite(parsed) ? new Intl.NumberFormat().format(parsed) : value} ${unit}`;
  }
</script>

<section class="usage-panel" aria-labelledby="provider-usage-title">
  <div class="usage-heading">
    <div>
      <p class="eyebrow">Connected providers only</p>
      <h2 id="provider-usage-title">Rolling seven-day usage</h2>
      <p>
        Tokens, turns, and known API cost come from Raiker’s ledger. Provider
        account data appears separately when the connected API can supply it.
      </p>
    </div>
    <button
      type="button"
      class="btn btn-soft"
      onclick={() => void load(true)}
      disabled={refreshing || loading}
    >
      {refreshing ? "Checking providers…" : "Refresh provider data"}
    </button>
  </div>

  {#if error}<p class="usage-error" role="alert">{error}</p>{/if}
  {#if loading}
    <p class="usage-state" role="status">Loading usage…</p>
  {:else if usage && usage.providers.length === 0}
    <div class="usage-empty">
      <strong>No connected providers</strong>
      <span>Connect a hosted account or start and check a local runtime to see it here.</span>
    </div>
  {:else if usage}
    <div class="usage-list">
      {#each usage.providers as row (row.profile_id)}
        <article class="usage-row">
          <header>
            <span class="provider-mark"><ProviderLogo provider={row.provider} size={26} /></span>
            <div>
              <h3>{providerName(row.provider)}</h3>
              <code>{row.profile_id}</code>
            </div>
            <span class="window-chip">7 days</span>
          </header>

          <div class="source-pair">
            <section class="source observed" aria-label={`${providerName(row.provider)} Raiker-observed usage`}>
              <p class="source-label">Raiker observed</p>
              <strong>{number(row.observed.total_tokens)} tokens</strong>
              <p>
                {number(row.observed.turns)} turns · {number(row.observed.requests)} model requests
                {#if row.observed.compactions > 0}
                  · {number(row.observed.compactions)} compaction{row.observed.compactions === 1 ? "" : "s"}
                {/if}
              </p>
              {#if row.observed.known_cost !== null}
                <p class="cost">
                  {metricValue(row.observed.known_cost, row.observed.cost_currency ?? "USD")}
                  known cost
                </p>
              {:else if row.observed.total_tokens > 0}
                <p class="quiet">Cost unknown for the recorded model pricing.</p>
              {/if}
            </section>

            <section class="source native" aria-label={`${providerName(row.provider)} provider-reported usage`}>
              <p class="source-label">Provider reported</p>
              {#if row.native.status === "available" && row.native.metrics.length > 0}
                {#each row.native.metrics as metric (`${metric.unit}-${metric.scope}`)}
                  <p class="native-metric">
                    <strong>{metricValue(metric.used, metric.unit)}</strong>
                    {#if metric.limit !== null}
                      <span>of {metricValue(metric.limit, metric.unit)}</span>
                    {/if}
                    <small>{metric.scope.replaceAll("_", " ")} · {metric.reset_interval?.replaceAll("_", " ") ?? "provider period"}</small>
                  </p>
                {/each}
              {:else if row.native.status === "not_configured"}
                <p class="quiet">A separate organization admin key is needed for genuine usage reports.</p>
              {:else if row.native.status === "not_supported"}
                <p class="quiet">This provider exposes no compatible account-quota API.</p>
              {:else if row.native.status === "unavailable"}
                <p class="quiet">Provider data is temporarily unavailable.</p>
              {:else}
                <p class="quiet">Refresh to ask this provider for genuine account data.</p>
              {/if}
            </section>
          </div>

          <div class="budget-row">
            <div class="budget-copy">
              <span>Owner weekly token budget</span>
              <strong>{row.owner_budget ? number(row.owner_budget) : "Not set"}</strong>
            </div>
            {#if editingFor === row.profile_id}
              <label>
                <span class="sr-only">Weekly token budget for {providerName(row.provider)}</span>
                <input class="input" inputmode="numeric" placeholder="e.g. 500000" bind:value={budgetDraft} />
              </label>
              <button type="button" class="btn btn-primary btn-sm" onclick={() => void saveBudget(row)} disabled={savingBudget}>Save</button>
              <button type="button" class="btn btn-ghost btn-sm" onclick={() => (editingFor = null)}>Cancel</button>
            {:else}
              <div class="budget-track" aria-label={row.owner_budget ? `${budgetPercent(row).toFixed(0)} percent of owner budget observed` : "No owner budget set"}>
                <span style={`width:${budgetPercent(row)}%`}></span>
              </div>
              <button type="button" class="btn btn-ghost btn-sm" onclick={() => editBudget(row)}>
                {row.owner_budget ? "Edit budget" : "Set budget"}
              </button>
            {/if}
          </div>
          <p class="budget-note">Advisory Raiker control — not a provider subscription limit.</p>
        </article>
      {/each}
    </div>
  {/if}
</section>

<style>
  .usage-panel { margin-bottom: var(--space-5); }
  .usage-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); margin-bottom: var(--space-3); }
  .usage-heading h2 { margin: .15rem 0 .35rem; font-size: 1.08rem; }
  .usage-heading p { margin: 0; color: var(--text-2); max-width: 68ch; font-size: .86rem; }
  .eyebrow { color: var(--accent) !important; font-size: .68rem !important; font-weight: 750; letter-spacing: .1em; text-transform: uppercase; }
  .usage-list { display: grid; gap: var(--space-3); }
  .usage-row { border: 1px solid var(--border); border-radius: var(--r-md); background: var(--surface); overflow: hidden; }
  .usage-row > header { display: flex; align-items: center; gap: var(--space-2); padding: var(--space-3); border-bottom: 1px solid var(--border); }
  .usage-row h3 { margin: 0; font-size: .95rem; }
  .usage-row code { color: var(--text-3); font-size: .68rem; }
  .provider-mark { display: grid; place-items: center; width: 36px; height: 36px; border-radius: var(--r-sm); background: var(--surface-2); }
  .window-chip { margin-left: auto; color: var(--text-2); font-size: .7rem; font-weight: 700; border: 1px solid var(--border); border-radius: 999px; padding: .18rem .48rem; }
  .source-pair { display: grid; grid-template-columns: 1fr 1fr; }
  .source { padding: var(--space-3); min-width: 0; }
  .source + .source { border-left: 1px solid var(--border); background: color-mix(in srgb, var(--surface-2) 55%, transparent); }
  .source-label { margin: 0 0 .45rem; color: var(--text-3); font-size: .68rem; font-weight: 750; letter-spacing: .07em; text-transform: uppercase; }
  .source > strong { font-size: 1.15rem; letter-spacing: -.02em; }
  .source > p:not(.source-label) { margin: .25rem 0 0; color: var(--text-2); font-size: .78rem; }
  .cost { color: var(--text-1) !important; font-weight: 650; }
  .quiet { line-height: 1.45; }
  .native-metric { display: grid; grid-template-columns: auto 1fr; align-items: baseline; gap: .2rem .4rem; margin: 0 0 .45rem; }
  .native-metric small { grid-column: 1 / -1; color: var(--text-3); text-transform: capitalize; }
  .budget-row { display: flex; align-items: center; gap: var(--space-2); padding: var(--space-2) var(--space-3) 0; border-top: 1px solid var(--border); }
  .budget-copy { display: flex; flex-direction: column; min-width: 155px; font-size: .72rem; color: var(--text-3); }
  .budget-copy strong { color: var(--text-1); font-size: .82rem; }
  .budget-track { flex: 1; min-width: 80px; height: 5px; border-radius: 999px; background: var(--surface-3); overflow: hidden; }
  .budget-track span { display: block; height: 100%; border-radius: inherit; background: var(--accent); }
  .budget-row label { flex: 1; }
  .budget-row .input { width: 100%; }
  .budget-note { margin: .35rem var(--space-3) var(--space-2); color: var(--text-3); font-size: .67rem; }
  .usage-state, .usage-error, .usage-empty { border: 1px solid var(--border); border-radius: var(--r-md); padding: var(--space-4); color: var(--text-2); }
  .usage-error { color: var(--danger); border-color: var(--danger-border); background: var(--danger-soft); }
  .usage-empty { display: flex; flex-direction: column; gap: .3rem; }
  .usage-empty strong { color: var(--text-1); }
  .usage-empty span { font-size: .82rem; }
  @media (max-width: 720px) {
    .usage-heading { flex-direction: column; }
    .source-pair { grid-template-columns: 1fr; }
    .source + .source { border-left: 0; border-top: 1px solid var(--border); }
    .budget-row { align-items: stretch; flex-wrap: wrap; }
    .budget-copy { width: 100%; }
    .budget-track { align-self: center; }
  }
</style>
