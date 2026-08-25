<script lang="ts">
  import Icon from "../components/Icon.svelte";
  import PageState from "../components/PageState.svelte";
  import { api, ApiError } from "../api";
  import FileInspector from "../components/FileInspector.svelte";
  import type { CapabilityGate, MemoryControlView, MemoryHistoryEvent, MemoryProposal, MemoryRelationshipProposal, MemorySettingsView, ObservationsView, SourceExcerptView } from "../apiTypes";
  import { relativeTime } from "../format";
  import { memoryWritePosture } from "../memoryPosture";
  import GuideLink from "../components/GuideLink.svelte";
  import FileLibrary from "../components/FileLibrary.svelte";

  type MemoryImport = Array<Partial<MemoryControlView> & { text: string }>;
  let memories = $state<MemoryControlView[] | null>(null);
  let settings = $state<MemorySettingsView | null>(null);
  let proposals = $state<MemoryProposal[]>([]);
  let relationshipProposals = $state<MemoryRelationshipProposal[]>([]);
  let loadError = $state<string | null>(null);
  let actionError = $state<string | null>(null);
  let busy = $state(false);
  let query = $state("");
  let statusFilter = $state("all");
  let scopeFilter = $state("all");
  let sensitivityFilter = $state("all");
  let pinnedOnly = $state(false);
  let sort = $state("recently-approved");
  let editingId = $state<string | null>(null);
  let editDraft = $state("");
  let importPreview = $state<MemoryImport | null>(null);
  let importFileName = $state("");
  let proposalEditingId = $state<string | null>(null);
  let proposalDraft = $state("");
  let historyById = $state<Record<string, MemoryHistoryEvent[]>>({});

  // MEM-04 — what the runtime captured while it worked. Loaded beside the
  // memories rather than behind a tab click, because the summary counters at
  // the top of this page are only honest if this half is known: "0 observations
  // captured" and "everything was refused on sensitivity" are different facts
  // and used to be indistinguishable.
  let observations = $state<ObservationsView | null>(null);
  let observationFilter = $state("all");

  // BUG-71 — the two facts that decide whether this page may promise proposals
  // at all. Read alongside the memories so the promise and the gate can never
  // disagree; a failed read says so rather than assuming the happy answer.
  let gates = $state<CapabilityGate[] | null>(null);
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
  // Three states, not two. The card used to have a sentence for "the fallback"
  // and a sentence for "a semantic space", and the second one claimed a recall
  // the runtime does not perform yet: the stored vectors are semantic, and the
  // question is not embedded into them, so matching is still by words. Saying
  // "matches meaning" there would be the same defect MEM-03 was raised to
  // remove, one layer further in.
  const recall = $derived(
    !retrieval.semantic
      ? "lexical"
      : retrieval.query_embeddable
        ? "semantic"
        : "stored_only",
  );

  async function load() {
    loadError = null;
    try {
      [memories, settings] = await Promise.all([api.memories(), api.memorySettings()]);
      try { proposals = await api.memoryProposals(); } catch { proposals = []; }
      try { relationshipProposals = await api.memoryRelationshipProposals(); } catch { relationshipProposals = []; }
      try { gates = await api.capabilityGates(); } catch { gates = null; }
      // A failed read is null, never an empty list: "capture is not reporting"
      // must not render as "capture found nothing".
      try { observations = await api.observations(); } catch { observations = null; }
    }
    catch (e) { memories = null; settings = null; loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable"; }
  }
  async function toggleIncognito() {
    if (!settings || busy) return;
    busy = true; actionError = null;
    try { await api.setMemoryIncognito(!settings.incognito); await load(); }
    catch (e) { actionError = e instanceof ApiError ? `Could not update memory use (${e.status}).` : "Could not update memory use."; }
    finally { busy = false; }
  }
  // MEM-03 — recall searches exactly one embedding space. Reloading rather than
  // patching the local object is deliberate: the server decides what "auto"
  // resolved to, and showing a guess would put the page back in the business of
  // claiming a backend it did not confirm.
  async function chooseEmbeddingBackend(backend: string) {
    if (!settings || busy) return;
    busy = true; actionError = null;
    try { await api.setMemoryEmbeddingBackend(backend); await load(); }
    catch (e) { actionError = e instanceof ApiError ? `Could not change the recall backend (${e.status}).` : "Could not change the recall backend."; }
    finally { busy = false; }
  }
  // MEM-10 — the select above can only offer spaces this workspace already
  // holds vectors in, which on a default install is the lexical fallback and
  // nothing else. This is how the first semantic space comes to exist: one
  // governed run that sends each approved memory to the named embedding model.
  // The count and the destination are both stated before the owner confirms,
  // because the text really does leave the machine.
  let indexProvider = $state("");
  let indexResult = $state<string | null>(null);
  const indexTarget = $derived(
    (settings?.embedding_providers ?? []).find((p) => p.space === indexProvider) ?? null,
  );
  async function buildEmbeddingIndex() {
    if (!indexTarget || busy) return;
    const waiting = settings?.unindexed_memories ?? 0;
    const where = indexTarget.local_only ? "on this machine" : `to ${indexTarget.provider}`;
    if (!window.confirm(`Send the text of ${waiting} approved ${waiting === 1 ? "memory" : "memories"} ${where} to be embedded as ${indexTarget.model}? Memories marked secret-like or credential-like are never sent.`)) return;
    busy = true; actionError = null; indexResult = null;
    try {
      const result = await api.buildMemoryEmbeddingIndex(indexTarget.provider, indexTarget.model);
      indexResult = `Embedded ${result.indexed_count} into ${result.embedding_model}.`;
      await load();
    } catch (e) {
      actionError = e instanceof ApiError ? `Could not build the index (${e.status}).` : "Could not build the index.";
    } finally { busy = false; }
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
    if (!window.confirm("Forget this memory? Raiker will stop using it in future work. Existing responses and required audit records will not be rewritten.")) return;
    try { await api.forgetMemory(m.memory_id); await load(); }
    catch { actionError = "Could not forget this memory."; }
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
    const file = (event.currentTarget as HTMLInputElement).files?.[0];
    if (!file) return;
    try {
      const parsed = JSON.parse(await file.text()) as unknown;
      const values = Array.isArray(parsed) ? parsed : typeof parsed === "object" && parsed !== null && Array.isArray((parsed as { memories?: unknown }).memories) ? (parsed as { memories: unknown[] }).memories : [];
      if (!values.every((value) => typeof value === "object" && value !== null && typeof (value as { text?: unknown }).text === "string")) throw new Error("schema");
      importPreview = values as MemoryImport; importFileName = file.name; actionError = null;
    } catch { importPreview = null; actionError = "This file is not a valid Raiker memory export."; }
  }
  async function applyImport() {
    if (!importPreview) return;
    try { await api.importMemories(importPreview); importPreview = null; importFileName = ""; await load(); }
    catch { actionError = "Could not import memories."; }
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

  const approved = $derived((memories ?? []).filter((m) => m.approval_state === "approved"));
  const pending = $derived(proposals);
  const expired = $derived((memories ?? []).filter((m) => m.expires_at && new Date(m.expires_at) <= new Date()));
  const scopes = $derived([...new Set((memories ?? []).map((m) => m.scope))]);
  const sensitivities = $derived([...new Set((memories ?? []).map((m) => m.sensitivity))]);
  const filtered = $derived(
    approved.filter((m) => {
      const matchStatus = statusFilter === "all" || m.approval_state === statusFilter || (statusFilter === "expired" && !!m.expires_at && new Date(m.expires_at) <= new Date());
      return matchStatus && (scopeFilter === "all" || m.scope === scopeFilter) && (sensitivityFilter === "all" || m.sensitivity === sensitivityFilter) && (!pinnedOnly || m.pinned) && `${m.text} ${provenanceLabel(m)} ${m.tags.join(" ")}`.toLowerCase().includes(query.toLowerCase());
    }).sort((a, b) => sort === "review-date" ? (a.expires_at ?? "9999").localeCompare(b.expires_at ?? "9999") : b.created_at.localeCompare(a.created_at)),
  );
  $effect(() => { void load(); });
</script>

<header class="page-intro"><GuideLink route="memory" /><button class="btn btn-ghost btn-sm" type="button" onclick={load}><Icon name="refresh" size={15} /> Refresh</button></header>

<section class="posture-card posture-{posture.kind}" role="note" aria-label="Memory permission posture">
  <Icon name={posture.kind === "proposes" ? "check" : "info"} size={16} />
  <p>{posture.headline}</p>
  {#if posture.action}<a class="posture-action" href="#/capabilities">{posture.action} →</a>{/if}
</section>

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
        <Icon name={recall === "semantic" ? "check" : "info"} size={14} />
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
      <!-- MEM-10 — the select opposite can only offer spaces that already hold
           vectors, so on a default install it offers the fallback and nothing
           else. This row is the way out of that: it builds one. -->
      {#if recall !== "semantic" && settings.unindexed_memories > 0 && (settings.embedding_providers ?? []).length}
        <div class="index-row">
          <label class="index-field">
            <span class="sr-only">Embedding model to build with</span>
            <select class="select" aria-label="Embedding model" bind:value={indexProvider} disabled={busy}>
              <option value="">Build a meaning-based index…</option>
              {#each settings.embedding_providers as provider (provider.space)}
                <option value={provider.space}>{provider.model} · {provider.local_only ? "on this machine" : provider.provider}</option>
              {/each}
            </select>
          </label>
          <button
            class="btn btn-sm"
            type="button"
            disabled={busy || !indexTarget || !settings.unindexed_memories}
            onclick={() => void buildEmbeddingIndex()}
          >Embed {settings.unindexed_memories}</button>
        </div>
        {#if indexResult}<p class="posture-line" data-semantic="true"><Icon name="check" size={14} /><span>{indexResult}</span></p>{/if}
      {/if}
    </div>
    <label class="backend-field">
      <span class="sr-only">Recall backend</span>
      <select
        class="select"
        aria-label="Recall backend"
        value={settings.embedding_backend ?? "auto"}
        disabled={busy}
        onchange={(event) => void chooseEmbeddingBackend(event.currentTarget.value)}
      >
        <option value="auto">Automatic</option>
        {#each settings.spaces ?? [] as space (space.model)}
          <option value={space.model}>{space.model} · {space.dimensions}d</option>
        {/each}
      </select>
    </label>
  </section>
{/if}

{#if actionError}<p class="notice notice-danger" role="alert">{actionError}</p>{/if}
{#if loadError}<PageState state="error" title="Couldn't load memories" detail={loadError} />
{:else if memories === null}<PageState state="loading" title="Loading memories…" />
{:else}
  <section class="summary" aria-label="Memory summary">
    <div><strong>{approved.length}</strong><span>Approved</span></div><div><strong>{pending.length + relationshipProposals.length}</strong><span>Pending review</span></div><div><strong>{approved.filter((m) => m.pinned).length}</strong><span>Pinned</span></div><div><strong>{expired.length}</strong><span>Withheld or expired</span></div>
  </section>

  <!-- The document library is deliberately its own section, above the atomic
       records and outside their filters: an uploaded workbook and an approved
       remembered sentence are different kinds of thing, and mixing them into
       one list makes it impossible to tell which one answered a question. -->
  <section class="memory-section library-section" aria-label="Memory document library">
    <FileLibrary
      scope="memory"
      heading="Document library"
      description="Files kept under Raiker's managed memory storage. Uploaded content is data, never instructions."
    />
  </section>

  <section class="filters" aria-label="Filter memories">
    <label class="search"><Icon name="search" size={16} /><input bind:value={query} aria-label="Search memories" placeholder="Search memories…" /></label>
    <select bind:value={statusFilter} aria-label="Memory status"><option value="all">All statuses</option><option value="approved">Approved</option><option value="expired">Expired</option></select>
    <select bind:value={scopeFilter} aria-label="Memory scope"><option value="all">All scopes</option>{#each scopes as scope}<option value={scope}>{scope}</option>{/each}</select>
    <select bind:value={sensitivityFilter} aria-label="Memory sensitivity"><option value="all">All sensitivities</option>{#each sensitivities as sensitivity}<option value={sensitivity}>{sensitivity}</option>{/each}</select>
    <select bind:value={sort} aria-label="Sort memories"><option value="recently-approved">Recently approved</option><option value="review-date">Review date</option></select>
    <label class="pinned-filter"><input type="checkbox" bind:checked={pinnedOnly} /> Pinned only</label>
  </section>

  {#if pending.length}
    <section class="memory-section"><div class="section-head"><h3>Pending review</h3><span>{pending.length}</span></div>
      {#each pending as proposal (proposal.candidate_id)}<article class="memory-card pending">
        {#if proposalEditingId === proposal.candidate_id}<textarea rows="3" bind:value={proposalDraft} aria-label="Edit proposed memory"></textarea>{:else}<h4>{proposal.text}</h4>{/if}
        <p>Proposed from event: {proposal.source_event_id}</p>
        <div class="meta"><span>{proposal.scope}</span><span>{proposal.sensitivity} sensitivity</span><span>{Math.round(proposal.confidence * 100)}% confidence</span></div>
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
          <div class="meta"><span>{proposal.subject_type} → {proposal.object_type}</span><span>{Math.round(proposal.confidence * 100)}% confidence</span><span>{proposal.extractor_version}</span></div>
          <p>Evidence: {proposal.evidence_memory_id}. Approving adds the reviewed edge; denying leaves the evidence memory unchanged.</p>
          <div class="card-actions"><button class="btn btn-primary btn-sm" onclick={() => void decideRelationship(proposal, "approved")}>Approve relationship</button><button class="btn btn-ghost btn-sm danger" onclick={() => void decideRelationship(proposal, "denied")}>Reject relationship</button></div>
        </article>
      {/each}
    {:else}
      <p class="muted">No relationship proposals are waiting for review.</p>
    {/if}
  </section>

  <section class="memory-section"><div class="section-head"><h3>Approved memories</h3><span>{filtered.length}</span></div>
    <!-- The posture card at the top of the page already states *why* there are
         none. Repeating its sentence here put the same line on screen twice;
         the empty state keeps the action, which is the half that is not
         already said. -->
    {#if approved.length === 0}<div class="empty"><Icon name="spark" size={24} /><h4>No approved memories yet</h4><a href={posture.action ? "#/capabilities" : "#/approvals"}>{posture.action ?? "Learn how governed review works"}</a></div>
    {:else if filtered.length === 0}<div class="empty"><h4>No memories match these filters</h4><p>Clear or change the filters to see approved memories.</p></div>
    {:else}<div class="memory-grid">{#each filtered as m (m.memory_id)}<article class="memory-card" class:pinned={m.pinned}>
      <div class="memory-title">{#if editingId === m.memory_id}<textarea rows="3" bind:value={editDraft} aria-label="Memory text"></textarea>{:else}<h4>{m.text}</h4>{/if}{#if m.pinned}<span class="pin-label"><Icon name="check" size={12} /> Pinned</span>{/if}</div>
      <div class="meta"><span>Approved</span><span>{m.scope} scope</span><span>{m.sensitivity} sensitivity</span></div>
      <dl><div><dt>Source</dt><dd>{provenanceLabel(m)}</dd></div><div><dt>Approved</dt><dd>{relativeTime(m.created_at)}</dd></div><div><dt>Review or expiry</dt><dd>{m.expires_at ? relativeTime(m.expires_at) : "No date set"}</dd></div></dl>
      <div class="card-actions">{#if editingId === m.memory_id}<button class="btn btn-primary btn-sm" aria-label="Save memory" onclick={() => void saveEdit(m)}>Save</button><button class="btn btn-ghost btn-sm" onclick={() => editingId = null}>Cancel</button>{:else}<button class="btn btn-ghost btn-sm" aria-label={`View the source of “${m.text.slice(0, 40)}”`} onclick={() => void viewSource(m)}>View source</button><button class="btn btn-ghost btn-sm" aria-label="Edit memory" onclick={() => { editingId = m.memory_id; editDraft = m.text; }}>Edit</button><button class="btn btn-ghost btn-sm" onclick={() => void changeScope(m)}>Edit scope</button><button class="btn btn-ghost btn-sm" onclick={() => void reviewExpiry(m)}>Review expiry</button><button class="btn btn-ghost btn-sm" aria-label={m.pinned ? "Unpin memory" : "Pin memory"} onclick={() => void togglePin(m)}>{m.pinned ? "Unpin" : "Pin"}</button><button class="btn btn-ghost btn-sm" onclick={() => void viewHistory(m)}>View history</button><button class="btn btn-ghost btn-sm danger" aria-label="Forget memory" onclick={() => void forget(m)}>Forget</button>{/if}</div>
      <details><summary>Advanced metadata and deletion</summary><p>Type: {m.memory_type} · Retention: {m.retention} · Confidence: {m.confidence.toFixed(2)} · Trust: {m.trust_score.toFixed(2)}</p><p>Last used: {m.last_used_at ? relativeTime(m.last_used_at) : "Never recalled"}. Source record details: {Object.keys(m.provenance).length ? Object.keys(m.provenance).join(", ") : "Source metadata unavailable"}</p><button class="btn btn-ghost btn-sm danger" onclick={() => void purge(m)}>Delete permanently</button></details>
      {#if historyById[m.memory_id]}<ol class="history" aria-label="Memory history">{#each historyById[m.memory_id] as event}<li><strong>{event.action.replaceAll("_", " ")}</strong> <span>{relativeTime(event.created_at)}</span></li>{/each}</ol>{/if}
    </article>{/each}</div>{/if}
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
        <Icon name="info" size={14} />
        <span>{dueForExpiry.length} past their retention class.</span>
        <button class="btn btn-sm" type="button" disabled={busy} onclick={() => void sweepExpired()}>Remove</button>
      </div>
    {:else if sweepResult}
      <div class="due-row" role="status"><Icon name="check" size={14} /><span>{sweepResult}</span></div>
    {/if}
    {#if observations === null}
      <div class="empty"><Icon name="info" size={24} /><h4>Observation capture is not reporting</h4><p>The runtime could not be asked what it captured. This is not the same as having captured nothing.</p></div>
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
        <div class="empty"><Icon name="spark" size={24} /><h4>No observations yet</h4><p>Raiker records one observation each time a governed tool returns material. Run a turn that reads a file or searches the workspace and it will appear here.</p></div>
      {:else if observationRows.length === 0}
        <div class="empty"><h4>No observations match this filter</h4><p>Choose a different kind to see what was captured.</p></div>
      {:else}
        <div class="memory-grid">
          {#each observationRows as o (o.observation_id)}
            <article class="memory-card observation" class:refused={o.capture_status === "skipped"}>
              <div class="memory-title"><h4>{o.summary}</h4>{#if o.capture_status === "skipped"}<span class="refused-label"><Icon name="info" size={12} /> Not captured</span>{/if}</div>
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
                <p class="gist-note"><Icon name="spark" size={14} /> Gist proposed and pending review: “{o.gist_summary}”. It becomes durable memory only through the same approval every other memory needs.</p>
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

  <details class="advanced"><summary><span><strong>Advanced memory management</strong><small>Import or export governed memory records.</small></span><Icon name="chevron-down" size={16} /></summary><div class="advanced-body"><button class="btn btn-ghost" onclick={() => void exportMemories()}>Export memories</button><label class="btn btn-ghost file-button">Review import<input type="file" accept="application/json,.json" onchange={(e) => void reviewImport(e)} /></label>{#if importPreview}<div class="import-review" role="status"><strong>{importFileName}</strong><span>{importPreview.length} valid record{importPreview.length === 1 ? "" : "s"} ready for governed import.</span><button class="btn btn-primary btn-sm" onclick={() => void applyImport()}>Import reviewed records</button></div>{/if}</div></details>
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
  .posture-line { display:flex; align-items:baseline; gap:.4rem; margin-top:var(--space-2) !important; font-size:.82rem; }
  .posture-line :global(svg) { flex:none; align-self:center; color:var(--warn,var(--text-3)); }
  .posture-line[data-semantic="true"] :global(svg) { color:var(--ok,var(--text-3)); }
  .backend-field { flex:none; min-width:14rem; }
  /* A secondary clause under the lead, not a second lead. */
  .due-row { display:flex; align-items:center; gap:var(--space-2); margin-bottom:var(--space-3); font-size:.82rem; color:var(--text-2); }
  .due-row :global(svg) { flex:none; color:var(--warn,var(--text-3)); }
  .due-row[role="status"] :global(svg) { color:var(--ok,var(--text-3)); }
  .index-row { display:flex; gap:var(--space-2); align-items:center; margin-top:var(--space-2); flex-wrap:wrap; }
  .index-field { flex:1 1 14rem; min-width:0; }
  /* BUG-71 — the posture strip states what this page can actually promise. It
     sits above everything else because it changes the meaning of the counts
     below it: "0 Pending review" reads very differently when nothing is able
     to propose. */
  .posture-card { display:flex; align-items:flex-start; gap:var(--space-2); padding:var(--space-3) var(--space-4); margin-bottom:var(--space-4); border:1px solid var(--border); border-radius:var(--r-lg); background:var(--surface-2); }
  .posture-card p { margin:0; color:var(--text-2); flex:1; }
  .posture-card :global(svg) { flex:none; margin-top:.1rem; color:var(--text-3); }
  .posture-proposes { border-color:var(--ok-border,var(--border)); }
  .posture-proposes :global(svg) { color:var(--ok,var(--text-3)); }
  .posture-denied :global(svg),.posture-unknown :global(svg) { color:var(--warn,var(--text-3)); }
  .posture-action { flex:none; white-space:nowrap; font-weight:600; }
  .switch { min-width:76px; min-height:44px; display:flex; align-items:center; gap:.45rem; border:1px solid var(--border-strong); border-radius:var(--r-pill); padding:.25rem .55rem .25rem .3rem; background:var(--sunken); color:var(--text-2); cursor:pointer; } .switch span { width:1.65rem; height:1.65rem; border-radius:50%; background:var(--text-3); } .switch.on { background:var(--accent-soft); color:var(--accent); border-color:var(--accent-border); } .switch.on span { background:var(--accent); }
  .summary { display:grid; grid-template-columns:repeat(4,1fr); gap:1px; margin:var(--space-4) 0; overflow:hidden; border:1px solid var(--border); border-radius:var(--r-lg); background:var(--border); } .summary div { display:grid; gap:.15rem; padding:var(--space-3); background:var(--surface); } .summary strong { font-size:1.2rem; } .summary span { color:var(--text-3); font-size:.75rem; }
  .filters { display:flex; flex-wrap:wrap; gap:var(--space-2); align-items:center; margin-bottom:var(--space-5); } .search { min-height:var(--control-min-h); border:1px solid var(--border-strong); border-radius:var(--r-sm); background:var(--surface); color:var(--text-1); } .search { display:flex; align-items:center; gap:.45rem; padding:0 .7rem; flex:1; min-width:15rem; } .search input { width:100%; border:0; outline:0; background:transparent; color:inherit; } .pinned-filter { display:flex; align-items:center; gap:.35rem; color:var(--text-2); font-size:.82rem; }
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
  .memory-section { margin-top:var(--space-5); } .section-head { align-items:center; margin-bottom:var(--space-3); } .section-head span { color:var(--text-3); } .memory-grid { display:grid; gap:var(--space-3); }
  .memory-card { padding:var(--space-4); border:1px solid var(--border); border-radius:var(--r-lg); background:var(--surface); } .memory-card.pinned { border-color:var(--accent-border); } .memory-card.pending { margin-bottom:var(--space-3); background:var(--warning-soft); } .memory-card h4 { font-size:1rem; } .memory-title textarea { width:100%; }
  .pin-label { display:flex; align-items:center; gap:.25rem; color:var(--accent); font-size:.72rem; } .meta { display:flex; flex-wrap:wrap; gap:.35rem; margin:.6rem 0; } .meta span { padding:.22rem .48rem; border-radius:var(--r-pill); background:var(--sunken); color:var(--text-2); font-size:.72rem; } dl { display:grid; grid-template-columns:2fr 1fr 1fr; gap:var(--space-3); padding-block:var(--space-3); border-block:1px solid var(--border); } dl div { min-width:0; } dt { color:var(--text-3); font-size:.7rem; } dd { margin:.15rem 0 0; overflow-wrap:anywhere; font-size:.82rem; } .card-actions { justify-content:flex-start; margin-top:var(--space-3); } .danger { color:var(--danger); } details { margin-top:var(--space-3); color:var(--text-2); font-size:.78rem; } details summary { cursor:pointer; color:var(--text-1); }
  /* MEM-04 — an observation reads as a memory card with one difference: a
     refused one is drawn in the warning tone the pending proposals already use,
     because both are "here is something Raiker did not act on by itself". */
  .section-head p.section-note { margin:.2rem 0 0; color:var(--text-3); font-size:.8rem; max-width:52rem; }
  .memory-card.observation.refused { background:var(--warning-soft); border-color:var(--warn-border,var(--border-strong)); }
  .refused-label { display:flex; align-items:center; gap:.25rem; flex:none; color:var(--warn,var(--text-3)); font-size:.72rem; }
  .refused-note,.gist-note { margin:.5rem 0 0; color:var(--text-2); font-size:.8rem; }
  .gist-note { display:flex; align-items:baseline; gap:.4rem; }
  .gist-note :global(svg) { flex:none; align-self:center; color:var(--accent); }
  .empty { padding:var(--space-7); text-align:center; border:1px dashed var(--border-strong); border-radius:var(--r-lg); color:var(--text-2); } .empty h4 { color:var(--text-1); margin-top:var(--space-2); }
  .advanced { margin-top:var(--space-6); padding:var(--space-4); border:1px solid var(--border); border-radius:var(--r-lg); background:var(--surface); } .advanced summary { margin:0; list-style:none; } .advanced summary span { display:grid; gap:.2rem; } .advanced small { color:var(--text-2); font-weight:400; } .advanced-body { display:flex; align-items:center; flex-wrap:wrap; gap:var(--space-2); padding-top:var(--space-4); } .file-button input { position:absolute; width:1px; height:1px; opacity:0; } .import-review { width:100%; display:flex; align-items:center; gap:var(--space-3); padding:var(--space-3); background:var(--sunken); border-radius:var(--r-md); }
  @media (max-width:45rem) {
    .summary { grid-template-columns:repeat(2,1fr); }
    dl { grid-template-columns:1fr; }
    .page-intro,.control-card,.posture-card { flex-direction:column; }
    .posture-action { white-space:normal; }
    .backend-field { min-width:0; width:100%; }
  }
</style>
