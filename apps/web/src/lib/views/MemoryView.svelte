<script lang="ts">
  import Icon from "../components/Icon.svelte";
  import PageState from "../components/PageState.svelte";
  import { api, ApiError } from "../api";
  import FileInspector from "../components/FileInspector.svelte";
  import type { MemoryControlView, MemoryHistoryEvent, MemoryProposal, MemorySettingsView, SourceExcerptView } from "../apiTypes";
  import { relativeTime } from "../format";

  type MemoryImport = Array<Partial<MemoryControlView> & { text: string }>;
  let memories = $state<MemoryControlView[] | null>(null);
  let settings = $state<MemorySettingsView | null>(null);
  let proposals = $state<MemoryProposal[]>([]);
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

  async function load() {
    loadError = null;
    try {
      [memories, settings] = await Promise.all([api.memories(), api.memorySettings()]);
      try { proposals = await api.memoryProposals(); } catch { proposals = []; }
    }
    catch (e) { memories = null; settings = null; loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable"; }
  }
  async function toggleIncognito() {
    if (!settings || busy) return;
    busy = true; actionError = null;
    try { const incognito = !settings.incognito; await api.setMemoryIncognito(incognito); settings = { incognito }; }
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

<header class="page-intro"><div><h2>Memory</h2><p>Review and control the approved information Raiker can reuse.</p></div><button class="btn btn-ghost btn-sm" type="button" onclick={load}><Icon name="refresh" size={15} /> Refresh</button></header>

{#if settings}
  <section class="control-card">
    <div><h3>Incognito session</h3><p>Do not use approved memories in new conversations and tasks. Stored memories are not deleted.</p></div>
    <button class="switch" class:on={settings.incognito} role="switch" aria-checked={settings.incognito} aria-label="Incognito session" disabled={busy} onclick={() => void toggleIncognito()}><span></span><b>{settings.incognito ? "On" : "Off"}</b></button>
  </section>
{/if}

{#if actionError}<p class="notice notice-danger" role="alert">{actionError}</p>{/if}
{#if loadError}<PageState state="error" title="Couldn't load memories" detail={loadError} />
{:else if memories === null}<PageState state="loading" title="Loading memories…" />
{:else}
  <section class="summary" aria-label="Memory summary">
    <div><strong>{approved.length}</strong><span>Approved</span></div><div><strong>{pending.length}</strong><span>Pending review</span></div><div><strong>{approved.filter((m) => m.pinned).length}</strong><span>Pinned</span></div><div><strong>{expired.length}</strong><span>Withheld or expired</span></div>
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

  <section class="memory-section"><div class="section-head"><h3>Approved memories</h3><span>{filtered.length}</span></div>
    {#if approved.length === 0}<div class="empty"><Icon name="spark" size={24} /><h4>No approved memories yet</h4><p>When Raiker identifies a useful preference or durable fact, it will propose it for review. Nothing becomes reusable memory until it is approved.</p><a href="#/approvals">Learn how governed review works</a></div>
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
  .page-intro,.control-card,.section-head,.memory-title,.card-actions,.advanced summary { display:flex; align-items:flex-start; justify-content:space-between; gap:var(--space-3); } .page-intro { margin-bottom:var(--space-4); } .page-intro h2,.control-card h3,.section-head h3,.memory-card h4,.empty h4 { margin:0; } .page-intro p,.control-card p { margin:.25rem 0 0; color:var(--text-2); }
  .control-card { padding:var(--space-4); border:1px solid var(--border); border-radius:var(--r-lg); background:var(--surface); }
  .switch { min-width:76px; min-height:44px; display:flex; align-items:center; gap:.45rem; border:1px solid var(--border-strong); border-radius:var(--r-pill); padding:.25rem .55rem .25rem .3rem; background:var(--sunken); color:var(--text-2); cursor:pointer; } .switch span { width:1.65rem; height:1.65rem; border-radius:50%; background:var(--text-3); } .switch.on { background:var(--accent-soft); color:var(--accent); border-color:var(--accent-border); } .switch.on span { background:var(--accent); }
  .summary { display:grid; grid-template-columns:repeat(4,1fr); gap:1px; margin:var(--space-4) 0; overflow:hidden; border:1px solid var(--border); border-radius:var(--r-lg); background:var(--border); } .summary div { display:grid; gap:.15rem; padding:var(--space-3); background:var(--surface); } .summary strong { font-size:1.2rem; } .summary span { color:var(--text-3); font-size:.75rem; }
  .filters { display:flex; flex-wrap:wrap; gap:var(--space-2); align-items:center; margin-bottom:var(--space-5); } .filters select,.search { min-height:42px; border:1px solid var(--border); border-radius:var(--r-md); background:var(--surface); color:var(--text-1); } .filters select { padding:0 .65rem; } .search { display:flex; align-items:center; gap:.45rem; padding:0 .7rem; flex:1; min-width:15rem; } .search input { width:100%; border:0; outline:0; background:transparent; color:inherit; } .pinned-filter { display:flex; align-items:center; gap:.35rem; color:var(--text-2); font-size:.82rem; }
  .memory-section { margin-top:var(--space-5); } .section-head { align-items:center; margin-bottom:var(--space-3); } .section-head span { color:var(--text-3); } .memory-grid { display:grid; gap:var(--space-3); }
  .memory-card { padding:var(--space-4); border:1px solid var(--border); border-radius:var(--r-lg); background:var(--surface); } .memory-card.pinned { border-color:var(--accent-border); } .memory-card.pending { margin-bottom:var(--space-3); background:var(--warning-soft); } .memory-card h4 { font-size:1rem; } .memory-title textarea { width:100%; }
  .pin-label { display:flex; align-items:center; gap:.25rem; color:var(--accent); font-size:.72rem; } .meta { display:flex; flex-wrap:wrap; gap:.35rem; margin:.6rem 0; } .meta span { padding:.22rem .48rem; border-radius:var(--r-pill); background:var(--sunken); color:var(--text-2); font-size:.72rem; } dl { display:grid; grid-template-columns:2fr 1fr 1fr; gap:var(--space-3); padding-block:var(--space-3); border-block:1px solid var(--border); } dl div { min-width:0; } dt { color:var(--text-3); font-size:.7rem; } dd { margin:.15rem 0 0; overflow-wrap:anywhere; font-size:.82rem; } .card-actions { justify-content:flex-start; margin-top:var(--space-3); } .danger { color:var(--danger); } details { margin-top:var(--space-3); color:var(--text-2); font-size:.78rem; } details summary { cursor:pointer; color:var(--text-1); }
  .empty { padding:var(--space-7); text-align:center; border:1px dashed var(--border-strong); border-radius:var(--r-lg); color:var(--text-2); } .empty h4 { color:var(--text-1); margin-top:var(--space-2); }
  .advanced { margin-top:var(--space-6); padding:var(--space-4); border:1px solid var(--border); border-radius:var(--r-lg); background:var(--surface); } .advanced summary { margin:0; list-style:none; } .advanced summary span { display:grid; gap:.2rem; } .advanced small { color:var(--text-2); font-weight:400; } .advanced-body { display:flex; align-items:center; flex-wrap:wrap; gap:var(--space-2); padding-top:var(--space-4); } .file-button input { position:absolute; width:1px; height:1px; opacity:0; } .import-review { width:100%; display:flex; align-items:center; gap:var(--space-3); padding:var(--space-3); background:var(--sunken); border-radius:var(--r-md); }
  @media (max-width:45rem) { .summary { grid-template-columns:repeat(2,1fr); } dl { grid-template-columns:1fr; } .page-intro,.control-card { flex-direction:column; } }
</style>
