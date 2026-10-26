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
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import PageState from "../components/PageState.svelte";
  import TabStrip from "../components/TabStrip.svelte";
  import TelemetryExport from "../components/TelemetryExport.svelte";
  import { api, ApiError } from "../api";
  import { digestEvents } from "../auditDigest";
  import { allClearSentence, attentionItems, RUNTIME_HEALTH_CHANGED, type AttentionTone } from "../observeAttention";
  import type { IconName } from "../icons";
  import { presentationPhrase, repeatPhrase } from "../noticePresentation";
  import { delivery, localClock } from "../deliveryPolicy.svelte";
  import { isDeferred, isInherent } from "../capabilityModel";
  import type {
    ApprovalView,
    Diagnostics,
    DiagnosticsExport,
    EventEntry,
    Notification as RaikerNotification,
    RuntimeReadiness,
    SecurityHealth,
    TaskView,
  } from "../apiTypes";
  import { humanize, isAddressableSession, isRedacted, relativeTime, shortId } from "../format";
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
  // REM-OBSERVE — containment is the one signal on this page that must never
  // sit below a telemetry delivery error, so the overview reads it itself
  // rather than waiting for the specialist view below to be opened.
  let security = $state<SecurityHealth[] | null>(null);
  let loadError = $state<string | null>(null);
  let offline = $state(false);
  /** When the reads behind this page last came back: the cards' "last checked". */
  let checkedAt = $state<string | null>(null);

  // QUI-L11 — what kind of problem a card is, in words as well as an icon,
  // because status never relies on colour alone.
  const TONE_LABEL: Record<AttentionTone, string> = {
    containment: "Security",
    blocking: "Stops work",
    waiting: "Waiting on you",
    unknown: "Not known",
  };
  const TONE_ICON: Record<AttentionTone, IconName> = {
    containment: "shield",
    blocking: "warning",
    waiting: "hand",
    unknown: "help",
  };

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
        // QUI-L11 — the record of points to go back to is Recovery.
        checkpoints: "Recovery",
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
  // BUG-239 — a gate the enforcing path would run is not a closed gate. Counting
  // `!runtime_enabled` alone made this tile say "66 closed" on a workspace where
  // `web_fetch` would have fetched, which is the same defect Permissions had.
  const closedGates = $derived(
    (readiness?.gates ?? []).filter(
      (gate) => !gate.runtime_enabled && gate.enforced_enabled !== true,
    ),
  );
  // …and a gate the owner cannot open is not something to send them to
  // Permissions about. This tile said "65 closed" under a link to a page that
  // lists 48, because Permissions deliberately omits capabilities with no
  // executor and the contract surfaces that are not tools. The number is now
  // the number of rows on the page the link opens; the rest are named as what
  // they are rather than being counted as work.
  const openableGates = $derived(
    closedGates.filter((gate) => !isDeferred(gate) && !isInherent(gate)),
  );
  const gatesWithNoExecutor = $derived(closedGates.length - openableGates.length);
  const ready = $derived(
    diagnostics?.production_ready_local_single_user_runtime === true,
  );
  /** "What changed?" answers with changes — see `auditDigest.ts`. */
  const changes = $derived(digestEvents(events ?? []));

  // REM-OBSERVE — the exceptions, and what an empty list of them may claim.
  // `null` for `unreadNotifications` while the read is in flight or failed, so
  // an unread count that could not be read is not counted as zero.
  const attentionInputs = $derived({
    diagnostics,
    approvals,
    security,
    unreadNotifications:
      notifications === null ? null : notifications.filter((n) => !n.read).length,
  });
  const attention = $derived(attentionItems(attentionInputs));

  /** The resting state of a working install, folded under "What is working". */
  const healthyRows = $derived.by(() => {
    if (diagnostics === null) return [];
    const unread = (notifications ?? []).filter((n) => !n.read).length;
    const live = (approvals ?? []).filter((a) => !a.is_expired).length;
    return [
      {
        label: "Raiker",
        value: `${ready ? "Ready" : "Not ready"} · ${humanize(diagnostics.runtime_mode)} mode`,
        href: null,
        linkLabel: "",
      },
      {
        label: "Permissions",
        value:
          openableGates.length === 0
            ? "Every capability you can turn on is on"
            : `${openableGates.length} turned off${gatesWithNoExecutor > 0 ? ` · ${gatesWithNoExecutor} with no executor` : ""}`,
        href: "#/capabilities",
        linkLabel: "Permissions",
      },
      {
        label: "Required settings",
        value: diagnostics.missing_config.length === 0 ? "All set" : `${diagnostics.missing_config.length} unset`,
        href: null,
        linkLabel: "",
      },
      { label: "Decisions", value: live === 0 ? "None waiting" : `${live} waiting`, href: "#/approvals", linkLabel: "Approvals" },
      {
        label: "Background work",
        value: activeTasks.length === 0 ? "Nothing running" : `${activeTasks.length} running or waiting`,
        href: "#/observe?tab=work",
        linkLabel: "Live board",
      },
      { label: "Notifications", value: unread === 0 ? "All read" : `${unread} unread`, href: "#/observe?tab=notifications", linkLabel: "History" },
    ];
  });

  // BUG-322 — a link to a damaged index's repair (the attention item, the
  // notice) opens the detail it lives in and brings the repair into view,
  // instead of leaving the owner to find it behind a closed fold.
  let address = $state(typeof window !== "undefined" ? window.location.hash : "");
  $effect(() => {
    const follow = () => (address = window.location.hash);
    window.addEventListener("hashchange", follow);
    return () => window.removeEventListener("hashchange", follow);
  });
  const repairOpen = $derived(address.includes("repair=indexes"));
  // A repair made in the detail below changes what the attention list above
  // reports; re-read rather than keep saying the index is damaged.
  $effect(() => {
    const reread = () => void load();
    window.addEventListener(RUNTIME_HEALTH_CHANGED, reread);
    return () => window.removeEventListener(RUNTIME_HEALTH_CHANGED, reread);
  });
  $effect(() => {
    if (!repairOpen || diagnostics === null) return;
    const timer = setTimeout(() => {
      document.getElementById("diag-memory-h")?.scrollIntoView({ block: "start" });
    }, 200);
    return () => clearTimeout(timer);
  });

  // A command-line flag or an environment variable in a card's sentence is
  // something to type: it must not break at its own hyphens across lines.
  const TERM = /(--[a-z][a-z-]*|\bRAIKER_[A-Z_]+\b)/;

  function detailParts(text: string): { text: string; term: boolean }[] {
    // split() with a capturing group puts each matched term at an odd index.
    return text
      .split(TERM)
      .map((part, index) => ({ text: part, term: index % 2 === 1 }))
      .filter((part) => part.text !== "");
  }

  function selectTab(next: string) {
    window.location.hash = `#/observe?tab=${encodeURIComponent(next)}`;
  }

  async function load() {
    loadError = null;
    try {
      [diagnostics, readiness, approvals, tasks, events, notifications] = await Promise.all([
        api.diagnostics(),
        api.runtimeReadiness(),
        // Waiting and lapsed together: this page counts the two separately.
        Promise.all([api.approvals(), api.lapsedApprovals()]).then(([live, lapsed]) => [...live, ...lapsed]),
        api.tasks(),
        // Over-fetched because the digest filters: a page of routine
        // authorization lookups must not be able to empty it.
        api.events({ limit: 60 }),
        api.notifications(),
      ]);
      offline = false;
      checkedAt = new Date().toISOString();
      // Read separately and allowed to fail on its own: a build without the
      // security-health route must not take the whole overview down, and a
      // failure here becomes an explicit *unknown* in the attention list
      // rather than a silent all-clear.
      try {
        security = await api.securityHealth();
      } catch {
        security = null;
      }
    } catch (error) {
      // A failed read never invents a green status: the overview says it could
      // not reach the runtime and offers a retry, rather than showing stale
      // readiness as if it were current.
      loadError =
        error instanceof ApiError ? `Unavailable (${error.status})` : "Could not reach Raiker";
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
      // DEC-24 step 4 — the server checks its own redaction and refuses a
      // bundle that still holds anything secret-shaped. Said as a refusal for
      // the owner's protection, not as a fault, so nobody retries around it.
      bundleError =
        error instanceof ApiError && error.reasonCode === "support_export_blocked"
          ? "Raiker did not build the support bundle: after redaction, something in it still " +
            "looked like a secret, so nothing was produced to copy. Check Settings → Security for " +
            "a credential stored where a name or label belongs."
          : error instanceof ApiError
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

<TabStrip {tabs} selected={tab} onselect={selectTab} label="Diagnostics sections" />

{#if tab === "overview"}
  <div id="panel-overview" role="tabpanel" aria-labelledby="tab-overview" class="overview">
    {#if loadError}
      <PageState
        state="error"
        title={offline ? "Raiker is not reachable" : "Couldn't read Raiker's status"}
        detail={`${loadError}. Nothing was started or changed. Select Refresh once Raiker is back.`}
      />
    {:else if diagnostics === null}
      <PageState state="loading" title="Reading status…" />
    {:else}
      <!-- QUI-L11 — Diagnostics: what needs attention, one card per issue
           (the problem, what it affects, when it was checked, the safe fix, and
           the runtime's own words under Technical details). Healthy systems,
           recent changes and sharing are folded below it, so a healthy install
           is one line and a sick one leads with the problem. -->
      <section aria-labelledby="attention-h" class="attention">
        <div class="attention-head">
          <h2 id="attention-h" class="section-h">What needs attention</h2>
          <span class="checked">
            {#if checkedAt}Checked <time datetime={checkedAt}>{relativeTime(checkedAt)}</time>{/if}
          </span>
          <button type="button" class="btn btn-ghost btn-sm" onclick={load}>
            <Icon name="refresh" size="sm" /> Check again
          </button>
        </div>
        {#if attention.length === 0}
          <!-- NEW-HOME-01's rule, stated in the sentence itself: an all-clear
               names what it covers, so a read that failed cannot hide inside
               the word "nothing". -->
          <p class="quiet" role="status">{allClearSentence(attentionInputs)}</p>
        {:else}
          <ul class="issues">
            {#each attention as item (item.id)}
              <li class="issue" data-tone={item.tone}>
                <div class="issue-main">
                  <h3 class="issue-title">{item.title}</h3>
                  <p class="issue-detail">
                    {#each detailParts(item.detail) as part, index (index)}{#if part.term}<span class="term">{part.text}</span>{:else}{part.text}{/if}{/each}
                  </p>
                  <p class="issue-meta">
                    <Icon name={TONE_ICON[item.tone]} size="sm" />
                    <span>{TONE_LABEL[item.tone]}</span>
                    {#if checkedAt}<span aria-hidden="true">·</span><span>last checked {relativeTime(checkedAt)}</span>{/if}
                  </p>
                  {#if item.technical}
                    <details class="technical">
                      <summary>Technical details</summary>
                      <code>{item.technical}</code>
                    </details>
                  {/if}
                </div>
                <a class="btn btn-sm issue-fix" href={item.href}>{item.linkLabel}</a>
              </li>
            {/each}
          </ul>
        {/if}
      </section>

      <details class="fold" aria-labelledby="healthy-h">
        <summary>
          <span id="healthy-h" class="fold-title">What is working</span>
          <span class="fold-meta">{healthyRows.length} check{healthyRows.length === 1 ? "" : "s"}</span>
          <Icon name="chevron-down" size="sm" />
        </summary>
        <dl class="healthy-rows">
          {#each healthyRows as row (row.label)}
            <div>
              <dt>{row.label}</dt>
              <dd>{row.value}{#if row.href}<a href={row.href}>{row.linkLabel}</a>{/if}</dd>
            </div>
          {/each}
        </dl>
      </details>

      <details class="fold">
        <summary>
          <span class="fold-title">What changed</span>
          <span class="fold-meta">{changes.length === 0 ? "Nothing yet" : `${changes.length} recent`}</span>
          <Icon name="chevron-down" size="sm" />
        </summary>
        {#if changes.length === 0}
          <p class="quiet">Nothing has changed yet.</p>
        {:else}
          <ol class="timeline">
            {#each changes as event (event.event_id)}
              <li>
                <span class="dot" data-risk={event.risk_level} aria-hidden="true"></span>
                <div class="entry">
                  <p class="entry-title">{humanize(event.event_type)}</p>
                  <!-- Not every governed event carries a summary; an empty
                       line under the title is a row that looks broken. -->
                  {#if event.summary}<p class="entry-detail">{event.summary}</p>{/if}
                  <p class="entry-meta">
                    <time title={event.timestamp}>{relativeTime(event.timestamp)}</time>
                    {#if isAddressableSession(event.session_id)}
                      ·
                      <a href={`#/sessions?session=${encodeURIComponent(event.session_id!)}`}>
                        session {shortId(event.session_id)}
                      </a>
                    {:else if isRedacted(event.session_id)}
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
            <a class="more" href="#/observe?tab=checkpoints">Open Recovery</a>
          </p>
        {/if}
      </details>

      <details class="fold support">
        <summary>
          <span class="fold-title">Share or export</span>
          <span class="fold-meta">Support bundle and telemetry</span>
          <Icon name="chevron-down" size="sm" />
        </summary>
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
        <!-- Backlog #18 — the record Raiker keeps can leave the machine on a
             wire, to a collector the owner adds. -->
        <TelemetryExport />
      </details>

      <!--
        Diagnostics was a seventh tab on this hub reading the *same* `diagnostics`
        object this page already reads. Four of its six cards restated the three
        tiles at the top: the readiness tick list said "Runtime: Ready", the
        configuration-gaps card rendered the identical `missing_config`, the
        capability chips expanded the closed-gates count, and the provider table
        was a thinner copy of Models. What only it had is here — the runtime's
        own health transitions, the memory integrity report and its repair, and
        any readiness check that actually failed.
      -->
      <!-- REM-OBSERVE — "preserve diagnostics as specialist views". The whole
           of Diagnostics rendered inline on every visit, below two rows of
           tiles, on a page whose first job is to say what is wrong. It is one
           disclosure now: the failed readiness checks, the runtime's health
           transitions and the memory integrity report are all still here, and
           a healthy install does not have to scroll past them. What its
           failures mean for the owner is already in the attention list above,
           read from the same records. -->
      <details class="fold specialist" open={repairOpen} id="runtime-health-detail">
        <summary>
          <span class="fold-title">Health, in detail</span>
          <span class="fold-meta">Readiness checks, memory integrity, restarts</span>
          <Icon name="chevron-down" size="sm" />
        </summary>
        <div class="specialist-body">
          <DiagnosticsView />
        </div>
      </details>

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
{:else if tab === "work"}
  <div id="panel-work" role="tabpanel" aria-labelledby="tab-work">
    <WorkInActionView />
  </div>
{:else}
  <div id="panel-notifications" role="tabpanel" aria-labelledby="tab-notifications">
    <h2 class="section-h">Notification history</h2>
    {#if notifications === null}
      <PageState state="loading" title="Loading notifications…" />
    {:else if notifications.length === 0}
      <!-- BUG-280 — the one tab in this hub that answered an empty list with a
           bare grey line. Its five siblings, and every other list surface in the
           product, use the shared empty state; this read as an unfinished page
           rather than as a quiet one. Same component, same icon vocabulary. -->
      <EmptyState
        icon="bell"
        title="Nothing has been raised"
        body="Approvals, background work and containment write here when they need you."
      />
    {:else}
      <ul class="notifications">
        {#each notifications as notification (notification.notification_id)}
          <li class:unread={!notification.read}>
            <p class="entry-title">{notification.title}</p>
            <p class="entry-detail">{notification.body}</p>
            <p class="entry-meta">
              <time title={notification.created_at}>{relativeTime(notification.created_at)}</time>
              · {notification.read ? "read" : "unread"}
              {#if presentationPhrase(notification, (instant) => localClock(instant, delivery.current?.quiet_hours.timezone ?? "UTC"))}
                · <span data-testid="notice-presentation">{presentationPhrase(notification, (instant) => localClock(instant, delivery.current?.quiet_hours.timezone ?? "UTC"))}</span>
              {/if}
              {#if repeatPhrase(notification)}
                · <span data-testid="notice-repeats">{repeatPhrase(notification)}</span>
              {/if}
              <!-- C10 — a notice about background work is only useful if it
                   leads to the work. The card there carries the run's thread. -->
              {#if notification.kind === "task_finished"}
                · <a href="#/tasks">Open Tasks</a>
              {/if}
            </p>
          </li>
        {/each}
      </ul>
    {/if}
  </div>
{/if}

<style>
  .overview { display: grid; gap: var(--space-3); max-width: 52rem; }
  .section-h {
    font-size: var(--text-md);
    margin: 0 0 var(--space-3);
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
  .entry-title { margin: 0; font-weight: 650; font-size: var(--text-md); }
  .entry-detail { margin: 0; color: var(--text-2); font-size: var(--text-sm); overflow-wrap: anywhere; }
  .entry-meta { margin: 0; color: var(--text-3); font-size: var(--text-xs); }
  .more { font-size: var(--text-sm); font-weight: 600; }
  .more-row { display: flex; flex-wrap: wrap; gap: var(--space-1) var(--space-4); margin: var(--space-2) 0 0; }
  .quiet { color: var(--text-3); }

  /* QUI-L11 — one flat card per issue. The kind of problem is a word and an
     icon in the meta line, never a coloured stripe: status never relies on
     colour alone, and a side stripe was decoration doing a label's job. */
  .attention { margin-bottom: var(--space-3); }
  .attention-head { display: flex; align-items: baseline; gap: var(--space-3); margin-bottom: var(--space-3); }
  .attention-head .section-h { margin: 0; font-size: var(--text-lg); }
  .checked { color: var(--text-3); font-size: var(--text-sm); margin-right: auto; }
  .issues { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-2); }
  .issue {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-4);
    padding: var(--space-4);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--surface);
  }
  .issue[data-tone="containment"] { border-color: var(--danger-border); }
  .issue[data-tone="blocking"] { border-color: var(--warn-border); }
  .issue-main { display: grid; gap: var(--space-1); min-width: 0; }
  .issue-title { margin: 0; font-size: var(--text-base); font-weight: 650; }
  .issue-detail { margin: 0; color: var(--text-2); font-size: var(--text-sm); max-width: 62ch; }
  .issue-detail .term { white-space: nowrap; }
  .issue-meta { display: flex; align-items: center; gap: 0.35rem; margin: var(--space-1) 0 0; color: var(--text-3); font-size: var(--text-xs); }
  .issue[data-tone="containment"] .issue-meta { color: var(--danger); }
  .issue[data-tone="blocking"] .issue-meta { color: var(--warn); }
  .issue-fix { flex: none; }
  .technical summary { cursor: pointer; color: var(--text-3); font-size: var(--text-xs); width: fit-content; }
  .technical code { display: block; margin-top: var(--space-1); font-family: var(--font-mono); font-size: var(--text-xs); color: var(--text-2); overflow-wrap: anywhere; }
  .fold { border-top: 1px solid var(--border); padding: var(--space-3) 0 0; }
  .fold > summary {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    cursor: pointer;
    list-style: none;
    min-height: var(--control-normal);
  }
  .fold > summary::-webkit-details-marker { display: none; }
  .fold > summary :global(svg) { transition: transform var(--motion-fast) var(--ease); }
  .fold[open] > summary :global(svg) { transform: rotate(180deg); }
  .fold-title { font-weight: 650; }
  .fold-meta { color: var(--text-3); font-size: var(--text-sm); margin-right: auto; }
  .fold[open] > :not(summary) { margin-top: var(--space-3); }
  .healthy-rows { margin: 0; display: grid; gap: 0; }
  .healthy-rows div { display: grid; grid-template-columns: 12rem 1fr; gap: var(--space-3); padding: var(--space-2) 0; }
  .healthy-rows dt { color: var(--text-2); font-size: var(--text-sm); }
  .healthy-rows dd { margin: 0; font-size: var(--text-sm); display: flex; gap: var(--space-3); flex-wrap: wrap; }
  .healthy-rows a { font-weight: 600; }
  .support p { color: var(--text-2); max-width: 68ch; }
  .support-actions { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
  .copy-note { color: var(--ok); font-size: var(--text-sm); font-weight: 600; }
  .copy-note.warn { color: var(--warn); }
  .bundle {
    margin: var(--space-3) 0 0;
    padding: var(--space-3);
    max-height: 22rem;
    overflow: auto;
    background: var(--sunken);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  .notifications { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-2); }
  .notifications li {
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--surface);
    padding: var(--space-3) var(--space-4);
  }
  .notifications li.unread { border-color: var(--accent-border); background: var(--accent-soft); }
</style>
