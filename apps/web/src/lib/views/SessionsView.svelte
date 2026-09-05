<script lang="ts">
  import Badge from "../components/Badge.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import PageState from "../components/PageState.svelte";
  import SessionMenu from "../components/SessionMenu.svelte";
  import { api, ApiError } from "../api";
  import type { ProjectView, SessionDetail, SessionSummary, TurnDetail } from "../apiTypes";
  import { responseBadge } from "../statusMaps";
  import { humanize, relativeTime, shortId } from "../format";
  import { conversationLink } from "../turnAnchor";

  // When a project is active (topbar switcher) the list is scoped to it.
  let { projectId = null, sessionId = null }: { projectId?: string | null; sessionId?: string | null } = $props();

  let sessions = $state<SessionSummary[] | null>(null);
  let loadError = $state<string | null>(null);

  let detail = $state<SessionDetail | null>(null);
  let detailError = $state<string | null>(null);

  let turnDetail = $state<TurnDetail | null>(null);
  let turnError = $state<string | null>(null);
  let openedRouteSessionId = $state<string | null | undefined>(undefined);

  // Conversation organisation: multi-select for bulk delete, plus a per-row
  // pin toggle. Pinned sessions surface first. These are organizing actions
  // only — they grant nothing and change no authority.
  let selected = $state<Set<string>>(new Set());
  let actionError = $state<string | null>(null);
  let deleting = $state(false);

  // Conversation organisation remainder: per-session tags. Tags are organizing
  // labels only — they grant nothing. The view renders chips, lets the user
  // add/remove a tag inline, and filter the list by a tag substring.
  let tagDraft = $state<Record<string, string>>({});
  let tagFilter = $state("");

  // Archived sessions stay out of the default list; the toggle re-reads the
  // owner-scoped list with include_archived. Archive is reversible and never
  // deletes transcripts, events, checkpoints, or permissions.
  let showArchived = $state(false);

  // Project context (backlog item 1): a chat can be moved into a project or out
  // of every project. The project is an organizing scope — the move grants
  // nothing; it only changes the bounded context (instructions, shared
  // attachments, opt-in project memory) the chat receives on its next turn.
  let projects = $state<ProjectView[]>([]);

  // Pinned sessions first, then most-recently-updated. The sort is display-only
  // — the backend list order is unchanged. A non-empty tag filter further
  // narrows the list to sessions carrying a tag that contains the substring.
  const ordered = $derived(
    sessions === null
      ? null
      : [...sessions]
          .filter((s) => {
            const q = tagFilter.trim().toLowerCase();
            if (q === "") return true;
            return s.tags.some((t) => t.toLowerCase().includes(q));
          })
          .sort((a, b) => {
            if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
            return b.updated_at.localeCompare(a.updated_at);
          }),
  );

  function toggleSelected(id: string) {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    selected = next;
  }

  // Select-all toggles every visible (filtered+ordered) session. If all are
  // already selected it clears; otherwise it selects all.
  function toggleSelectAll() {
    if (ordered === null) return;
    const allIds = ordered.map((s) => s.session_id);
    const allSelected = allIds.every((id) => selected.has(id));
    const next = new Set(selected);
    if (allSelected) {
      for (const id of allIds) next.delete(id);
    } else {
      for (const id of allIds) next.add(id);
    }
    selected = next;
  }

  const allVisibleSelected = $derived(
    ordered !== null && ordered.length > 0 && ordered.every((s) => selected.has(s.session_id)),
  );

  // A selection must never outlive its visibility: when the tag filter or the
  // archived scope hides a session, it silently leaving via a later bulk
  // delete would be a trap. Prune hidden ids whenever the visible set changes.
  $effect(() => {
    if (ordered === null) return;
    const visible = new Set(ordered.map((s) => s.session_id));
    const kept = [...selected].filter((id) => visible.has(id));
    if (kept.length !== selected.size) selected = new Set(kept);
  });

  async function togglePin(s: SessionSummary) {
    actionError = null;
    try {
      await api.setSessionPinned(s.session_id, !s.pinned);
      await load();
    } catch (e) {
      actionError =
        e instanceof ApiError ? `Could not update pin (${e.status}).` : "Could not update pin.";
    }
  }

  async function renameSession(s: SessionSummary, title: string) {
    const next = title.trim();
    if (next === "" || next === s.title) return;
    actionError = null;
    try {
      await api.renameSession(s.session_id, next);
      await load();
    } catch (e) {
      actionError =
        e instanceof ApiError ? `Could not rename (${e.status}).` : "Could not rename.";
    }
  }

  async function toggleArchived(s: SessionSummary) {
    actionError = null;
    try {
      if (s.archived) await api.unarchiveSession(s.session_id);
      else await api.archiveSession(s.session_id);
      await load();
    } catch (e) {
      actionError =
        e instanceof ApiError ? `Could not update archive state (${e.status}).` : "Could not update archive state.";
    }
  }

  // Add or remove a single tag by replacing the session's full tag set. The
  // server normalizes and dedupes, so we send the desired next set and let
  // the backend be the source of truth.
  async function addTag(s: SessionSummary) {
    const draft = (tagDraft[s.session_id] ?? "").trim();
    if (draft === "") return;
    actionError = null;
    const next = [...s.tags, draft];
    try {
      await api.setSessionTags(s.session_id, next);
      tagDraft[s.session_id] = "";
      await load();
    } catch (e) {
      actionError =
        e instanceof ApiError ? `Could not add tag (${e.status}).` : "Could not add tag.";
    }
  }

  async function removeTag(s: SessionSummary, tag: string) {
    actionError = null;
    const next = s.tags.filter((t) => t !== tag);
    try {
      await api.setSessionTags(s.session_id, next);
      await load();
    } catch (e) {
      actionError =
        e instanceof ApiError ? `Could not remove tag (${e.status}).` : "Could not remove tag.";
    }
  }

  // Move a chat into a project, or out of every project (empty selection).
  // Moving out removes the project's bounded context from the next turn.
  async function moveToProject(s: SessionSummary, value: string) {
    const next = value === "" ? null : value;
    if (next === s.project_id) return;
    actionError = null;
    try {
      await api.setSessionProject(s.session_id, next);
      await load();
    } catch (e) {
      actionError =
        e instanceof ApiError ? `Could not move chat (${e.status}).` : "Could not move chat.";
    }
  }

  async function deleteOne(id: string) {
    if (!window.confirm("Delete this conversation permanently? Its turns and governed events will be removed.")) return;
    actionError = null;
    deleting = true;
    try {
      await api.deleteSession(id);
      if (detail?.session.session_id === id) detail = null;
      selected = new Set([...selected].filter((x) => x !== id));
      await load();
    } catch (e) {
      actionError =
        e instanceof ApiError ? `Could not delete (${e.status}).` : "Could not delete.";
    } finally {
      deleting = false;
    }
  }

  async function deleteSelected() {
    if (selected.size === 0) return;
    if (
      !window.confirm(
        `Delete ${selected.size} conversation${selected.size === 1 ? "" : "s"} permanently? Their turns and governed events will be removed.`,
      )
    )
      return;
    actionError = null;
    deleting = true;
    try {
      await api.deleteSessions([...selected]);
      if (detail && selected.has(detail.session.session_id)) detail = null;
      selected = new Set();
      await load();
    } catch (e) {
      actionError = e instanceof ApiError ? `Could not delete (${e.status}).` : "Could not delete.";
    } finally {
      deleting = false;
    }
  }

  async function load() {
    loadError = null;
    try {
      // The project list feeds the per-row move control. A failure here must
      // not break the session list, so it degrades to "no projects to move to".
      try {
        projects = (await api.projects()).projects.filter((p) => !p.is_archived);
      } catch {
        projects = [];
      }
      sessions = await api.sessions(projectId ?? undefined, showArchived);
      // Drop any selection that no longer exists after a refresh.
      const ids = new Set((sessions ?? []).map((s) => s.session_id));
      selected = new Set([...selected].filter((id) => ids.has(id)));
    } catch (e) {
      sessions = null;
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }

  async function openSession(id: string) {
    detailError = null;
    turnDetail = null;
    turnError = null;
    try {
      detail = await api.session(id);
    } catch (e) {
      detail = null;
      detailError = e instanceof ApiError ? `Could not load session (${e.status}).` : "Could not load session.";
    }
  }

  async function openTurn(id: string) {
    turnError = null;
    try {
      turnDetail = await api.turn(id);
    } catch (e) {
      turnDetail = null;
      turnError = e instanceof ApiError ? `Could not load turn (${e.status}).` : "Could not load turn.";
    }
  }

  // Load on mount and again whenever the active project or archive scope changes.
  $effect(() => {
    void projectId;
    void showArchived;
    void load();
  });

  $effect(() => {
    if (sessionId === openedRouteSessionId) return;
    openedRouteSessionId = sessionId;
    if (sessionId) void openSession(sessionId);
  });
</script>

<div class="head-row">
  <p class="page-lead">
    Every conversation with the runtime, with its turns and the governed events behind each turn.
  </p>
  <div class="head-actions">
    <label class="tag-filter">
      <span class="sr-only">Filter by tag</span>
      <input
        type="text"
        placeholder="Filter by tag…"
        bind:value={tagFilter}
        aria-label="Filter sessions by tag"
      />
    </label>
    <label class="archived-toggle">
      <input type="checkbox" bind:checked={showArchived} aria-label="Show archived sessions" />
      Show archived
    </label>
    <button type="button" class="btn btn-ghost btn-sm" onclick={load} aria-label="Refresh sessions">
      <Icon name="refresh" size="sm" />
      Refresh
    </button>
  </div>
</div>

{#if loadError}
  <PageState state="error" title="Couldn't load sessions" detail={loadError} />
{:else if sessions === null}
  <PageState state="loading" title="Loading sessions…" />
{:else if sessions.length === 0}
  <div class="card">
    <EmptyState icon="sessions" title="No sessions yet" body="Start a chat to create your first governed session." />
  </div>
{:else}
  {#if selected.size > 0}
    <div class="bulk-bar" role="toolbar" aria-label="Bulk actions">
      <span class="bulk-count">{selected.size} selected</span>
      <button
        type="button"
        class="btn btn-ghost btn-sm"
        onclick={() => (selected = new Set())}
        disabled={deleting}
      >
        Clear
      </button>
      <button
        type="button"
        class="btn btn-danger btn-sm"
        onclick={deleteSelected}
        disabled={deleting}
      >
        <Icon name="x" size="sm" />
        {deleting ? "Deleting…" : "Delete selected"}
      </button>
    </div>
  {/if}
  {#if actionError}<p class="error" role="alert">{actionError}</p>{/if}

  <div class="layout">
    <div class="card list-card">
      <table class="table">
        <thead>
          <tr>
            <th class="check-col"><input type="checkbox" checked={allVisibleSelected} onchange={toggleSelectAll} aria-label="Select all sessions" /></th>
            <th>Session</th>
            <th>Status</th>
            <th>Turns</th>
            <th>Tags</th>
            <th>Updated</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {#each ordered as s (s.session_id)}
            <tr
              class="row-btn"
              class:selected={detail?.session.session_id === s.session_id}
            >
              <td class="check-col" onclick={() => toggleSelected(s.session_id)}>
                <input
                  type="checkbox"
                  checked={selected.has(s.session_id)}
                  aria-label={`Select ${s.title ?? shortId(s.session_id)}`}
                />
              </td>
              <td onclick={() => openSession(s.session_id)}>
                <span class="session-title">
                  {#if s.pinned}<span class="pin-mark" title="Pinned" aria-label="Pinned">★</span>{/if}
                  {s.title ?? shortId(s.session_id)}
                </span>
                <span class="title-sub">
                  <span class="mono sub">{shortId(s.session_id)}</span>
                  <a
                    class="open-link"
                    href={`#/new-chat?session=${encodeURIComponent(s.session_id)}`}
                    aria-label={`Open ${s.title ?? shortId(s.session_id)} in chat`}
                    onclick={(e) => e.stopPropagation()}
                  >Open</a>
                </span>
              </td>
              <td onclick={() => openSession(s.session_id)}>
                <Badge variant={s.status === "active" ? "active" : "idle"} label={s.status} />
                {#if s.archived}<Badge variant="disabled" label="archived" />{/if}
              </td>
              <td onclick={() => openSession(s.session_id)}>{s.turn_count}</td>
              <td class="tags-col" onclick={(e) => e.stopPropagation()}>
                <span class="tag-chips">
                  {#each s.tags as t (t)}
                    <span class="tag-chip">
                      {t}
                      <button
                        type="button"
                        class="tag-x"
                        aria-label={`Remove tag ${t} from ${s.title ?? shortId(s.session_id)}`}
                        title="Remove tag"
                        onclick={() => void removeTag(s, t)}
                      >×</button>
                    </span>
                  {/each}
                </span>
                <span class="tag-add">
                  <input
                    type="text"
                    class="tag-input"
                    placeholder="Add tag…"
                    value={tagDraft[s.session_id] ?? ""}
                    oninput={(e) => (tagDraft = { ...tagDraft, [s.session_id]: e.currentTarget.value })}
                    onkeydown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        void addTag(s);
                      }
                    }}
                    aria-label={`Add a tag to ${s.title ?? shortId(s.session_id)}`}
                  />
                  <button
                    type="button"
                    class="tag-add-btn"
                    aria-label={`Add tag to ${s.title ?? shortId(s.session_id)}`}
                    title="Add tag"
                    onclick={() => void addTag(s)}
                  >+</button>
                </span>
              </td>
              <td onclick={() => openSession(s.session_id)} title={s.updated_at}>{relativeTime(s.updated_at)}</td>
              <td class="row-actions" onclick={(e) => e.stopPropagation()}>
                <SessionMenu
                  sessionId={s.session_id}
                  title={s.title ?? shortId(s.session_id)}
                  projects={projects.map((p) => ({ project_id: p.project_id, name: p.name }))}
                  pinned={s.pinned}
                  archived={s.archived}
                  onRename={(title) => void renameSession(s, title)}
                  onMove={(projectId) => void moveToProject(s, projectId)}
                  onPin={() => void togglePin(s)}
                  onArchive={() => void toggleArchived(s)}
                  onDelete={() => void deleteOne(s.session_id)}
                />
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <div class="detail-col">
      {#if detailError}
        <p class="error" role="alert">{detailError}</p>
      {:else if detail !== null}
        <section class="card" aria-labelledby="session-detail-h">
          <h2 id="session-detail-h">{detail.session.title ?? shortId(detail.session.session_id)}</h2>
          <p class="sub">Created {relativeTime(detail.session.created_at)} · {detail.turns.length} turns</p>
          <p class="session-links">
            <a href={`#/new-chat?session=${encodeURIComponent(detail.session.session_id)}`}>Open in chat</a>
            <!-- BUG-242 — Build restores a stored conversation on the same
                 coordinate Chat does, so the one surface where the approvals
                 for a change live is reachable from here too. -->
            <a href={`#/build?session=${encodeURIComponent(detail.session.session_id)}`}>Open in Build</a>
            <a href={`#/tasks?session=${encodeURIComponent(detail.session.session_id)}`}>View session tasks</a>
            <a href={`#/approvals?session=${encodeURIComponent(detail.session.session_id)}`}>View session approvals</a>
            <a href={`#/activity?session=${encodeURIComponent(detail.session.session_id)}`}>View audit events</a>
            <a href={`#/checkpoints?session=${encodeURIComponent(detail.session.session_id)}`}>View checkpoints</a>
          </p>
          <ol class="turns">
            {#each detail.turns as t (t.turn_id)}
              <li>
                <button type="button" class="turn-btn" onclick={() => openTurn(t.turn_id)}>
                  <span class="turn-prompt">{t.prompt_text ?? t.turn_type}</span>
                  <Badge variant={responseBadge(t.status)} label={t.status} />
                </button>
              </li>
            {/each}
          </ol>
        </section>
      {/if}

      {#if turnError}
        <p class="error" role="alert">{turnError}</p>
      {:else if turnDetail !== null}
        <section class="card" aria-labelledby="turn-detail-h">
          <div class="turn-head">
            <h3 id="turn-detail-h">Turn {shortId(turnDetail.turn.turn_id)}</h3>
            <!-- MEM-08 — the audit record of a turn and the exchange itself are
                 the same turn seen twice. This is the way back to it. -->
            <a
              class="btn btn-ghost btn-sm"
              href={conversationLink(
                turnDetail.turn.session_id === detail?.session.session_id &&
                  detail?.session.origin === "build"
                  ? "build"
                  : "new-chat",
                turnDetail.turn.session_id,
                turnDetail.turn.turn_id,
              )}
            >
              <Icon name="chat" size="sm" />
              Open in the conversation
            </a>
            <button type="button" class="btn btn-ghost btn-sm" onclick={() => (turnDetail = null)}>
              <Icon name="x" size="sm" />
              Close
            </button>
          </div>
          {#if turnDetail.turn.prompt_text}
            <p class="prompt-text">{turnDetail.turn.prompt_text}</p>
          {/if}
          {#if turnDetail.turn.summary}
            <p class="sub">{turnDetail.turn.summary}</p>
          {/if}
          <h4 class="kicker">Governed events</h4>
          {#if turnDetail.events.length === 0}
            <p class="sub">No indexed events for this turn.</p>
          {:else}
            <ul class="events">
              {#each turnDetail.events as ev (ev.event_id)}
                <li>
                  <span class="ev-type">{humanize(ev.event_type)}</span>
                  <span class="ev-summary">{ev.summary ?? ""}</span>
                  <span class="ev-time" title={ev.timestamp}>{relativeTime(ev.timestamp)}</span>
                </li>
              {/each}
            </ul>
          {/if}
        </section>
      {/if}
    </div>
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
  .head-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }
  .tag-filter input {
    font: inherit;
    font-size: var(--text-sm);
    padding: 0.3rem 0.55rem;
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: var(--bg);
    color: var(--text-1);
    min-width: 12rem;
  }
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }
  .bulk-bar {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: var(--space-3);
    padding: 0.5rem 0.7rem;
    border: 1px solid var(--warn-border);
    background: var(--warn-soft);
    border-radius: var(--r-sm);
    flex-wrap: wrap;
  }
  .bulk-count {
    font-weight: 650;
    font-size: var(--text-sm);
    margin-right: auto;
  }
  .layout {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    align-items: start;
  }
  .list-card {
    width: 100%;
    padding: var(--space-2) var(--space-3);
    overflow-x: auto;
    box-shadow: var(--shadow-0);
  }
  .table .check-col {
    width: 2rem;
  }
  .row-btn {
    cursor: pointer;
  }
  .row-btn.selected {
    background: var(--accent-soft);
  }
  .row-btn > td {
    cursor: pointer;
  }
  .row-actions,
  .check-col,
  .tags-col {
    cursor: default;
  }
  .archived-toggle {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: var(--text-sm);
    color: var(--text-2);
    cursor: pointer;
    white-space: nowrap;
  }
  .archived-toggle input {
    accent-color: var(--accent);
  }
  .title-sub {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
  }
  .open-link {
    font-size: var(--text-xs);
    font-weight: 600;
  }
  .tags-col {
    max-width: 22rem;
  }
  .tag-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.2rem;
    margin-bottom: 0.2rem;
  }
  .tag-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.2rem;
    background: var(--accent-soft);
    border: 1px solid var(--accent-border);
    color: var(--text-1);
    border-radius: 999px;
    padding: 0.05rem 0.45rem;
    font-size: var(--text-xs);
    line-height: 1.4;
  }
  .tag-x {
    border: none;
    background: none;
    color: var(--text-3);
    cursor: pointer;
    font-size: var(--text-md);
    line-height: 1;
    padding: 0 0.1rem;
    border-radius: 999px;
  }
  .tag-x:hover {
    color: var(--danger);
  }
  .tag-add {
    display: inline-flex;
    align-items: center;
    gap: 0.2rem;
  }
  .tag-input {
    font: inherit;
    font-size: var(--text-sm);
    padding: 0.15rem 0.4rem;
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: var(--bg);
    color: var(--text-1);
    width: 8rem;
  }
  /* A square control, so it is sized like one: 23x20 was under the 24px
     minimum target at every window width, not only on touch. */
  .tag-add-btn {
    display: inline-grid;
    place-items: center;
    min-width: 1.5rem;
    min-height: 1.5rem;
    border: 1px solid var(--border);
    background: var(--neutral-soft);
    color: var(--text-2);
    cursor: pointer;
    font-size: var(--text-md);
    line-height: 1;
    padding: 0.1rem 0.4rem;
    border-radius: var(--r-sm);
  }
  .tag-add-btn:hover {
    color: var(--text-1);
    border-color: var(--accent-border);
  }
  .session-title {
    display: block;
    font-weight: 600;
  }
  .pin-mark {
    color: var(--accent);
    margin-right: 0.2rem;
  }
  .row-actions {
    white-space: nowrap;
  }
  .sub {
    color: var(--text-3);
    font-size: var(--text-sm);
  }
  .detail-col {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }
  .detail-col :global(.card) {
    border-left: 3px solid var(--accent);
    box-shadow: var(--shadow-0);
  }
  .session-links {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem 0.8rem;
    font-size: var(--text-sm);
  }
  .turns {
    list-style: none;
    margin: var(--space-3) 0 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }
  .turn-btn {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.6rem;
    width: 100%;
    text-align: left;
    font: inherit;
    font-size: var(--text-sm);
    color: var(--text-1);
    background: var(--sunken);
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    padding: 0.45rem 0.65rem;
    cursor: pointer;
  }
  .turn-btn:hover {
    border-color: var(--accent-border);
  }
  .turn-prompt {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .turn-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .prompt-text {
    background: var(--accent-soft);
    border: 1px solid var(--accent-border);
    border-radius: var(--r-sm);
    padding: 0.5rem 0.7rem;
    font-size: var(--text-md);
  }
  .events {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    font-size: var(--text-sm);
  }
  .events li {
    display: flex;
    gap: 0.5rem;
    align-items: baseline;
    border-bottom: 1px dashed var(--border);
    padding-bottom: 0.3rem;
  }
  .ev-type {
    font-weight: 600;
    color: var(--text-1);
    white-space: nowrap;
  }
  .ev-summary {
    color: var(--text-2);
    flex: 1;
  }
  .ev-time {
    color: var(--text-3);
    font-size: var(--text-xs);
    white-space: nowrap;
  }
</style>
