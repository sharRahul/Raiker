<script lang="ts">
  import { onMount } from "svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import IdentityChip from "../components/IdentityChip.svelte";
  import PageState from "../components/PageState.svelte";
  import GuideLink from "../components/GuideLink.svelte";
  import ProviderLogo from "../components/ProviderLogo.svelte";
  import SubscriptionLimitStrip from "../components/SubscriptionLimitStrip.svelte";
  import { api, ApiError } from "../api";
  import type { AuditExportView, EventEntry, ProviderWeeklyUsage } from "../apiTypes";
  import { humanize, providerName, relativeTime, shortId } from "../format";

  let { sessionId = null }: { sessionId?: string | null } = $props();
  let events = $state<EventEntry[] | null>(null);
  let loadError = $state<string | null>(null);

  // BUG-254 — a connected subscription states how much of its own window is
  // left as part of a turn. Shown here because this is where an owner comes to
  // ask "what is going on right now", and hitting a limit mid-turn is exactly
  // the thing that page should have warned about. Only providers that actually
  // volunteered a reading appear; the rest are silent by design.
  let subscriptions = $state<ProviderWeeklyUsage[]>([]);

  async function loadSubscriptions() {
    try {
      const usage = await api.weeklyModelUsage(false);
      subscriptions = usage.providers.filter((row) => Boolean(row.subscription));
    } catch {
      // A usage read that fails costs this section and nothing else.
      subscriptions = [];
    }
  }

  let sessionFilter = $state("");
  let typeFilter = $state("");
  let limit = $state("100");
  let loadedSessionId = $state<string | null | undefined>(undefined);

  async function load() {
    loadError = null;
    try {
      events = await api.events({
        session_id: sessionFilter.trim() || undefined,
        event_type: typeFilter.trim() || undefined,
        limit: Number(limit) || 100,
      });
    } catch (e) {
      events = null;
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }

  // ── BUG-231 — the record, taken out of the product ─────────────────────
  // An audit trail that cannot leave is not usable as evidence in a review, an
  // incident write-up, or a second tool. Asking for an export is itself a
  // governed action and appears in the log it exported; what comes out carries
  // the same redaction this page does and covers this account only.
  let exports = $state<AuditExportView[] | null>(null);
  let exportBusy = $state(false);
  let exportError = $state<string | null>(null);
  let exportPanelOpen = $state(false);

  async function loadExports() {
    try {
      exports = await api.auditExports();
    } catch {
      exports = [];
    }
  }

  async function createExport() {
    if (exportBusy) return;
    exportBusy = true;
    exportError = null;
    try {
      const result = await api.createAuditExport(sessionFilter.trim() || undefined);
      await loadExports();
      await api.downloadAuditExport(result.export_id);
    } catch (e) {
      exportError =
        e instanceof ApiError
          ? e.status === 409
            ? "Nothing in scope to export — adjust the session filter, or run a turn first."
            : `Could not export the audit log (${e.status}).`
          : "Could not export the audit log.";
    } finally {
      exportBusy = false;
    }
  }

  function toggleExportPanel() {
    exportPanelOpen = !exportPanelOpen;
    if (exportPanelOpen && exports === null) void loadExports();
  }

  function riskTone(risk: string | null): string {
    if (risk === "critical" || risk === "high") return "risk-high";
    if (risk === "medium") return "risk-med";
    return "risk-low";
  }

  $effect(() => {
    if (sessionId === loadedSessionId) return;
    loadedSessionId = sessionId;
    sessionFilter = sessionId ?? "";
    void load();
  });

  onMount(() => void loadSubscriptions());
</script>

<div class="head-row">
  <!-- BUG-87 — the scope is stated, because the page used to claim "every
       governed step" while showing only conversation events, so connecting a
       credential or pinning a model appeared nowhere. It is stated in one line
       now: what it *includes* is read once and belongs in the guide, and four
       sentences above the filters filled a phone screen before the first row. -->
  <p class="page-lead">
    Every governed step in this account, append-only. <GuideLink route="activity" />
  </p>
  <div class="head-actions">
    <button
      type="button"
      class="btn btn-ghost btn-sm"
      onclick={toggleExportPanel}
      aria-expanded={exportPanelOpen}
      aria-controls="audit-export-panel"
    >
      <Icon name="download" size="sm" />
      Export
    </button>
    <button type="button" class="btn btn-ghost btn-sm" onclick={load} aria-label="Refresh events">
      <Icon name="refresh" size="sm" />
      Refresh
    </button>
  </div>
</div>

{#if subscriptions.length > 0}
  <section class="subscriptions" aria-label="Subscription limits">
    {#each subscriptions as row (row.profile_id)}
      {#if row.subscription}
        <article class="subscription">
          <span class="mark"><ProviderLogo provider={row.provider} size={18} /></span>
          <SubscriptionLimitStrip limits={row.subscription} label={providerName(row.provider)} />
        </article>
      {/if}
    {/each}
  </section>
{/if}

{#if exportPanelOpen}
  <div class="card export-card" id="audit-export-panel">
    <h2>Export this record</h2>
    <p class="quiet">
      Your account only, redacted exactly as this page is. Each file carries a manifest hash over
      the event ids it covers, so a reader outside Raiker can verify it — and the export is itself
      written to this log.
      {#if sessionFilter.trim()}
        Scoped to session <span class="mono">{shortId(sessionFilter.trim())}</span>.
      {/if}
    </p>
    {#if exportError}
      <p class="notice notice-danger" role="alert">{exportError}</p>
    {/if}
    <button type="button" class="btn btn-primary btn-sm" onclick={createExport} disabled={exportBusy}>
      {exportBusy ? "Exporting…" : "Export and download"}
    </button>
    {#if exports && exports.length > 0}
      <ul class="export-list">
        {#each exports as ex (ex.export_id)}
          <li>
            <span class="mono">{shortId(ex.export_id)}</span>
            <span class="quiet">{ex.event_count} events · {relativeTime(ex.created_at)}</span>
            <span class="mono hash" title={ex.manifest_hash}>{ex.manifest_hash.slice(0, 12)}</span>
            <button
              type="button"
              class="btn btn-ghost btn-sm"
              onclick={() => api.downloadAuditExport(ex.export_id)}
            >
              Download
            </button>
          </li>
        {/each}
      </ul>
    {/if}
  </div>
{/if}

<form
  class="filters"
  onsubmit={(e) => {
    e.preventDefault();
    void load();
  }}
>
  <div>
    <label class="field-label" for="ev-session">Session id</label>
    <input id="ev-session" class="input mono" type="text" placeholder="sess_…" bind:value={sessionFilter} />
  </div>
  <div>
    <label class="field-label" for="ev-type">Event type</label>
    <input id="ev-type" class="input" type="text" placeholder="Filter by type…" bind:value={typeFilter} />
  </div>
  <div>
    <label class="field-label" for="ev-limit">Limit</label>
    <select id="ev-limit" class="select" bind:value={limit}>
      <option value="50">50</option>
      <option value="100">100</option>
      <option value="250">250</option>
      <option value="500">500</option>
    </select>
  </div>
  <button type="submit" class="btn btn-sm apply">Apply</button>
</form>

{#if loadError}
  <PageState state="error" title="Couldn't load events" detail={loadError} />
{:else if events === null}
  <PageState state="loading" title="Loading events…" />
{:else if events.length === 0}
  <div class="card">
    <EmptyState icon="activity" title="No events match" body="Nothing in the governed record matches these filters." />
  </div>
{:else}
  <div class="card list-card">
    <table class="table">
      <thead>
        <tr>
          <th>Type</th>
          <th>Actor</th>
          <th>Turn identity</th>
          <th>Risk</th>
          <th>Summary</th>
          <th>Session / turn</th>
          <th>When</th>
        </tr>
      </thead>
      <tbody>
        {#each events as ev (ev.event_id)}
          <tr>
            <td title={ev.event_type}>{humanize(ev.event_type)}</td>
            <td class="actor">
              <span class="mono">{ev.actor}</span>
            </td>
            <td class="actor">
              {#if ev.machine_identity}
                <IdentityChip identity={ev.machine_identity} />
              {:else}
                <span aria-label="No turn identity">—</span>
              {/if}
            </td>
            <td>
              <span class={`risk ${riskTone(ev.risk_level)}`}>{ev.risk_level ?? "—"}</span>
            </td>
            <td class="summary-cell">{ev.summary ?? "—"}</td>
            <td class="mono ids">
              {shortId(ev.session_id)}{ev.turn_id ? ` · ${shortId(ev.turn_id)}` : ""}
            </td>
            <td title={ev.timestamp}>{relativeTime(ev.timestamp)}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<style>
  .subscriptions {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
    gap: var(--space-3);
    margin-bottom: var(--space-3);
  }
  .subscription {
    display: flex;
    align-items: flex-start;
    gap: var(--space-2);
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--surface);
  }
  .subscription .mark { flex: none; display: inline-flex; }

  .head-actions {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
  .export-card {
    display: grid;
    gap: var(--space-3);
    justify-items: start;
    margin-bottom: var(--space-4);
  }
  .export-card h2 {
    margin: 0;
    font-size: var(--text-md);
  }
  .export-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 0.3rem;
    width: 100%;
  }
  .export-list li {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    flex-wrap: wrap;
    font-size: var(--text-sm);
  }
  .export-list .hash {
    color: var(--text-3);
  }
  .quiet {
    color: var(--text-3);
    font-size: var(--text-sm);
    margin: 0;
  }
  .head-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-4);
  }
  @media (max-width: 720px) {
    .head-row {
      flex-direction: column;
    }
  }
  .filters {
    display: flex;
    align-items: flex-end;
    gap: var(--space-3);
    flex-wrap: wrap;
    margin-bottom: var(--space-4);
  }
  .apply {
    margin-bottom: 2px;
  }
  .list-card {
    padding: var(--space-2) var(--space-3);
    overflow-x: auto;
  }
  .summary-cell {
    max-width: 26rem;
  }
  .actor,
  .ids {
    font-size: var(--text-sm);
    color: var(--text-2);
    white-space: nowrap;
  }
  .risk {
    font-size: var(--text-xs);
    font-weight: 600;
    border-radius: var(--r-pill);
    padding: 0.05rem 0.5rem;
    border: 1px solid var(--neutral-border);
    background: var(--neutral-soft);
    color: var(--text-2);
  }
  .risk-high {
    border-color: var(--danger-border);
    background: var(--danger-soft);
    color: var(--danger);
  }
  .risk-med {
    border-color: var(--warn-border);
    background: var(--warn-soft);
    color: var(--warn);
  }
</style>
