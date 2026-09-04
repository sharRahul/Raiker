<script lang="ts">
  import { onMount } from "svelte";
  import Badge from "../components/Badge.svelte";
  import Icon from "../components/Icon.svelte";
  import PageState from "../components/PageState.svelte";
  import { api, ApiError } from "../api";
  import type {
    CheckpointCaptureHealth,
    Diagnostics,
    MemoryIntegrity,
    SecurityHealth,
  } from "../apiTypes";
  import { humanize, relativeTime } from "../format";

  let diag = $state<Diagnostics | null>(null);
  let loadError = $state<string | null>(null);
  // Redacted self-monitoring transitions (Task 5). A failed read degrades to
  // its own in-card message; it never hides the rest of the diagnostics.
  let health = $state<SecurityHealth[] | null>(null);
  let healthError = $state<string | null>(null);
  // MEM-09 — the memory integrity report. It has existed since the memory audit
  // and nothing displayed it, so a divergence between a table and its index was
  // invisible: search simply stopped finding things. Read-only, owner-started.
  let integrity = $state<MemoryIntegrity | null>(null);
  let integrityError = $state<string | null>(null);
  let integrityBusy = $state(false);
  let integrityNotice = $state<string | null>(null);

  // Only the findings worth acting on. A report that lists ten zeroes hides the
  // one number that is not zero.
  const integrityFindings = $derived.by(() => {
    if (integrity === null) return [];
    const labels: Array<[keyof MemoryIntegrity, string]> = [
      ["stale_fts_count", "Memory search index"],
      ["stale_conversation_index_count", "Conversation search index"],
      ["stale_projection_count", "Memory projections"],
      ["stale_graph_edge_count", "Knowledge graph edges"],
      ["missing_markdown_count", "Missing memory files"],
      ["orphaned_markdown_count", "Orphaned memory files"],
      ["checksum_mismatch_count", "Checksum mismatches"],
      ["failed_purge_location_count", "Unfinished purges"],
      ["project_path_inconsistency_count", "Project paths"],
      ["index_engine_mismatch_count", "Index engine"],
    ];
    return labels
      .map(([key, label]) => ({ key, label, count: Number(integrity?.[key] ?? 0) }))
      .filter((finding) => finding.count > 0);
  });

  async function loadIntegrity() {
    integrityError = null;
    try {
      integrity = await api.memoryIntegrity();
    } catch (e) {
      integrity = null;
      integrityError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }

  async function rebuildConversationIndex() {
    integrityBusy = true;
    integrityNotice = null;
    try {
      const result = await api.rebuildConversationIndex();
      integrityNotice = `Rebuilt — ${result.indexed_rows} rows indexed.`;
      await loadIntegrity();
    } catch (e) {
      integrityNotice = e instanceof ApiError ? `Could not rebuild (${e.status}).` : "Could not rebuild.";
    } finally {
      integrityBusy = false;
    }
  }

  async function load() {
    loadError = null;
    try {
      diag = await api.diagnostics();
    } catch (e) {
      diag = null;
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
    healthError = null;
    try {
      health = await api.securityHealth();
    } catch (e) {
      health = null;
      healthError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }

    await loadIntegrity();
  }

  function healthBadge(state: string): "blocked" | "implemented" | "idle" {
    if (state === "alerting") return "blocked";
    if (state === "recovered") return "implemented";
    return "idle";
  }

  /**
   * Only the readiness checks that failed.
   *
   * The tick list of passing checks, the runtime counts, the configuration gaps
   * and the capability chips all left this view: Observability -> Overview reads
   * the *same* `diagnostics` object and already states each of them as a tile,
   * with a link to where the owner acts. What Overview cannot fit is a failed
   * check's reason code and remediation, so that is what stays here.
   */
  const failedReadiness = $derived.by(() => {
    if (diag === null) return [];
    return Object.entries(diag.readiness)
      .filter((entry): entry is [string, CheckpointCaptureHealth] =>
        typeof entry[1] === "object" && entry[1] !== null && "reason_code" in entry[1],
      )
      .map(([key, detail]) => ({ key, detail }))
      .filter((check) => !check.detail.ok);
  });

  // Humanize readiness-check keys into readable labels.
  function readinessLabel(key: string): string {
    const map: Record<string, string> = {
      vault_configured: "Vault configured",
      egress_allowlist_configured: "Egress allowlist configured",
      owner_token_configured: "Owner token configured",
      model_profiles_configured: "Model profiles configured",
      production_ready_local_single_user_runtime: "Production-ready (local)",
    };
    return map[key] ?? humanize(key);
  }

  onMount(load);
</script>

<div class="head-row">
  <p class="page-lead">
    Derived from stored state only — nothing here probes the network or fabricates health.
  </p>
  <button type="button" class="btn btn-ghost btn-sm" onclick={load} aria-label="Refresh runtime health">
    <Icon name="refresh" size={15} />
    Refresh
  </button>
</div>

{#if loadError}
  <PageState state="error" title="Couldn't read runtime health" detail={loadError} />
{:else if diag === null}
  <PageState state="loading" title="Reading runtime health…" />
{:else}
  <div class="grid">
    <section class="card" aria-labelledby="diag-monitor-h">
      <h2 id="diag-monitor-h">Self-monitoring</h2>
      <p class="sub">Redacted health transitions recorded by the runtime's own monitors.</p>
      {#if healthError}
        <p class="error" role="alert">{healthError}</p>
      {:else if health === null}
        <p class="sub">Loading…</p>
      {:else if health.length === 0}
        <p class="sub">No health transitions recorded.</p>
      {:else}
        <ul class="monitor">
          {#each health as entry (`${entry.source}:${entry.subject_id}:${entry.code}`)}
            <li>
              <Badge variant={healthBadge(entry.state)} label={entry.state} />
              <span class="monitor-code">{humanize(entry.code)}</span>
              <span class="monitor-when" title={entry.updated_at}>{relativeTime(entry.updated_at)}</span>
            </li>
          {/each}
        </ul>
      {/if}
    </section>

    <section class="card" aria-labelledby="diag-memory-h">
      <h2 id="diag-memory-h">Memory integrity</h2>
      <p class="sub">
        Every index and projection the memory store depends on, compared against the table that owns
        the content.
      </p>
      {#if integrityError}
        <p class="error" role="alert">{integrityError}</p>
      {:else if integrity === null}
        <p class="sub">Loading…</p>
      {:else}
        <p class="big-status">
          <Badge
            variant={integrity.clean ? "implemented" : "approval-required"}
            label={integrity.clean ? "clean" : `${integrityFindings.length} to repair`}
          />
        </p>
        {#if integrityFindings.length > 0}
          <dl class="kv">
            {#each integrityFindings as finding (finding.key)}
              <div><dt>{finding.label}</dt><dd>{finding.count}</dd></div>
            {/each}
          </dl>
        {/if}
        <div class="card-actions">
          <button type="button" class="btn btn-ghost btn-sm" onclick={() => void loadIntegrity()}>
            Rescan
          </button>
          {#if integrity.stale_conversation_index_count > 0}
            <!-- MEM-09 — the stated repair, offered where the drift is reported.
                 The index is a projection of the turns, so a rebuild recomputes
                 every row and can lose nothing. -->
            <button
              type="button"
              class="btn btn-primary btn-sm"
              disabled={integrityBusy}
              onclick={() => void rebuildConversationIndex()}
            >
              Rebuild conversation index
            </button>
          {/if}
        </div>
        {#if integrityNotice}<p class="sub" role="status">{integrityNotice}</p>{/if}
      {/if}
    </section>

    <!--
      Only the readiness checks that FAILED, and only because a failure carries a
      remediation the tiles above cannot fit. The passing ones were a tick list
      restating "Runtime: Ready", which the tile at the top of this page already
      says; a check that is fine needs no words at all.
    -->
    {#each failedReadiness as check (check.key)}
      <section class="card readiness-failed" aria-labelledby={`diag-readiness-${check.key}`}>
        <h2 id={`diag-readiness-${check.key}`}>
          <Icon name="warning" size={15} /> {readinessLabel(check.key)}
        </h2>
        <p>Change capture failed — writes may not be reversible.</p>
        <p class="mono">{humanize(check.detail.reason_code)}</p>
        {#if check.detail.remediation}<p>{check.detail.remediation}</p>{/if}
        <p class="sub">Checked {relativeTime(check.detail.checked_at)}</p>
      </section>
    {/each}
  </div>
{/if}

<style>
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
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(20rem, 1fr));
    gap: var(--space-4);
    align-items: start;
  }
  .big-status {
    margin: 0 0 var(--space-3);
  }
  .readiness-failed {
    border-color: var(--danger-border, var(--border));
    background: var(--danger-soft, transparent);
  }
  .kv {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(8rem, 1fr));
    gap: 0.4rem 1rem;
    margin: 0 0 var(--space-3);
  }
  .kv dt {
    font-size: 0.7rem;
    font-weight: 650;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-3);
  }
  .kv dd {
    margin: 0.05rem 0 0;
    font-size: 0.88rem;
  }
  .sub {
    color: var(--text-3);
    font-size: var(--text-sm);
  }
  .monitor {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
    font-size: 0.85rem;
  }
  .monitor li {
    display: flex;
    align-items: baseline;
    gap: 0.55rem;
  }
  .monitor-code {
    color: var(--text-1);
    flex: 1;
  }
  .monitor-when {
    color: var(--text-3);
    font-size: 0.74rem;
    white-space: nowrap;
  }
  .error {
    color: var(--danger);
  }
  .card-actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }
</style>
