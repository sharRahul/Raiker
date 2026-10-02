<script lang="ts">
  import Icon from "../components/Icon.svelte";
  import PageState from "../components/PageState.svelte";
  import { api, ApiError } from "../api";
  import FileInspector from "../components/FileInspector.svelte";
  import type { CapabilityGate, MemoryControlView, MemoryHistoryEvent, MemoryImportBatch, MemoryImportPreview, MemoryProposal, MemoryRelationshipProposal, MemorySettingsView, ObservationsView, SourceExcerptView } from "../apiTypes";
  import { relativeTime } from "../format";
  import { memoryWritePosture } from "../memoryPosture";
  import GuideLink from "../components/GuideLink.svelte";
  import MemoryRecordDrawer from "../components/MemoryRecordDrawer.svelte";
  import FileLibrary from "../components/FileLibrary.svelte";
  import KnowledgeSources from "../components/KnowledgeSources.svelte";
  import TabStrip from "../components/TabStrip.svelte";
  import { HUB_TABS } from "../nav";
  import {
    MEMORY_TAB_LABELS,
    memoryAttention,
    memorySentence,
    type MemoryCounts,
    type MemoryTab,
  } from "../memoryHub";
  import {
    LIFECYCLE_VERBS,
    MEMORY_FILTERS,
    MEMORY_FILTER_LABELS,
    MEMORY_STATE_LABELS,
    isMemoryFilter,
    isRecallable,
    matchesFilter,
    memoryPipeline,
    memoryState,
    retentionRows,
    retentionSummary,
    type MemoryFilter,
  } from "../memoryLifecycle";
  import { memoryEvidence, proposalEvidence } from "../memoryEvidence";

  type MemoryImport = Array<Partial<MemoryControlView> & { text: string }>;
  let memories = $state<MemoryControlView[] | null>(null);
  let settings = $state<MemorySettingsView | null>(null);
  let proposals = $state<MemoryProposal[]>([]);
  let relationshipProposals = $state<MemoryRelationshipProposal[]>([]);
  let loadError = $state<string | null>(null);
  let actionError = $state<string | null>(null);
  let busy = $state(false);
  let query = $state("");
  // UX-MEM-03 — the list filter. A deep link's `filter=` wins, so a count on
  // the Overview opens exactly the records it counted.
  let statusFilter = $state<MemoryFilter>("active");
  let scopeFilter = $state("all");
  let sensitivityFilter = $state("all");
  let pinnedOnly = $state(false);
  let sort = $state("recently-approved");
  let editingId = $state<string | null>(null);
  let editDraft = $state("");
  let importPreview = $state<MemoryImport | null>(null);
  // BUG-244 — how many of the reviewed records the workspace already holds.
  let importAlready = $state<MemoryImportPreview | null>(null);
  let importBusy = $state(false);
  let importNotice = $state<string | null>(null);
  let importFileName = $state("");
  // UX-MEM-08 — the records the owner chose to leave out, by index in the file,
  // and the receipts of recent imports, each one an import that can be undone.
  let importExcluded = $state<Set<number>>(new Set());
  let importBatches = $state<MemoryImportBatch[]>([]);
  let proposalEditingId = $state<string | null>(null);
  let proposalDraft = $state("");
  let historyById = $state<Record<string, MemoryHistoryEvent[]>>({});

  // REM-MEM-01 — the record drawer holds an **id**, not a record. Scope,
  // expiry and deletion are all versioned against `updated_at` server-side, so
  // the drawer has to act on the revision the page currently holds rather than
  // on the copy a card was drawn from. Resolving through `memories` each time
  // also answers the "old bookmarked record" case honestly: when the id is no
  // longer listed, the drawer says so and offers nothing.
  let drawerId = $state<string | null>(null);
  const drawerRecord = $derived(
    drawerId === null ? null : ((memories ?? []).find((m) => m.memory_id === drawerId) ?? null),
  );

  // MEM-04 — what the runtime captured while it worked. Loaded beside the
  // memories rather than behind a tab click, because the summary counters at
  // the top of this page are only honest if this half is known: "0 observations
  // captured" and "everything was refused on sensitivity" are different facts.
  let observations = $state<ObservationsView | null>(null);
  let observationFilter = $state("all");

  // BUG-71 — the two facts that decide whether this page may promise proposals
  // at all. Read alongside the memories so the promise and the gate can never
  // disagree; a failed read says so rather than assuming the happy answer.
  // `undefined` is an in-flight read; `null` is a failed read. Keeping those
  // distinct prevents a short normal request from being presented as a broken
  // permission system (BUG-302).
  let gates = $state<CapabilityGate[] | null | undefined>(undefined);
  const posture = $derived(memoryWritePosture(gates));

  // MEM-03 — what recall is actually searching. Defaulted rather than assumed
  // present: a backend that predates the field would otherwise take the page
  // down, and the honest answer when nothing says otherwise is the fallback,
  // which is exactly what the server resolves to in that case anyway.
  const retrieval = $derived(
    settings?.retrieval ?? {
      backend_id: "local_hash",
      kind: "lexical_fallback" as const,
      model: "raiker-local-hash-v1",
      dimensions: 384,
      semantic: false,
      reason_code: "embedding_backend_semantic_not_configured",
      query_embeddable: false,
    },
  );
  // Three states, not two. Stored vectors being semantic does not make recall
  // semantic: until the question is embedded too, matching is by words, and
  // saying "matches meaning" then is the claim MEM-03 removes.
  const recall = $derived(
    !retrieval.semantic
      ? "lexical"
      : retrieval.query_embeddable
        ? "semantic"
        : "stored_only",
  );

  // Every action reloads the page's reads, and a reload can start while the
  // previous one is still waiting on its later reads. Only the newest may
  // write, so an archive is never undone on screen by a read taken before it.
  let loadSeq = 0;
  async function load() {
    const seq = ++loadSeq;
    const current = () => seq === loadSeq;
    loadError = null;
    try {
      const [listed, read] = await Promise.all([api.memories(undefined, true), api.memorySettings()]);
      if (!current()) return;
      [memories, settings] = [listed, read];
      try { const value = await api.memoryProposals(); if (current()) proposals = value; } catch { if (current()) proposals = []; }
      try { const value = await api.memoryRelationshipProposals(); if (current()) relationshipProposals = value; } catch { if (current()) relationshipProposals = []; }
      try { const value = await api.capabilityGates(); if (current()) gates = value; } catch { if (current()) gates = null; }
      // A failed read is null, never an empty list: "capture is not reporting"
      // must not render as "capture found nothing".
      try { const value = await api.observations(); if (current()) observations = value; } catch { if (current()) observations = null; }
      try { const value = (await api.memoryImportBatches()).batches; if (current()) importBatches = value; } catch { if (current()) importBatches = []; }
    }
    catch (e) {
      if (!current()) return;
      memories = null; settings = null; loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }
  async function toggleIncognito() {
    if (!settings || busy) return;
    busy = true; actionError = null;
    try { await api.setMemoryIncognito(!settings.incognito); await load(); }
    catch (e) { actionError = e instanceof ApiError ? `Could not update memory use (${e.status}).` : "Could not update memory use."; }
    finally { busy = false; }
  }
  async function togglePin(m: MemoryControlView) {
    try { await api.setMemoryPinned(m.memory_id, !m.pinned); await load(); }
    catch { actionError = "Could not update this memory."; }
  }
  async function saveEdit(m: MemoryControlView) {
    try { await api.editMemory(m.memory_id, editDraft); editingId = null; await load(); }
    catch { actionError = "Could not edit this memory."; }
  }
  async function forget(m: MemoryControlView) {
    if (!window.confirm(`Forget this memory? ${LIFECYCLE_VERBS.forget.consequence} To stop recalling it and keep it, archive it instead.`)) return;
    try { await api.forgetMemory(m.memory_id); await load(); }
    catch { actionError = "Could not forget this memory."; }
  }
  // UX-MEM-02 — archive and restore are the reversible pair; neither asks to
  // confirm, because neither loses anything.
  async function setArchived(m: MemoryControlView, archived: boolean) {
    try { await api.setMemoryArchived(m.memory_id, archived); await load(); }
    catch { actionError = archived ? "Could not archive this memory." : "Could not restore this memory."; }
  }
  async function decideProposal(proposal: MemoryProposal, decision: "approved" | "rejected", editedText?: string) {
    const reason = decision === "rejected" ? window.prompt("Why should this proposal be rejected?", "Not useful as durable memory") : "";
    if (decision === "rejected" && reason === null) return;
    try {
      await api.decideMemoryProposal(proposal.candidate_id, { decision, edited_text: editedText, reason: reason ?? "", expected_decision: proposal.decision });
      proposalEditingId = null;
      await load();
    } catch { actionError = "This proposal could not be decided. Refresh in case it changed elsewhere."; }
  }
  async function scanRelationships() {
    if (busy) return;
    busy = true; actionError = null;
    try { await api.scanMemoryRelationships(); await load(); }
    catch { actionError = "Could not scan approved memories for relationships."; }
    finally { busy = false; }
  }
  async function decideRelationship(proposal: MemoryRelationshipProposal, decision: "approved" | "denied") {
    try {
      await api.decideMemoryRelationshipProposal(proposal.candidate_id, decision, proposal.decision);
      await load();
    } catch { actionError = "This relationship could not be decided. Refresh in case it changed elsewhere."; }
  }
  async function changeScope(m: MemoryControlView) {
    const scope = window.prompt("New scope (account, project, project:<id>, session, or session:<id>)", m.scope);
    if (!scope || scope === m.scope) return;
    const reason = window.prompt("Why is this scope appropriate?", "Owner-requested scope change");
    if (reason === null) return;
    try { await api.changeMemoryScope(m.memory_id, scope, m.updated_at, reason); await load(); }
    catch { actionError = "Could not change scope. Refresh in case this memory changed elsewhere."; }
  }
  async function viewHistory(m: MemoryControlView) {
    try { historyById = { ...historyById, [m.memory_id]: (await api.memoryHistory(m.memory_id)).events }; }
    catch { actionError = "Could not load this memory's history."; }
  }
  async function reviewExpiry(m: MemoryControlView) {
    const value = window.prompt("Review/expiry date as ISO-8601, or leave blank for no expiry", m.expires_at ?? "");
    if (value === null) return;
    try { await api.setMemoryExpiry(m.memory_id, value.trim() || null); await load(); }
    catch { actionError = "Could not update the review or expiry date."; }
  }
  async function purge(m: MemoryControlView) {
    try {
      const preview = await api.previewMemoryPurge(m.memory_id);
      const confirmation = window.prompt(`Permanent deletion removes ${preview.artifacts.length} active artifact(s). Backups: ${preview.backup_disposition}. Type ${m.memory_id} to continue.`);
      if (confirmation !== m.memory_id) return;
      await api.purgeMemory(m.memory_id);
      await load();
    } catch { actionError = "Could not permanently delete this memory."; }
  }
  async function exportMemories() {
    try {
      const exported = await api.exportMemories();
      const url = URL.createObjectURL(new Blob([JSON.stringify(exported, null, 2)], { type: "application/json" }));
      const anchor = document.createElement("a"); anchor.href = url; anchor.download = "raiker-memories.json"; anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch { actionError = "Could not export memories."; }
  }
  async function reviewImport(event: Event) {
    // Held before the first await: `currentTarget` is cleared once the event
    // has finished dispatching.
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    try {
      const parsed = JSON.parse(await file.text()) as unknown;
      const values = Array.isArray(parsed) ? parsed : typeof parsed === "object" && parsed !== null && Array.isArray((parsed as { memories?: unknown }).memories) ? (parsed as { memories: unknown[] }).memories : [];
      if (!values.every((value) => typeof value === "object" && value !== null && typeof (value as { text?: unknown }).text === "string")) throw new Error("schema");
      importPreview = values as MemoryImport; importFileName = file.name; actionError = null;
      importNotice = null;
      importExcluded = new Set();
      // BUG-244 — ask what this would actually change before offering to do it.
      // A read: it writes nothing, so it is safe on every file chosen.
      importAlready = null;
      try { importAlready = await api.previewMemoryImport(importPreview); }
      catch { importAlready = null; }
    } catch { importPreview = null; importAlready = null; actionError = "This file is not a valid Raiker memory export."; }
    // A file input keeps its value, so choosing the same file again after an
    // undo would otherwise not fire `change`.
    input.value = "";
  }
  function toggleImportRecord(index: number) {
    const next = new Set(importExcluded);
    if (next.has(index)) next.delete(index); else next.add(index);
    importExcluded = next;
  }
  /** Records that would be written: new or similar, and not skipped by the owner. */
  const importChosen = $derived(
    (importAlready?.records ?? []).filter(
      (record) => (record.status === "new" || record.status === "similar") && !importExcluded.has(record.index),
    ).length,
  );
  const IMPORT_STATUS_LABELS: Record<string, string> = {
    new: "New",
    similar: "Like one you have",
    duplicate: "Already stored",
    duplicate_in_file: "Repeated in this file",
  };
  async function undoImport(batch: MemoryImportBatch) {
    if (!window.confirm(`Undo the import of ${batch.imported} record${batch.imported === 1 ? "" : "s"}${batch.file_name ? ` from ${batch.file_name}` : ""}? Each one is forgotten, except any you have changed since.`)) return;
    try {
      const result = await api.undoMemoryImport(batch.batch_id);
      const kept = result.kept_changed > 0 ? ` Kept ${result.kept_changed} you changed since.` : "";
      importNotice = `Undid the import: forgot ${result.removed} record${result.removed === 1 ? "" : "s"}.${kept}`;
      await load();
    } catch (e) {
      actionError = e instanceof ApiError && e.status === 409 ? "That import was already undone." : "Could not undo that import.";
    }
  }
  async function applyImport(skipDuplicates = true) {
    if (!importPreview) return;
    importBusy = true;
    try {
      const result = await api.importMemories(importPreview, skipDuplicates, {
        excludeIndices: [...importExcluded],
        fileName: importFileName,
      });
      // BUG-244 — say what changed, not how many records were offered.
      const skipped = [
        result.skipped_duplicates > 0 ? `${result.skipped_duplicates} already stored` : "",
        result.skipped_by_owner > 0 ? `${result.skipped_by_owner} you left out` : "",
      ].filter(Boolean).join(", ");
      importNotice = `Imported ${result.imported} record${result.imported === 1 ? "" : "s"}${skipped ? `; skipped ${skipped}` : ""}.${result.batch_id ? " You can undo this import below." : ""}`;
      importPreview = null; importAlready = null; importFileName = ""; importExcluded = new Set();
      await load();
    }
    catch { actionError = "Could not import memories."; }
    finally { importBusy = false; }
  }
  // BUG-27 — opening the passage a memory was drawn from. Provenance that
  // cannot be checked is indistinguishable, from where the owner sits, from
  // provenance that was invented; this is the check. Resolved on demand,
  // because the answer depends on what is still readable now.
  let sourceFor = $state<MemoryControlView | null>(null);
  let sourceExcerpt = $state<SourceExcerptView | null>(null);
  let sourceLoading = $state(false);

  async function viewSource(m: MemoryControlView) {
    sourceFor = m;
    sourceExcerpt = null;
    sourceLoading = true;
    try {
      sourceExcerpt = await api.memorySource(m.memory_id);
    } catch {
      // The resolver answers every knowable case with a status, so reaching
      // here means the runtime itself could not be asked. Say that, rather
      // than implying the memory has no source.
      sourceExcerpt = {
        status: "no_provenance",
        resolution_method: "",
        kind: "",
        title: "",
        excerpt: "",
        highlight_start: -1,
        highlight_length: 0,
        session_id: "",
        turn_id: "",
        attachment_id: "",
        truncated: false,
      };
      actionError = "Could not reach the runtime to open this memory's source.";
    } finally {
      sourceLoading = false;
    }
  }

  function closeSource() {
    sourceFor = null;
    sourceExcerpt = null;
    sourceLoading = false;
  }

  // MEM-07 — the retention classes were stated on every row and nothing ever
  // acted on them, so `turn_only` and `short_term_7_days` records were kept
  // forever. There is still no cleanup daemon, which is deliberate; this is the
  // deliberate alternative that was missing — the owner is shown what is due
  // and confirms it, and the server refuses anything its own preview did not
  // list.
  const dueForExpiry = $derived(observations?.due_for_expiry ?? []);
  let sweepResult = $state<string | null>(null);
  async function sweepExpired() {
    if (busy || !dueForExpiry.length) return;
    if (!window.confirm(`Remove ${dueForExpiry.length} observation records whose retention has run out? Raiker keeps no copy of the material they describe.`)) return;
    busy = true; actionError = null; sweepResult = null;
    try {
      const result = await api.cleanupExpiredObservations(dueForExpiry);
      sweepResult = `Removed ${result.deleted_observation_ids.length}.`;
      await load();
    } catch (e) {
      actionError = e instanceof ApiError ? `Could not run the retention cleanup (${e.status}).` : "Could not run the retention cleanup.";
    } finally { busy = false; }
  }
  async function deleteObservation(observationId: string) {
    if (!window.confirm("Delete this observation? Raiker keeps no copy of the material it describes, so this removes the record that it was seen.")) return;
    try { await api.deleteObservations([observationId]); await load(); }
    catch { actionError = "Could not delete this observation."; }
  }
  async function discardGist(gistId: string) {
    try { await api.discardGist(gistId); await load(); }
    catch { actionError = "Could not discard this proposed gist."; }
  }
  const observationRows = $derived(
    (observations?.observations ?? []).filter((o) =>
      observationFilter === "all"
      || (observationFilter === "skipped" && o.capture_status === "skipped")
      || (observationFilter === "gist" && o.gist_status === "pending_review")
      || o.source_type === observationFilter,
    ),
  );
  const observationSources = $derived([...new Set((observations?.observations ?? []).map((o) => o.source_type))]);
  function retentionLabel(retention: string): string {
    if (retention === "turn_only") return "Kept for this turn";
    if (retention === "short_term_7_days") return "Kept 7 days";
    if (retention === "short_term_30_days") return "Kept 30 days";
    if (retention === "project_lifetime") return "Kept for the project";
    if (retention === "legal_hold") return "Legal hold";
    return "Kept until forgotten";
  }

  function provenanceLabel(m: MemoryControlView): string {
    const title = m.provenance["source_title"] ?? m.provenance["session_title"] ?? m.provenance["path"];
    return title ? `${m.source} — ${String(title)}` : m.source || "Source not available";
  }

  function isApproved(m: MemoryControlView): boolean {
    return m.approval_state === "approved" || m.approval_state === "policy_allowed";
  }

  let { tab = "overview", filter = null }: { tab?: string; filter?: string | null } = $props();
  $effect(() => {
    if (isMemoryFilter(filter)) statusFilter = filter;
  });

  const tabs = HUB_TABS.memory.map((id) => ({
    id,
    label: MEMORY_TAB_LABELS[id as MemoryTab] ?? id,
  }));

  /** The hash owns which panel is open, so a deep link and the strip agree. */
  function selectTab(next: string, listFilter?: MemoryFilter) {
    const filterPart = listFilter ? `&filter=${encodeURIComponent(listFilter)}` : "";
    window.location.hash = `#/memory?tab=${encodeURIComponent(next)}${filterPart}`;
  }

  // Every approved record the page was given, recallable or not, and the
  // recallable ones — the only ones a turn can be given.
  const records = $derived((memories ?? []).filter(isApproved));
  const approved = $derived(records.filter((m) => isRecallable(m)));
  const pending = $derived(proposals);
  const expired = $derived(records.filter((m) => memoryState(m) === "expired"));
  const scopes = $derived([...new Set((memories ?? []).map((m) => m.scope))]);
  const sensitivities = $derived([...new Set((memories ?? []).map((m) => m.sensitivity))]);
  const filtered = $derived(
    records.filter((m) => {
      return matchesFilter(m, statusFilter) && (scopeFilter === "all" || m.scope === scopeFilter) && (sensitivityFilter === "all" || m.sensitivity === sensitivityFilter) && (!pinnedOnly || m.pinned) && `${m.text} ${provenanceLabel(m)} ${m.tags.join(" ")}`.toLowerCase().includes(query.toLowerCase());
    }).sort((a, b) => sort === "review-date" ? (a.expires_at ?? "9999").localeCompare(b.expires_at ?? "9999") : b.created_at.localeCompare(a.created_at)),
  );
  const retention = $derived(retentionRows(retentionSummary(records)));
  const pipeline = $derived(
    memoryPipeline({
      observations: observations ? observations.captured : null,
      suggestions: pending.length + relationshipProposals.length,
      memories: records,
    }),
  );
  /** One reading of what the hub holds, shared by the Overview and its tabs. */
  const counts = $derived<MemoryCounts>({
    approved: approved.length,
    pinned: approved.filter((m) => m.pinned).length,
    expired: expired.length,
    proposals: pending.length,
    relationshipProposals: relationshipProposals.length,
    observations: observations?.observations?.length ?? 0,
  });
  const attention = $derived(memoryAttention(counts));

  $effect(() => { void load(); });
</script>

<header class="page-intro"><GuideLink route="memory" /><button class="btn btn-ghost btn-sm" type="button" onclick={load}><Icon name="refresh" size="sm" /> Refresh</button></header>

<!-- Memory carried approved records, proposals, observations, a document
     library, two recall controls and an import/export drawer at one visual
     level, so telling administration from content meant reading all of it, and
     the one proposal waiting on a decision looked exactly like the settings
     above it. It is a hub now, and Overview leads for the same reason it does
     on Extensions and Models: people arrive asking whether anything is waiting
     on them and what Raiker can recall, not to look at a category. -->
<TabStrip {tabs} selected={tab} onselect={selectTab} label="Memory sections" />

<section class="posture-card posture-{posture.kind}" role="note" aria-label="Memory permission posture">
  <Icon name={posture.kind === "proposes" ? "check" : "info"} size="md" />
  <p>{posture.headline}</p>
  {#if posture.action}<a class="posture-action" href="#/capabilities">{posture.action} →</a>{/if}
</section>

<!-- An action's failure belongs above the panels, not inside one: the action
     that failed may have been taken on a tab the owner has since left. -->
{#if actionError}<p class="notice notice-danger" role="alert">{actionError}</p>{/if}

{#if loadError}<PageState state="error" title="Couldn't load memories" detail={loadError} />
{:else if memories === null}<PageState state="loading" title="Loading memories…" />
{:else if tab === "overview"}
  <div id="panel-overview" role="tabpanel" aria-labelledby="tab-overview">
    <p class="page-lead">{memorySentence(counts)}</p>

  <!-- UX-MEM-06 — where every record is in the one pipeline it passes
       through, so "why is Raiker using this?" has an answer on the page that
       lists it. The empty-board rule still holds: on a fresh install every
       count is 0, which is the sentence above restated, so the strip appears
       once there is something in it. -->
  {#if pipeline.some((stage) => (stage.count ?? 0) > 0)}
  <section class="pipeline" aria-label="How a memory moves through Raiker">
    <ol>
      {#each pipeline as stage (stage.id)}
        <li>
          <a href={stage.href}>
            <strong>{stage.count === null ? "—" : stage.count}</strong>
            <span>{stage.label}</span>
          </a>
          <p>{stage.meaning}</p>
        </li>
      {/each}
    </ol>
  </section>
  {/if}

  <!-- UX-MEM-03 — retention as a policy, not as a date on each card: what is
       kept, what is about to lapse, what has gone quiet, and what is no longer
       recalled. Each row opens the records it counts. -->
  {#if records.length > 0}
  <section class="memory-section retention" aria-label="Retention">
    <div class="section-head"><h3>Retention</h3></div>
    <ul class="retention-list">
      {#each retention as row (row.filter + row.label)}
        <li>
          <span class="retention-count">{row.count}</span>
          <span class="retention-text"><strong>{row.label}</strong><small>{row.note}</small></span>
          {#if row.count > 0}
            <button type="button" class="btn btn-ghost btn-sm" onclick={() => selectTab("memories", row.filter)}>Show</button>
          {/if}
        </li>
      {/each}
    </ul>
  </section>
  {/if}

    {#if attention.length > 0}
      <!-- The attention half of the hub. Only decisions appear here:
           an expired memory has already stopped being recalled, so it is a fact
           in the summary above rather than a row saying "act on this" about
           something with nothing to act on. -->
      <section class="memory-section" aria-label="Waiting on you">
        <div class="section-head"><h3>Waiting on you</h3></div>
        <ul class="attention-list">
          {#each attention as item (item.label)}
            <li>
              <span><strong>{item.count}</strong> {item.label}</span>
              <button type="button" class="btn btn-sm" onclick={() => selectTab(item.tab)}>
                Open {MEMORY_TAB_LABELS[item.tab]}
              </button>
            </li>
          {/each}
        </ul>
      </section>
    {/if}
  </div>
{:else if tab === "memories"}
  <div id="panel-memories" role="tabpanel" aria-labelledby="tab-memories">
  <section class="filters" aria-label="Filter memories">
    <label class="search"><Icon name="search" size="md" /><input bind:value={query} aria-label="Search memories" placeholder="Search memories…" /></label>
    <select bind:value={statusFilter} aria-label="Memory status">{#each MEMORY_FILTERS as option (option)}<option value={option}>{MEMORY_FILTER_LABELS[option]}</option>{/each}</select>
    <select bind:value={scopeFilter} aria-label="Memory scope"><option value="all">All scopes</option>{#each scopes as scope}<option value={scope}>{scope}</option>{/each}</select>
    <select bind:value={sensitivityFilter} aria-label="Memory sensitivity"><option value="all">All sensitivities</option>{#each sensitivities as sensitivity}<option value={sensitivity}>{sensitivity}</option>{/each}</select>
    <select bind:value={sort} aria-label="Sort memories"><option value="recently-approved">Recently approved</option><option value="review-date">Review date</option></select>
    <label class="pinned-filter"><input type="checkbox" bind:checked={pinnedOnly} /> Pinned only</label>
  </section>

  <section class="memory-section"><div class="section-head"><h3>{statusFilter === "active" ? "Approved memories" : MEMORY_FILTER_LABELS[statusFilter]}</h3><span>{filtered.length}</span></div>
    <!-- The posture card at the top of the page already states *why* there are
         none. Repeating its sentence here put the same line on screen twice;
         the empty state keeps the action, which is the half that is not
         already said. -->
    {#if records.length === 0}<div class="empty"><Icon name="spark" size="xl" /><h4>No approved memories yet</h4><a href={posture.action ? "#/capabilities" : "#/approvals"}>{posture.action ?? "Learn how governed review works"}</a></div>
    {:else if filtered.length === 0}<div class="empty"><h4>No memories match these filters</h4><p>Clear or change the filters to see approved memories.</p></div>
    {:else}<div class="memory-grid">{#each filtered as m (m.memory_id)}<article class="memory-card" class:pinned={m.pinned}>
      <div class="memory-title">{#if editingId === m.memory_id}<textarea rows="3" bind:value={editDraft} aria-label="Memory text"></textarea>{:else}<h4>{m.text}</h4>{/if}{#if m.pinned}<span class="pin-label"><Icon name="check" size="sm" /> Pinned</span>{/if}</div>
      <!-- UX-MEM-04 — who put it there, in words; UX-MEM-02 — its state, when
           it is anything but current. -->
      <div class="meta">{#if memoryState(m) !== "current"}<span class="state-chip state-{memoryState(m)}">{MEMORY_STATE_LABELS[memoryState(m)]}</span>{/if}<span>{memoryEvidence(m).label}</span><span>{m.scope} scope</span><span>{m.sensitivity} sensitivity</span></div>
      <dl><div><dt>Source</dt><dd>{provenanceLabel(m)}</dd></div><div><dt>Approved</dt><dd>{relativeTime(m.created_at)}</dd></div><div><dt>Review or expiry</dt><dd>{m.expires_at ? relativeTime(m.expires_at) : "No date set"}</dd></div></dl>
      <!-- REM-MEM-01 — two everyday actions and one way in to the rest, so
           "edit the words" and "delete this permanently" never share a weight,
           and showing something never looks like changing what Raiker
           remembers. -->
      <div class="card-actions">{#if editingId === m.memory_id}<button class="btn btn-primary btn-sm" aria-label="Save memory" onclick={() => void saveEdit(m)}>Save</button><button class="btn btn-ghost btn-sm" onclick={() => editingId = null}>Cancel</button>{:else}<button class="btn btn-ghost btn-sm" aria-label="Edit memory" onclick={() => { editingId = m.memory_id; editDraft = m.text; }}>Edit</button><button class="btn btn-ghost btn-sm" aria-label={m.pinned ? "Unpin memory" : "Pin memory"} onclick={() => void togglePin(m)}>{m.pinned ? "Unpin" : "Pin"}</button><button class="btn btn-ghost btn-sm" aria-expanded={drawerId === m.memory_id} aria-label={`More for “${m.text.slice(0, 40)}”`} onclick={() => drawerId = drawerId === m.memory_id ? null : m.memory_id}>More</button>{/if}</div>
      {#if drawerId === m.memory_id}
        <MemoryRecordDrawer
          record={drawerRecord}
          history={historyById[m.memory_id] ?? null}
          onClose={() => (drawerId = null)}
          onViewSource={(r) => void viewSource(r)}
          onChangeScope={(r) => void changeScope(r)}
          onReviewExpiry={(r) => void reviewExpiry(r)}
          onViewHistory={(r) => void viewHistory(r)}
          onForget={(r) => void forget(r)}
          onPurge={(r) => void purge(r)}
          onArchive={(r, archived) => void setArchived(r, archived)}
        />
      {/if}
    </article>{/each}</div>{/if}
  </section>
  </div>
{:else if tab === "suggestions"}
  <div id="panel-suggestions" role="tabpanel" aria-labelledby="tab-suggestions">
  {#if pending.length}
    <section class="memory-section"><div class="section-head"><h3>Pending review</h3><span>{pending.length}</span></div>
      {#each pending as proposal (proposal.candidate_id)}<article class="memory-card pending">
        {#if proposalEditingId === proposal.candidate_id}<textarea rows="3" bind:value={proposalDraft} aria-label="Edit proposed memory"></textarea>{:else}<h4>{proposal.text}</h4>{/if}
        <p>Proposed from event: {proposal.source_event_id}</p>
        <div class="meta"><span>{proposal.scope}</span><span>{proposal.sensitivity} sensitivity</span><span title={proposalEvidence(proposal.confidence).why}>{proposalEvidence(proposal.confidence).label}</span></div>
        <details><summary>View source details</summary><p>Source event: {proposal.source_event_id}. The original event remains governed by its session access.</p></details>
        <div class="card-actions">
          {#if proposalEditingId === proposal.candidate_id}<button class="btn btn-primary btn-sm" onclick={() => void decideProposal(proposal, "approved", proposalDraft)}>Approve edited proposal</button><button class="btn btn-ghost btn-sm" onclick={() => proposalEditingId = null}>Cancel</button>
          {:else}<button class="btn btn-primary btn-sm" onclick={() => void decideProposal(proposal, "approved")}>Approve</button><button class="btn btn-ghost btn-sm" onclick={() => { proposalEditingId = proposal.candidate_id; proposalDraft = proposal.text; }}>Edit &amp; approve</button><button class="btn btn-ghost btn-sm danger" onclick={() => void decideProposal(proposal, "rejected")}>Reject</button>{/if}
        </div>
      </article>{/each}
    </section>
  {/if}

  <section class="memory-section relationship-review">
    <div class="section-head">
      <div><h3>Relationship review</h3><p>Only approved relationships can enter recall and the Knowledge Map.</p></div>
      <button class="btn btn-ghost btn-sm" type="button" disabled={busy} onclick={() => void scanRelationships()}>{busy ? "Scanning…" : "Scan approved memories"}</button>
    </div>
    {#if relationshipProposals.length}
      {#each relationshipProposals as proposal (proposal.candidate_id)}
        <article class="memory-card pending relationship-card">
          <h4>{proposal.subject_name} <span>{proposal.predicate.replaceAll("_", " ")}</span> {proposal.object_name}</h4>
          <blockquote>{proposal.evidence_text}</blockquote>
          <div class="meta"><span>{proposal.subject_type} → {proposal.object_type}</span><span title={proposalEvidence(proposal.confidence).why}>{proposalEvidence(proposal.confidence).label}</span><span>{proposal.extractor_version}</span></div>
          <p>Evidence: {proposal.evidence_memory_id}. Approving adds the reviewed edge; denying leaves the evidence memory unchanged.</p>
          <div class="card-actions"><button class="btn btn-primary btn-sm" onclick={() => void decideRelationship(proposal, "approved")}>Approve relationship</button><button class="btn btn-ghost btn-sm danger" onclick={() => void decideRelationship(proposal, "denied")}>Reject relationship</button></div>
        </article>
      {/each}
    {:else}
      <p class="muted">No relationship proposals are waiting for review.</p>
    {/if}
  </section>

  <!-- MEM-04 — the capture half of eidetic memory, made visible. Every row
       here is metadata about material the runtime saw; none of it is the
       material. A row that reads "Not captured" is a refusal that happened,
       which is the only thing that makes an empty list readable. -->
  <section class="memory-section" aria-label="Observations">
    <div class="section-head">
      <div>
        <h3>Observations</h3>
        <p class="section-note">What Raiker recorded seeing while it worked — provenance, a checksum and a retention class, never the material itself.</p>
      </div>
      <span>{observations ? `${observations.captured} captured · ${observations.skipped} not captured` : "—"}</span>
    </div>
    {#if dueForExpiry.length}
      <div class="due-row" role="note">
        <Icon name="info" size="sm" />
        <span>{dueForExpiry.length} past their retention class.</span>
        <button class="btn btn-sm" type="button" disabled={busy} onclick={() => void sweepExpired()}>Remove</button>
      </div>
    {:else if sweepResult}
      <div class="due-row" role="status"><Icon name="check" size="sm" /><span>{sweepResult}</span></div>
    {/if}
    {#if observations === null}
      <div class="empty"><Icon name="info" size="xl" /><h4>Observation capture is not reporting</h4><p>The runtime could not be asked what it captured. This is not the same as having captured nothing.</p></div>
    {:else}
      {#if observations.observations.length}
        <div class="filters">
          <select bind:value={observationFilter} aria-label="Observation kind">
            <option value="all">All observations</option>
            <option value="skipped">Not captured (sensitivity)</option>
            <option value="gist">Gist pending review</option>
            {#each observationSources as source (source)}<option value={source}>{source.replaceAll("_", " ")}</option>{/each}
          </select>
        </div>
      {/if}
      {#if observations.observations.length === 0}
        <div class="empty"><Icon name="spark" size="xl" /><h4>No observations yet</h4><p>Raiker records one observation each time a governed tool returns material. Run a turn that reads a file or searches the workspace and it will appear here.</p></div>
      {:else if observationRows.length === 0}
        <div class="empty"><h4>No observations match this filter</h4><p>Choose a different kind to see what was captured.</p></div>
      {:else}
        <div class="memory-grid">
          {#each observationRows as o (o.observation_id)}
            <article class="memory-card observation" class:refused={o.capture_status === "skipped"}>
              <div class="memory-title"><h4>{o.summary}</h4>{#if o.capture_status === "skipped"}<span class="refused-label"><Icon name="info" size="sm" /> Not captured</span>{/if}</div>
              <div class="meta">
                <span>{o.source_type.replaceAll("_", " ")}</span>
                <span>{retentionLabel(o.retention)}</span>
                <span>{o.sensitivity} sensitivity</span>
                {#if o.promotable_to_memory}<span>May be proposed as memory</span>{/if}
              </div>
              {#if o.capture_status === "skipped"}
                <p class="refused-note">Refused on sensitivity ({o.skip_reason.replace("observation_sensitivity_", "").replaceAll("_", " ")}). No checksum of the material was kept either.</p>
              {/if}
              <dl>
                <div><dt>Seen</dt><dd>{relativeTime(o.created_at)}</dd></div>
                <div><dt>Expires</dt><dd>{o.expires_at ? relativeTime(o.expires_at) : "No automatic expiry"}</dd></div>
                <div><dt>Checksum</dt><dd>{o.content_sha256 ? `${o.content_sha256.slice(0, 12)}… · ${o.content_bytes} bytes` : "None kept"}</dd></div>
              </dl>
              {#if o.gist_status === "pending_review"}
                <p class="gist-note"><Icon name="spark" size="sm" /> Gist proposed and pending review: “{o.gist_summary}”. It becomes durable memory only through the same approval every other memory needs.</p>
              {/if}
              <div class="card-actions">
                {#if o.gist_id}<button class="btn btn-ghost btn-sm" onclick={() => void discardGist(o.gist_id)}>Discard gist</button>{/if}
                <button class="btn btn-ghost btn-sm danger" aria-label={`Delete observation ${o.observation_id}`} onclick={() => void deleteObservation(o.observation_id)}>Delete</button>
              </div>
            </article>
          {/each}
        </div>
      {/if}
    {/if}
  </section>
  </div>
{:else if tab === "sources"}
  <div id="panel-sources" role="tabpanel" aria-labelledby="tab-sources">
    <!-- The document library was always kept apart from the atomic records and
         outside their filters: an uploaded workbook and an approved remembered
         sentence are different kinds of thing, and mixing them into one list
         makes it impossible to tell which one answered a question. A tab of its
         own is the same separation, stated by the page's structure. -->
  <!-- BUG-305 — the owner's question answered once, over both controllers. The
       library below stays: it is how a document is *added*, and adding is where
       the two kinds genuinely differ. -->
  <section class="memory-section" aria-label="Sources Raiker can read">
    <KnowledgeSources onchange={() => void load()} />
  </section>

  <section class="memory-section library-section" aria-label="Memory document library">
    <FileLibrary
      scope="memory"
      heading="Document library"
      description="Files kept under Raiker's managed memory storage. Uploaded content is data, never instructions."
      onLibraryChange={() => void load()}
    />
    <!-- BUG-305 — adding is where the two kinds differ and stay separate: a
         document is imported here, a folder is granted on the Map with its own
         picker. What they can no longer differ about is the inventory above,
         which lists both and stops either. -->
    <p class="control-note">
      To let Raiker read a folder where it already lives, grant it on the
      <a href="#/brain">Knowledge Map</a>.
    </p>
  </section>
  </div>
{:else}
  <div id="panel-recall" role="tabpanel" aria-labelledby="tab-recall">
{#if settings}
  <section class="control-card">
    <div><h3>Incognito session</h3><p>Do not use approved memories in new conversations and tasks. Stored memories are not deleted.</p></div>
    <button class="switch" class:on={settings.incognito} role="switch" aria-checked={settings.incognito} aria-label="Incognito session" disabled={busy} onclick={() => void toggleIncognito()}><span></span><b>{settings.incognito ? "On" : "Off"}</b></button>
  </section>

  <section class="control-card">
    <div>
      <h3>Recall backend</h3>
      <!-- MEM-11 — the setting governs both the memories Raiker attaches to a
           turn on its own and the search the assistant runs itself. That was
           not always true, and the guide is where the distinction is
           explained; this card states only what is in force. -->
      <!-- One flex child, not three: the icon and the sentence. With the words
           as separate children a narrow window broke the model name across two
           columns and stranded the clause beside it. -->
      <p class="posture-line" data-semantic={recall === "semantic"}>
        <Icon name={recall === "semantic" ? "check" : "info"} size="sm" />
        <span>
          {#if recall === "semantic"}
            Searching <b>{retrieval.model}</b> — matches meaning.
          {:else if recall === "stored_only"}
            Stored in <b>{retrieval.model}</b>. Recall still matches words: a
            question is not embedded into this space yet.
          {:else}
            Searching <b>{retrieval.model}</b> — matches words, not meaning.
          {/if}
        </span>
      </p>
      <!-- The index's mechanics are in the guide's *Recall backend and token
           budget*; this page keeps the one number a reader might check. -->
      {#if settings.vector_search_strategy === "exact_then_approximate"}
        <p class="control-note">
          Ranks {settings.vector_search_exact_limit ?? 512} vectors exactly, then approximates.
        </p>
      {/if}
      <!-- REM-MEM-03 — the health, and the way to repair it. Which space recall
           searches, and building one, are engine configuration and moved to
           Settings → Memory engine; what an owner reading their own memories
           needs here is whether recall is matching meaning or only words, and
           one link when it is not what they wanted. -->
      <p class="control-note">
        <a href="#/settings?tab=memory-engine">Change the recall backend, or build a
        meaning-based index</a>
      </p>
    </div>
  </section>
{/if}

  <details class="advanced"><summary><span><strong>Advanced memory management</strong><small>Import or export governed memory records.</small></span><Icon name="chevron-down" size="md" /></summary><div class="advanced-body"><button class="btn btn-ghost" onclick={() => void exportMemories()}>Export memories</button><label class="btn btn-ghost file-button">Review import<input type="file" accept="application/json,.json" onchange={(e) => void reviewImport(e)} /></label>{#if importPreview}
      <!-- BUG-244 — what this would change, before it changes anything. A
           re-import must not duplicate: recall is budgeted, and four copies of
           one sentence take four of the slots a turn has for remembering. -->
      <div class="import-review" role="status">
        <strong>{importFileName}</strong>
        {#if importAlready === null}
          <span>{importPreview.length} valid record{importPreview.length === 1 ? "" : "s"} ready for governed import.</span>
          <button class="btn btn-primary btn-sm" disabled={importBusy} onclick={() => void applyImport()}>Import reviewed records</button>
        {:else}
          <!-- UX-MEM-08 — the file is an untrusted batch. Say what it looks
               like, then what each record would do, and let the owner leave
               any of them out before anything is written. -->
          <span class="import-class">
            {importAlready.source_class === "raiker_export"
              ? "Looks like a Raiker export."
              : "Not a Raiker export — read each record before you import it."}
            Imported records are marked as imported by you.
          </span>
          <ul class="import-records" aria-label="Records in this file">
            {#each importAlready.records ?? [] as record (record.index)}
              {@const writable = record.status === "new" || record.status === "similar"}
              <li class="import-record" class:skipped={!writable || importExcluded.has(record.index)}>
                <label>
                  <input
                    type="checkbox"
                    disabled={!writable || importBusy}
                    checked={writable && !importExcluded.has(record.index)}
                    onchange={() => toggleImportRecord(record.index)}
                    aria-label={`Import “${record.text.slice(0, 60)}”`}
                  />
                  <span class="import-text">{record.text}</span>
                </label>
                <span class="import-status status-{record.status}">{IMPORT_STATUS_LABELS[record.status] ?? record.status}</span>
              </li>
            {/each}
          </ul>
          {#if importAlready.total > (importAlready.records ?? []).length}
            <span class="muted">Showing the first {(importAlready.records ?? []).length} of {importAlready.total}.</span>
          {/if}
          {#if importChosen === 0}
            <span>Nothing selected to import. Records already stored are skipped so recall is not spent on copies.</span>
            {#if importAlready.duplicate_count > 0}
              <button class="btn btn-ghost btn-sm" disabled={importBusy} onclick={() => void applyImport(false)}>Import all {importAlready.total} anyway</button>
            {/if}
          {:else}
            <button class="btn btn-primary btn-sm" disabled={importBusy} onclick={() => void applyImport()}>
              {importBusy ? "Importing…" : `Import ${importChosen} record${importChosen === 1 ? "" : "s"}`}
            </button>
          {/if}
        {/if}
      </div>
    {/if}
    {#if importNotice}<p class="import-notice" role="status">{importNotice}</p>{/if}
    {#if importBatches.length > 0}
      <!-- UX-MEM-08 — each import is a receipt that can be taken back. -->
      <section class="import-batches" aria-label="Recent imports">
        <h4>Recent imports</h4>
        <ul>
          {#each importBatches as batch (batch.batch_id)}
            <li>
              <span>
                <strong>{batch.imported} record{batch.imported === 1 ? "" : "s"}</strong>
                {#if batch.file_name}from {batch.file_name}{/if}
                · {relativeTime(batch.created_at)}
                {#if batch.skipped > 0}· {batch.skipped} skipped{/if}
              </span>
              {#if batch.undone_at}
                <span class="muted">Undone {relativeTime(batch.undone_at)}</span>
              {:else}
                <button class="btn btn-ghost btn-sm" type="button" onclick={() => void undoImport(batch)}>Undo import</button>
              {/if}
            </li>
          {/each}
        </ul>
      </section>
    {/if}</div></details>
  </div>
{/if}

{#if sourceFor !== null}
  <FileInspector
    preview={null}
    filename={sourceFor.text.slice(0, 60)}
    source={sourceExcerpt}
    {sourceLoading}
    onclose={closeSource}
  />
{/if}

<style>
  .page-intro,.control-card,.section-head,.memory-title,.card-actions,.advanced summary { display:flex; align-items:flex-start; justify-content:space-between; gap:var(--space-3); } .page-intro { margin-bottom:var(--space-4); } .control-card h3,.section-head h3,.memory-card h4,.empty h4 { margin:0; } .page-intro p,.control-card p { margin:.25rem 0 0; color:var(--text-2); }
  .control-card { padding:var(--space-4); border:1px solid var(--border); border-radius:var(--r-lg); background:var(--surface); }
  .control-card + .control-card { margin-top:var(--space-3); }
  /* MEM-03 — the sentence that says which embedding is in force. It is a
     statement of fact rather than an alert, so it uses the same tone treatment
     as the posture strip above rather than a second, louder one. */
  .posture-line { display:flex; align-items:baseline; gap:.4rem; margin-top:var(--space-2) !important; font-size:var(--text-sm); }
  .posture-line :global(svg) { flex:none; align-self:center; color:var(--warn,var(--text-3)); }
  .posture-line[data-semantic="true"] :global(svg) { color:var(--ok,var(--text-3)); }
  .backend-field { flex:none; min-width:14rem; }
  /* A secondary clause under the lead, not a second lead. */
  .due-row { display:flex; align-items:center; gap:var(--space-2); margin-bottom:var(--space-3); font-size:var(--text-sm); color:var(--text-2); }
  .due-row :global(svg) { flex:none; color:var(--warn,var(--text-3)); }
  .due-row[role="status"] :global(svg) { color:var(--ok,var(--text-3)); }
  .index-row { display:flex; gap:var(--space-2); align-items:center; margin-top:var(--space-2); flex-wrap:wrap; }
  /* BUG-284 — two mobile bleeds this page had as soon as it held anything.
     `min-width:0` lets the label shrink; the select inside it still claims the
     width of its longest option unless it is told otherwise. And an approved
     memory offers seven controls in a row that could not wrap, so at 390px the
     card bled 145px past its own edge and over the one beside it. Neither was
     visible on an empty workspace, which is why the width sweep went green on a
     fresh instance and red on a used one. */
  .index-field { flex:1 1 14rem; min-width:0; }
  /* BUG-71 — the posture strip states what this page can actually promise. It
     sits above everything else because it changes the meaning of the counts
     below it: "0 Pending review" reads very differently when nothing is able
     to propose. */
  .posture-card { display:flex; align-items:flex-start; gap:var(--space-2); padding:var(--space-3) var(--space-4); margin-bottom:var(--space-4); border:1px solid var(--border); border-radius:var(--r-lg); background:var(--sunken); }
  .posture-card p { margin:0; color:var(--text-2); flex:1; }
  .posture-card :global(svg) { flex:none; margin-top:.1rem; color:var(--text-3); }
  .posture-proposes { border-color:var(--ok-border,var(--border)); }
  .posture-proposes :global(svg) { color:var(--ok,var(--text-3)); }
  .posture-denied :global(svg),.posture-unknown :global(svg) { color:var(--warn,var(--text-3)); }
  .posture-action { flex:none; white-space:nowrap; font-weight:600; }
  .switch { min-width:76px; min-height:44px; display:flex; align-items:center; gap:.45rem; border:1px solid var(--border-strong); border-radius:var(--r-pill); padding:.25rem .55rem .25rem .3rem; background:var(--sunken); color:var(--text-2); cursor:pointer; } .switch span { width:1.65rem; height:1.65rem; border-radius:50%; background:var(--text-3); } .switch.on { background:var(--accent-soft); color:var(--accent); border-color:var(--accent-border); } .switch.on span { background:var(--accent); }
  /* UX-MEM-06 — the pipeline reads left to right on a wide window and top to
     bottom on a narrow one; a count is a link to where those records live. */
  .pipeline ol { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:1px; margin:var(--space-4) 0; padding:0; list-style:none; overflow:hidden; border:1px solid var(--border); border-radius:var(--r-lg); background:var(--border); }
  .pipeline li { display:grid; align-content:start; gap:.3rem; padding:var(--space-3); background:var(--surface); min-width:0; }
  .pipeline a { display:grid; gap:.1rem; color:inherit; text-decoration:none; }
  .pipeline a:hover span,.pipeline a:focus-visible span { color:var(--accent); text-decoration:underline; }
  .pipeline strong { font-size:var(--text-xl); }
  .pipeline span { color:var(--text-2); font-size:var(--text-sm); font-weight:600; }
  .pipeline p { margin:0; color:var(--text-3); font-size:var(--text-xs); }
  .retention-list { display:grid; gap:1px; margin:0; padding:0; list-style:none; overflow:hidden; border:1px solid var(--border); border-radius:var(--r-lg); background:var(--border); }
  .retention-list li { display:flex; align-items:center; gap:var(--space-3); padding:var(--space-3); background:var(--surface); }
  .retention-count { flex:none; min-width:2.5rem; font-size:var(--text-lg); font-weight:650; text-align:right; }
  .retention-text { display:grid; gap:.1rem; flex:1; min-width:0; }
  .retention-text small { color:var(--text-3); font-size:var(--text-xs); }
  .state-chip { font-weight:600; }
  .meta span.state-expires_soon,.meta span.state-stale { background:var(--warn-soft); }
  /* UX-MEM-08 — one row per record in the file, its status beside it. */
  .import-class { width:100%; color:var(--text-2); font-size:var(--text-sm); }
  .import-records { width:100%; display:grid; gap:.35rem; max-height:22rem; overflow:auto; margin:0; padding:0; list-style:none; }
  .import-record { display:flex; align-items:flex-start; justify-content:space-between; gap:var(--space-3); padding:.45rem .6rem; border:1px solid var(--border); border-radius:var(--r-sm); background:var(--surface); }
  .import-record label { display:flex; align-items:flex-start; gap:.5rem; min-width:0; }
  .import-record.skipped .import-text { color:var(--text-3); }
  .import-text { overflow-wrap:anywhere; font-size:var(--text-sm); }
  .import-status { flex:none; padding:.15rem .45rem; border-radius:var(--r-pill); background:var(--sunken); color:var(--text-2); font-size:var(--text-2xs); }
  .import-status.status-similar { background:var(--warn-soft); }
  .import-batches { width:100%; margin-top:var(--space-3); }
  .import-batches h4 { margin:0 0 var(--space-2); font-size:var(--text-sm); }
  .import-batches ul { display:grid; gap:.35rem; margin:0; padding:0; list-style:none; }
  .import-batches li { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:var(--space-2); font-size:var(--text-sm); color:var(--text-2); }
  .muted { color:var(--text-3); font-size:var(--text-sm); }
  .filters { display:flex; flex-wrap:wrap; gap:var(--space-2); align-items:center; margin-bottom:var(--space-5); } .search { min-height:var(--control-min-h); border:1px solid var(--border-strong); border-radius:var(--r-sm); background:var(--surface); color:var(--text-1); } .search { display:flex; align-items:center; gap:.45rem; padding:0 .7rem; flex:1; min-width:15rem; } .search input { width:100%; border:0; outline:0; background:transparent; color:inherit; } .pinned-filter { display:flex; align-items:center; gap:.35rem; color:var(--text-2); font-size:var(--text-sm); }
  /* The library is a card like the posture controls above it, not a bare run of
     text. Without the enclosure its empty state ("No files yet.") sat directly
     on top of the memory filter row and read as a caption for the filters. */
  .library-section {
    margin-top: var(--space-5);
    padding: var(--card-pad-y) var(--card-pad-x);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--surface);
    box-shadow: var(--shadow-1);
  }
  .memory-section { margin-top:var(--space-5); } .section-head { align-items:center; margin-bottom:var(--space-3); flex-wrap:wrap; } .section-head span { color:var(--text-3); }
  /* The trailing control keeps its own width and drops to a line of its
     own rather than being squeezed: at 390px "Scan approved memories"
     wrapped into a three-line column beside its heading, and so did the
     observations count. A short count still sits inline. */
  .section-head > :last-child:not(:first-child) { flex:none; max-width:100%; } .memory-grid { display:grid; gap:var(--space-3); }
  .memory-card { padding:var(--space-4); border:1px solid var(--border); border-radius:var(--r-lg); background:var(--surface); } .memory-card.pinned { border-color:var(--accent-border); } .memory-card.pending { margin-bottom:var(--space-3); background:var(--warn-soft); } .memory-card h4 { font-size:var(--text-base); } .memory-title textarea { width:100%; }
  .pin-label { display:flex; align-items:center; gap:.25rem; color:var(--accent); font-size:var(--text-xs); } .meta { display:flex; flex-wrap:wrap; gap:.35rem; margin:.6rem 0; } .meta span { padding:.22rem .48rem; border-radius:var(--r-pill); background:var(--sunken); color:var(--text-2); font-size:var(--text-xs); } dl { display:grid; grid-template-columns:2fr 1fr 1fr; gap:var(--space-3); padding-block:var(--space-3); border-block:1px solid var(--border); } dl div { min-width:0; } dt { color:var(--text-3); font-size:var(--text-2xs); } dd { margin:.15rem 0 0; overflow-wrap:anywhere; font-size:var(--text-sm); } .card-actions { justify-content:flex-start; flex-wrap:wrap; margin-top:var(--space-3); } .danger { color:var(--danger); } details { margin-top:var(--space-3); color:var(--text-2); font-size:var(--text-sm); } details summary { cursor:pointer; color:var(--text-1); }
  /* MEM-04 — an observation reads as a memory card with one difference: a
     refused one is drawn in the warning tone the pending proposals already use,
     because both are "here is something Raiker did not act on by itself". */
  .section-head p.section-note { margin:.2rem 0 0; color:var(--text-3); font-size:var(--text-sm); max-width:52rem; }
  .memory-card.observation.refused { background:var(--warn-soft); border-color:var(--warn-border,var(--border-strong)); }
  .refused-label { display:flex; align-items:center; gap:.25rem; flex:none; color:var(--warn,var(--text-3)); font-size:var(--text-xs); }
  .refused-note,.gist-note { margin:.5rem 0 0; color:var(--text-2); font-size:var(--text-sm); }
  .gist-note { display:flex; align-items:baseline; gap:.4rem; }
  .gist-note :global(svg) { flex:none; align-self:center; color:var(--accent); }
  .empty { padding:var(--space-6); text-align:center; border:1px dashed var(--border-strong); border-radius:var(--r-lg); color:var(--text-2); } .empty h4 { color:var(--text-1); margin-top:var(--space-2); }
  .advanced { margin-top:var(--space-6); padding:var(--space-4); border:1px solid var(--border); border-radius:var(--r-lg); background:var(--surface); } .advanced summary { margin:0; list-style:none; } .advanced summary span { display:grid; gap:.2rem; } .advanced small { color:var(--text-2); font-weight:400; } .advanced-body { display:flex; align-items:center; flex-wrap:wrap; gap:var(--space-2); padding-top:var(--space-4); } .file-button input { position:absolute; width:1px; height:1px; opacity:0; } .import-review { width:100%; display:flex; align-items:center; flex-wrap:wrap; gap:var(--space-3); padding:var(--space-3); background:var(--sunken); border-radius:var(--r-md); } .import-notice { width:100%; margin:var(--space-2) 0 0; color:var(--text-2); font-size:var(--text-sm); }
  @media (max-width:45rem) {
    .pipeline ol { grid-template-columns:1fr; }
    .retention-list li { flex-wrap:wrap; }
    dl { grid-template-columns:1fr; }
    .page-intro,.control-card,.posture-card { flex-direction:column; }
    .posture-action { white-space:normal; }
    .backend-field { min-width:0; width:100%; }
  }
</style>
