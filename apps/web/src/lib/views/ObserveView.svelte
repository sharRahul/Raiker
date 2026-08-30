<script lang="ts">
  /**
   * Observability hub — one read-first destination for readiness, the audit
   * log, live work, and notification history.
   *
   * The Overview tab answers four questions and nothing else: is Raiker ready,
   * is anything waiting for me, what changed, and can I safely proceed. Every
   * card links to the record that proves its claim, so no status is an opaque
   * coloured dot. The other tabs mount the existing views unchanged.
   */
  import { onMount } from "svelte";
  import ActivityView from "./ActivityView.svelte";
  import CheckpointsView from "./CheckpointsView.svelte";
  import DiagnosticsView from "./DiagnosticsView.svelte";
  import WorkInActionView from "./WorkInActionView.svelte";
  import SessionsView from "./SessionsView.svelte";
  import Icon from "../components/Icon.svelte";
  import PageState from "../components/PageState.svelte";
  import StatTile from "../components/StatTile.svelte";
  import TabStrip from "../components/TabStrip.svelte";
  import { api, ApiError } from "../api";
  import type {
    ApprovalView,
    Diagnostics,
    DiagnosticsExport,
    EventEntry,
    Notification as RaikerNotification,
    RuntimeReadiness,
    TaskView,
  } from "../apiTypes";
  import { humanize, isRedacted, relativeTime, shortId } from "../format";
  import { HUB_TABS } from "../nav";
  import { isActiveTask } from "../statusMaps";

  let {
    tab = "overview",
    sessionId = null,
    projectId = null,
  }: { tab?: string; sessionId?: string | null; projectId?: string | null } = $props();

  let diagnostics = $state<Diagnostics | null>(null);
  let readiness = $state<RuntimeReadiness | null>(null);
  let approvals = $state<ApprovalView[] | null>(null);
  let tasks = $state<TaskView[] | null>(null);
  let events = $state<EventEntry[] | null>(null);
  let notifications = $state<RaikerNotification[] | null>(null);
  let loadError = $state<string | null>(null);
  let offline = $state(false);

  // Support bundle. It is only ever what the server sends back — the browser
  // assembles nothing and claims nothing about the runtime on its own.
  let bundle = $state<DiagnosticsExport | null>(null);
  let bundleError = $state<string | null>(null);
  let bundleBusy = $state(false);
  let copyState = $state<"idle" | "copied" | "failed">("idle");

  const tabs = $derived(
    HUB_TABS.observe.map((id) => ({
      id,
      label: {
        overview: "Overview",
        sessions: "Sessions",
        activity: "Audit log",
        checkpoints: "Checkpoints",
        diagnostics: "Diagnostics",
        work: "Work in action",
        notifications: "Notifications",
      }[id] as string,
      badge:
        id === "notifications"
          ? (notifications ?? []).filter((n) => !n.read).length
          : null,
    })),
  );

  const activeTasks = $derived(
    (tasks ?? []).filter((task) => isActiveTask(task.status)),
  );
  const expiredApprovals = $derived((approvals ?? []).filter((a) => a.is_expired));
  // BUG-239 — a gate the enforcing path would run is not a closed gate. Counting
  // `!runtime_enabled` alone made this tile say "66 closed" on a workspace where
  // `web_fetch` would have fetched, which is the same defect Permissions had.
  const blockedGates = $derived(
    (readiness?.gates ?? []).filter(
      (gate) => !gate.runtime_enabled && gate.enforced_enabled !== true,
    ),
  );
  const ready = $derived(
    diagnostics?.production_ready_local_single_user_runtime === true,
  );

  function selectTab(next: string) {
    window.location.hash = `#/observe?tab=${encodeURIComponent(next)}`;
  }

  async function load() {
    loadError = null;
    try {
      [diagnostics, readiness, approvals, tasks, events, notifications] = await Promise.all([
        api.diagnostics(),
        api.runtimeReadiness(),
        api.approvals(),
        api.tasks(),
        api.events({ limit: 12 }),
        api.notifications(),
      ]);
      offline = false;
    } catch (error) {
      // A failed read never invents a green status: the overview says it could
      // not reach the runtime and offers a retry, rather than showing stale
      // readiness as if it were current.
      loadError =
        error instanceof ApiError ? `Unavailable (${error.status})` : "Could not reach the runtime";
      offline = !(error instanceof ApiError);
    }
  }

  async function loadBundle() {
    bundleBusy = true;
    bundleError = null;
    copyState = "idle";
    try {
      bundle = await api.diagnosticsExport();
    } catch (error) {
      bundle = null;
      bundleError =
        error instanceof ApiError
          ? `Could not build the support bundle (${error.status}).`
          : "Could not build the support bundle.";
    } finally {
      bundleBusy = false;
    }
  }

  async function copyBundle() {
    if (bundle === null) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(bundle, null, 2));
      copyState = "copied";
    } catch {
      // Clipboard access can be refused; the text stays on screen to select.
      copyState = "failed";
    }
  }

  onMount(load);
</script>

<TabStrip {tabs} selected={tab} onselect={selectTab} label="Observability sections" />

{#if tab === "overview"}
  <div id="panel-overview" role="tabpanel" aria-labelledby="tab-overview" class="overview">
    <div class="head">
      <p class="page-lead">
        A read-first record of what the runtime is doing. Every card below links to the evidence it
        is derived from — status here is never a colour without a record behind it.
      </p>
      <button type="button" class="btn btn-ghost btn-sm" onclick={load}>
        <Icon name="refresh" size={15} /> Refresh
      </button>
    </div>

    {#if loadError}
      <PageState
        state="error"
        title={offline ? "Raiker is not reachable" : "Couldn't read the runtime status"}
        detail={`${loadError}. Nothing was started or changed. Select Refresh once the runtime is back.`}
      />
    {:else if diagnostics === null}
      <PageState state="loading" title="Reading runtime status…" />
    {:else}
      <section aria-labelledby="ready-h">
        <h2 id="ready-h" class="section-h">Is Raiker ready?</h2>
        <div class="tiles">
          <StatTile
            label="Runtime"
            value={ready ? "Ready" : "Not ready"}
            detail={ready
              ? `Running in ${humanize(diagnostics.runtime_mode)} mode with its readiness checks met.`
              : `Running in ${humanize(diagnostics.runtime_mode)} mode with unmet readiness checks.`}
            tone={ready ? "ok" : "warn"}
            href="#/observe?tab=diagnostics"
            linkLabel="Open diagnostics"
          />
          <StatTile
            label="Closed capability gates"
            value={blockedGates.length}
            detail={blockedGates.length === 0
              ? "Every gate the runtime knows about is enabled."
              : "Requests needing these capabilities fail closed until you open them."}
            tone={blockedGates.length === 0 ? "ok" : "neutral"}
            href="#/capabilities"
            linkLabel="Review capabilities"
          />
          <StatTile
            label="Missing configuration"
            value={diagnostics.missing_config.length}
            detail={diagnostics.missing_config.length === 0
              ? "Nothing required is unset."
              : diagnostics.missing_config.join(", ")}
            tone={diagnostics.missing_config.length === 0 ? "ok" : "warn"}
            href="#/settings"
            linkLabel="Open settings"
          />
        </div>
      </section>

      <section aria-labelledby="waiting-h">
        <h2 id="waiting-h" class="section-h">Is anything waiting for me?</h2>
        <div class="tiles">
          <StatTile
            label="Pending approvals"
            value={(approvals ?? []).length}
            detail={(approvals ?? []).length === 0
              ? "No decision needs your review."
              : "Each one blocks a governed action until you decide."}
            tone={(approvals ?? []).length > 0 ? "accent" : "neutral"}
            href="#/approvals"
            linkLabel="Open the decision queue"
          />
          <StatTile
            label="Expired approvals"
            value={expiredApprovals.length}
            detail={expiredApprovals.length === 0
              ? "Nothing has aged out."
              : "These can no longer be approved; the action must be requested again."}
            tone={expiredApprovals.length > 0 ? "warn" : "neutral"}
            href="#/approvals"
            linkLabel="Review expiries"
          />
          <StatTile
            label="Open work"
            value={activeTasks.length}
            detail={activeTasks.length === 0
              ? "No task is queued, running, paused, or waiting for approval."
              : "You can stop any of these at a safe boundary."}
            href="#/observe?tab=work"
            linkLabel="Open the live board"
          />
          <StatTile
            label="Unread notifications"
            value={(notifications ?? []).filter((n) => !n.read).length}
            detail="The same record the bell in the context bar reads from."
            href="#/observe?tab=notifications"
            linkLabel="Open notification history"
          />
        </div>
      </section>

      <section aria-labelledby="changed-h">
        <h2 id="changed-h" class="section-h">What changed?</h2>
        {#if (events ?? []).length === 0}
          <p class="quiet">No events recorded yet.</p>
        {:else}
          <ol class="timeline">
            {#each events ?? [] as event (event.event_id)}
              <li>
                <span class="dot" data-risk={event.risk_level} aria-hidden="true"></span>
                <div class="entry">
                  <p class="entry-title">{humanize(event.event_type)}</p>
                  <p class="entry-detail">{event.summary}</p>
                  <p class="entry-meta">
                    <time title={event.timestamp}>{relativeTime(event.timestamp)}</time>
                    {#if event.session_id && !isRedacted(event.session_id)}
                      ·
                      <a href={`#/sessions?session=${encodeURIComponent(event.session_id)}`}>
                        session {shortId(event.session_id)}
                      </a>
                    {:else if event.session_id}
                      <!-- The server redacted this id, so it cannot address a
                           session. Say so rather than offering a dead link. -->
                      · <span title="The server redacted this identifier.">session withheld</span>
                    {/if}
                    {#if event.turn_id}· turn <span class="mono">{shortId(event.turn_id)}</span>{/if}
                  </p>
                </div>
              </li>
            {/each}
          </ol>
          <!-- Two links, deliberately in a row of their own: inline they ran
               together into one unreadable sentence at a phone width. -->
          <p class="more-row">
            <a class="more" href="#/observe?tab=activity">Open the full audit log</a>
            <a class="more" href="#/observe?tab=checkpoints">See the rewind timeline</a>
          </p>
        {/if}
      </section>

      <section aria-labelledby="support-h" class="support">
        <h2 id="support-h" class="section-h">Can I safely share this?</h2>
        <p>
          The support bundle is built by the server and redacted with the same rules every API
          response uses. It carries readiness facts and gate state — no credential, prompt, file
          content, or workspace path.
        </p>
        <div class="support-actions">
          <button type="button" class="btn btn-sm" onclick={loadBundle} disabled={bundleBusy}>
            {bundleBusy ? "Building…" : "Build support bundle"}
          </button>
          {#if bundle !== null}
            <button type="button" class="btn btn-sm" onclick={copyBundle}>Copy to clipboard</button>
            {#if copyState === "copied"}<span class="copy-note" role="status">Copied.</span>{/if}
            {#if copyState === "failed"}
              <span class="copy-note warn" role="status">
                The browser refused clipboard access — select the text below instead.
              </span>
            {/if}
          {/if}
        </div>
        {#if bundleError}<p class="error" role="alert">{bundleError}</p>{/if}
        {#if bundle !== null}
          <pre class="bundle" aria-label="Redacted support bundle">{JSON.stringify(bundle, null, 2)}</pre>
        {/if}
      </section>
    {/if}
  </div>
{:else if tab === "sessions"}
  <div id="panel-sessions" role="tabpanel" aria-labelledby="tab-sessions">
    <SessionsView {projectId} {sessionId} />
  </div>
{:else if tab === "activity"}
  <div id="panel-activity" role="tabpanel" aria-labelledby="tab-activity">
    <ActivityView {sessionId} />
  </div>
{:else if tab === "checkpoints"}
  <div id="panel-checkpoints" role="tabpanel" aria-labelledby="tab-checkpoints">
    <CheckpointsView {projectId} {sessionId} />
  </div>
{:else if tab === "diagnostics"}
  <div id="panel-diagnostics" role="tabpanel" aria-labelledby="tab-diagnostics">
    <DiagnosticsView />
  </div>
{:else if tab === "work"}
  <div id="panel-work" role="tabpanel" aria-labelledby="tab-work">
    <WorkInActionView />
  </div>
{:else}
  <div id="panel-notifications" role="tabpanel" aria-labelledby="tab-notifications">
    <h2 class="section-h">Notification history</h2>
    <p class="page-lead">
      Everything the context-bar bell has raised, newest first. Reading history changes nothing.
    </p>
    {#if notifications === null}
      <PageState state="loading" title="Loading notifications…" />
    {:else if notifications.length === 0}
      <p class="quiet">Nothing has been raised yet.</p>
    {:else}
      <ul class="notifications">
        {#each notifications as notification (notification.notification_id)}
          <li class:unread={!notification.read}>
            <p class="entry-title">{notification.title}</p>
            <p class="entry-detail">{notification.body}</p>
            <p class="entry-meta">
              <time title={notification.created_at}>{relativeTime(notification.created_at)}</time>
              · {notification.read ? "read" : "unread"}
            </p>
          </li>
        {/each}
      </ul>
    {/if}
  </div>
{/if}

<style>
  .overview { display: grid; gap: var(--space-5); }
  .head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-3);
  }
  .head .page-lead { margin: 0; }
  .section-h {
    font-size: 0.95rem;
    margin: 0 0 var(--space-3);
  }
  .tiles {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
    gap: var(--space-3);
  }
  .timeline { list-style: none; margin: 0; padding: 0; display: grid; gap: 0; }
  .timeline li {
    display: grid;
    grid-template-columns: 1rem 1fr;
    gap: var(--space-3);
    padding-bottom: var(--space-3);
    position: relative;
  }
  .timeline li:not(:last-child)::before {
    content: "";
    position: absolute;
    left: 0.44rem;
    top: 1rem;
    bottom: 0;
    width: 1px;
    background: var(--border);
  }
  .dot {
    width: 0.55rem;
    height: 0.55rem;
    margin-top: 0.4rem;
    border-radius: 50%;
    background: var(--neutral-border);
    box-shadow: 0 0 0 3px var(--bg);
  }
  .dot[data-risk="high"], .dot[data-risk="critical"] { background: var(--danger); }
  .dot[data-risk="medium"] { background: var(--warn); }
  .dot[data-risk="low"] { background: var(--ok); }
  .entry { display: grid; gap: 0.1rem; min-width: 0; }
  .entry-title { margin: 0; font-weight: 650; font-size: 0.88rem; }
  .entry-detail { margin: 0; color: var(--text-2); font-size: 0.84rem; overflow-wrap: anywhere; }
  .entry-meta { margin: 0; color: var(--text-3); font-size: 0.75rem; }
  .more { font-size: 0.82rem; font-weight: 600; }
  .more-row { display: flex; flex-wrap: wrap; gap: var(--space-1) var(--space-4); margin: var(--space-2) 0 0; }
  .quiet { color: var(--text-3); }
  .support p { color: var(--text-2); max-width: 68ch; }
  .support-actions { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
  .copy-note { color: var(--ok); font-size: 0.8rem; font-weight: 600; }
  .copy-note.warn { color: var(--warn); }
  .error { color: var(--danger); }
  .bundle {
    margin: var(--space-3) 0 0;
    padding: var(--space-3);
    max-height: 22rem;
    overflow: auto;
    background: var(--sunken);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    font-family: var(--font-mono);
    font-size: 0.74rem;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  .notifications { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-2); }
  .notifications li {
    border: 1px solid var(--border);
    border-left: 3px solid var(--border-strong);
    border-radius: var(--r-md);
    background: var(--surface);
    padding: var(--space-3) var(--space-4);
  }
  .notifications li.unread { border-left-color: var(--accent); }
  @media (max-width: 720px) { .head { flex-direction: column; } }
</style>
