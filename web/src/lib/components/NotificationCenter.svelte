<script lang="ts">
  /**
   * Unread notices, wherever the owner is — and the one place the notification
   * preferences actually reach.
   *
   * **REM-SET-NOTIFY.** Settings offered two switches, *In-app popups* and
   * *Desktop alerts*, described as though they governed how Raiker reaches you.
   * The second did. The first governed this strip, and this strip was mounted
   * on the MCP page and nowhere else — so a setting presented as an account-wide
   * alert preference decided whether a banner appeared on one destination the
   * owner may never open. That is not a control whose scope can be labelled
   * accurately; it is a control in the wrong place.
   *
   * It reads its own notifications rather than taking them as a prop, for the
   * same reason `ApprovalPrompt` does: the shell is where it belongs, the shell
   * has no reason to know about notifications, and a component that is the only
   * thing using a read should own it.
   *
   * **The in-app record is still the truth.** This is a courtesy on top of
   * Observability → Notifications, which holds every notice whether or not
   * either alert showed it. Nothing here is the only copy of anything, so a
   * failed read changes nothing on screen and the next tick tries again.
   */
  import type { Notification as RaikerNotification } from "../apiTypes";
  import { api, hasToken } from "../api";
  import { canRaiseDesktopNotice, raiseDesktopNotice } from "../desktopNotice";
  import { uiPrefs } from "../prefs.svelte";
  import {
    NOTICES_CHANGED,
    NOTICE_RECORD,
    announceNoticesChanged,
    answeredByPage,
    noticeDestination,
    shownByApprovalCard,
    onNoticeRecord,
  } from "../noticeDestination";

  /** How often unread notices are re-read. The record is not urgent; a notice
   *  about work that finished is still true a minute later. */
  const POLL_MS = 30000;

  let notifications = $state<RaikerNotification[]>([]);
  const unread = $derived(notifications.filter((notification) => !notification.read));

  // The address, as state, for the same reason `ApprovalPrompt` keeps it:
  // `window.location.hash` is not reactive, and a notice must leave the moment
  // the owner arrives at the page that answers it, however they got there.
  let hash = $state(typeof window !== "undefined" ? window.location.hash : "");
  $effect(() => {
    const follow = () => (hash = window.location.hash);
    window.addEventListener("hashchange", follow);
    return () => window.removeEventListener("hashchange", follow);
  });

  /**
   * BUG-309 — what the dock may show on this page. A notice whose subject is
   * the page on screen (an approval notice on Approvals, a finished run on
   * Tasks) repeats a row of it, and on the record every notice is a row.
   */
  const shown = $derived(
    onNoticeRecord(hash)
      ? []
      : unread.filter((item) => !answeredByPage(item, hash) && !shownByApprovalCard(item)),
  );

  /**
   * A notice the page has answered is read: the owner is looking at its
   * subject. Marked through the same route opening one uses, so the bell's
   * count agrees with the dock rather than counting what the page just showed.
   * The record keeps it either way.
   */
  let marking = new Set<string>();
  $effect(() => {
    const answered = unread.filter(
      (item) => answeredByPage(item, hash) && !marking.has(item.notification_id),
    );
    if (answered.length === 0) return;
    for (const item of answered) marking.add(item.notification_id);
    void Promise.allSettled(
      answered.map((item) => api.markNotificationRead(item.notification_id)),
    ).then(() => announceNoticesChanged());
  });

  async function poll() {
    if (!hasToken()) return;
    try {
      notifications = await api.notifications();
    } catch {
      // A failed read leaves the strip as it was. The complete record is on
      // Observability → Notifications either way.
    }
  }

  $effect(() => {
    void poll();
    const timer = setInterval(() => void poll(), POLL_MS);
    // The bell's *Mark all read* changes what this should show; re-read now
    // rather than keep a notice docked for up to thirty seconds after.
    const reread = () => void poll();
    window.addEventListener(NOTICES_CHANGED, reread);
    return () => {
      clearInterval(timer);
      window.removeEventListener(NOTICES_CHANGED, reread);
    };
  });

  /**
   * Reading it is what clears it.
   *
   * A docked notice that nothing dismisses is a permanent obstruction, which is
   * a worse defect than the one this strip was moved to fix. Opening it marks
   * the notice read through the same route the bell's **Mark all read** uses,
   * so the strip, the bell's count and the record never disagree — and the
   * owner lands on the record rather than on a banner they have to ignore.
   */
  async function open(notification: RaikerNotification) {
    window.location.hash = noticeDestination(notification.kind);
    try {
      await api.markNotificationRead(notification.notification_id);
    } catch {
      // The navigation already happened and the record is still the record.
      // A failed mark leaves the notice unread, which is the truth.
    }
    announceNoticesChanged();
  }

  /**
   * Read it here, without going anywhere.
   *
   * Opening was the only way to clear the dock, so a notice the owner had
   * already understood sat over the top of whatever page they were on — on
   * Chat, over the conversation's own **New chat** — until they left that page
   * to read it. Dismissing marks it read through the same route; the record
   * keeps it.
   */
  async function dismiss(notification: RaikerNotification) {
    notifications = notifications.map((item) =>
      item.notification_id === notification.notification_id ? { ...item, read: true } : item,
    );
    try {
      await api.markNotificationRead(notification.notification_id);
    } catch {
      // The next poll shows it again if the mark did not land, which is the truth.
    }
    announceNoticesChanged();
  }

  /**
   * How far the dock drops so it never covers a page's own top actions.
   *
   * Found live on 2026-10-01: docked under the top bar, the notice sat over the
   * conversation header's **New chat** on Chat and Build and over **Refresh**
   * on the list pages, and a click meant for either opened the notice instead.
   * The approval card learned the same thing about composers at the bottom
   * (FIXED-621); this is the top half. A page's top action row is measured and
   * the dock sits just below any row it would cover, and back under the top bar
   * when there is none.
   */
  const KEEP_CLEAR_TOP = ".head-row, .header-actions, [data-dock-clear-top]";
  const DOCK_RIGHT = 20;
  let drop = $state(0);
  let dock = $state<HTMLElement | null>(null);

  function measure() {
    if (typeof document === "undefined" || dock === null) return;
    const width = dock.offsetWidth || 384;
    const left = window.innerWidth - DOCK_RIGHT - width;
    // Where the dock sits with no drop. `offsetTop` ignores the transform the
    // drop is applied as, so measuring never feeds back into itself.
    const baseTop = dock.offsetTop;
    // Its own height, or a typical card's before it has been laid out.
    const baseBottom = baseTop + (dock.offsetHeight || 96);
    let needed = 0;
    for (const row of document.querySelectorAll<HTMLElement>(KEEP_CLEAR_TOP)) {
      if (dock.contains(row)) continue;
      const rect = row.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0 || rect.right <= left) continue;
      if (rect.bottom <= baseTop || rect.top >= baseBottom) continue;
      needed = Math.max(needed, rect.bottom + 8 - baseTop);
    }
    drop = Math.max(0, Math.round(needed));
  }

  $effect(() => {
    if (shown.length === 0 || dock === null) return;
    measure();
    const tick = setInterval(measure, 1000);
    window.addEventListener("resize", measure);
    return () => {
      clearInterval(tick);
      window.removeEventListener("resize", measure);
    };
  });

  // Mirror new unread notifications to the desktop through the one path every
  // surface uses (BUG-255). Best-effort only — the in-app record is the source
  // of truth.
  let mirrored = new Set<string>();
  $effect(() => {
    if (!canRaiseDesktopNotice()) return;
    for (const item of unread) {
      if (mirrored.has(item.notification_id)) continue;
      mirrored.add(item.notification_id);
      raiseDesktopNotice({
        title: item.title,
        body: item.body,
        tag: item.notification_id,
        // C10 — clicking a notice about background work should land on the
        // work. Only for the kinds that have somewhere to land.
        route: noticeDestination(item.kind),
      });
    }
  });
</script>

{#if uiPrefs.inApp && shown.length > 0}
  {@const newest = shown[0]}
  <section
    class="notifications"
    aria-label="Notifications"
    bind:this={dock}
    style:transform={drop > 0 ? `translateY(${drop}px)` : undefined}
  >
    <!-- One, not a stack. Three docked cards covered Home's primary actions at
         1080p and most of the screen at 390px, which is a worse obstruction
         than the banner nobody could see. The rest are never lost: the bell
         counts them and the link below opens the record. -->
    <div class="notice-row">
      <button type="button" class="notice" onclick={() => void open(newest)}>
        <strong>{newest.title}</strong><span>{newest.body}</span>
      </button>
      <button
        type="button"
        class="dismiss"
        aria-label={`Dismiss: ${newest.title}`}
        title="Mark read"
        onclick={() => void dismiss(newest)}>×</button
      >
    </div>
    {#if shown.length > 1}
      <!-- Inside the card, on its surface: drawn beside it, the link read as
           part of whatever page was underneath (BUG-309 found it across a
           table's Status header). -->
      <a class="all" href={NOTICE_RECORD}>{shown.length} unread notices</a>
    {/if}
  </section>
{/if}

<style>
  /**
   * Docked rather than in the flow, and the reason is measurable.
   *
   * The first placement put this inside `main#main`, above the routed page. The
   * responsive sweep caught it immediately: Chat, Build and Design size
   * themselves to `--content-h` — the room between the topbar and the bottom of
   * the viewport — so anything added above them pushes their composer below the
   * fold. At 390×844 Build's composer ended 385px past the bottom edge.
   *
   * A notice is not page content; the record is, and it is one link away. So
   * this docks like `ApprovalPrompt` does — fixed, bounded, and taking no part
   * in any page's height — at the opposite corner, so the two never collide.
   */
  .notifications {
    position: fixed;
    top: calc(var(--topbar-h) + 12px);
    right: 20px;
    z-index: var(--z-docked);
    width: min(24rem, calc(100vw - 40px));
    display: grid;
    border: 1px solid var(--warn-border, var(--neutral-border));
    border-radius: var(--r-md);
    background: var(--surface);
    box-shadow: var(--shadow-2);
    overflow: hidden;
  }
  .notifications:hover { border-color: var(--accent-border, var(--neutral-border)); }
  .notice {
    display: grid;
    gap: 0.15rem;
    width: 100%;
    text-align: left;
    cursor: pointer;
    padding: 0.72rem 0.8rem;
    border: 0;
    background: transparent;
  }
  .notice-row { display: flex; align-items: flex-start; }
  .notice-row .notice { flex: 1; min-width: 0; }
  .dismiss {
    flex: none;
    border: 0;
    background: transparent;
    color: var(--text-3);
    font-size: var(--text-lg);
    line-height: 1;
    cursor: pointer;
    padding: 0.6rem 0.7rem;
  }
  .dismiss:hover { color: var(--text-1); }
  .notice strong { color: var(--text-1); font-size: var(--text-sm); }
  .notice span { color: var(--text-2); font-size: var(--text-sm); overflow-wrap: anywhere; }
  .all {
    color: var(--text-2);
    font-size: var(--text-sm);
    padding: 0.45rem 0.8rem;
    border-top: 1px solid var(--neutral-border);
  }
  .all:hover { color: var(--text-1); }
</style>
