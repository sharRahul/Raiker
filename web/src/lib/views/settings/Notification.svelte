<script lang="ts">
  /**
   * REM-SET-NOTIFY — two switches, said accurately, and the record they sit on.
   *
   * The page offered *In-app popups* and *Desktop alerts* under a heading that
   * read **Alerts**, and neither said what it reached. The first governed a
   * banner strip mounted on the MCP page and nowhere else, so an account-wide
   * preference decided whether a notice appeared on one destination the owner
   * may never open — that placement is fixed where it belongs, in the shell.
   * The second's own sentence claimed it covered "approvals waiting on you",
   * which understated it: it mirrors *every* unread notice, a finished routine
   * included.
   *
   * What is deliberately **not** here: per-channel switches. Raiker has no
   * outbox and no delivery preferences, and a row of toggles for email, push or
   * a messaging channel would be four controls that decide nothing — the defect
   * FIXED-523 removed fourteen of. Two working switches and an honest sentence
   * each is the whole contract.
   *
   * **Muting is not approving.** Neither switch touches a decision: an approval
   * that nobody is alerted about still waits, and Raiker still does not act.
   *
   * **DEC-21a — quiet hours** (owner decision, 2026-10-05). Opt-in; once on, no
   * notice interrupts during the interval — approvals, failed routines and
   * security notices included — and the bell, the record, the approval queue
   * and the page that raised something are unchanged. The only way through is
   * an exception the owner turns on, per channel, for security findings and
   * containment, and it starts off. The server decides each notice when it is
   * written, so everything below is a setting the server evaluates, not a timer
   * in this tab. Per-category *Interrupt me* switches and the test notice go
   * through the same decision.
   */
  import { api } from "../../api";
  import { announceNoticesChanged } from "../../noticeDestination";
  import { delivery, localClock, refreshDelivery, watchDelivery } from "../../deliveryPolicy.svelte";
  let { settings, save }: { settings: Record<string, unknown>; save: (p: Record<string, unknown>) => void } =
    $props();

  const inApp = $derived(settings["notification.in_app"] !== false);
  const desktop = $derived(Boolean(settings["notification.desktop"]));

  /**
   * What the browser will actually do, which the preference alone cannot say.
   *
   * A switch the owner has turned on while the browser has refused permission
   * is a switch that silently does nothing — so the page reads the permission
   * back rather than leaving them to discover it when a notice never arrives.
   */
  type PermissionState = "default" | "granted" | "denied" | "unsupported";
  let permission = $state<PermissionState>(
    typeof Notification === "undefined"
      ? "unsupported"
      : (Notification.permission as PermissionState),
  );

  function toggleDesktop(enabled: boolean) {
    // Desktop alerts need the browser permission; request it on enable so the
    // preference never silently does nothing.
    if (enabled && typeof Notification !== "undefined" && Notification.permission === "default") {
      void Notification.requestPermission().then(
        (granted) => (permission = granted as PermissionState),
      );
    }
    save({ "notification.desktop": enabled });
  }

  const QUIET = "notification.quiet_hours.";
  const quietOn = $derived(settings[`${QUIET}enabled`] === true);
  const quietStart = $derived(typeof settings[`${QUIET}start`] === "string" ? String(settings[`${QUIET}start`]) : "22:00");
  const quietEnd = $derived(typeof settings[`${QUIET}end`] === "string" ? String(settings[`${QUIET}end`]) : "07:00");
  const criticalInApp = $derived(settings[`${QUIET}critical_in_app`] === true);
  const criticalDesktop = $derived(settings[`${QUIET}critical_desktop`] === true);
  const sameTime = $derived(quietOn && quietStart === quietEnd);

  /** Interrupt switches the server offers, with what each covers. Decisions are not among them. */
  const CATEGORY_FALLBACK = [
    { category: "work", label: "Background work finished or paused" },
    { category: "security", label: "Security findings and containment" },
    { category: "extensions", label: "Extensions and MCP servers" },
  ];
  const categories = $derived(
    (delivery.current?.categories ?? CATEGORY_FALLBACK).map((item) => ({
      category: item.category,
      label: item.label,
      on: settings[`notification.interrupt.${item.category}`] !== false,
    })),
  );

  $effect(() => watchDelivery());

  /** What the server says about the clock right now — never computed in this tab. */
  const quietNow = $derived.by(() => {
    const state = delivery.current?.quiet_hours;
    if (!state || !state.enabled) return null;
    if (state.active) {
      const until = localClock(state.ends_at, state.timezone);
      return `Quiet now${until ? `, until ${until}` : ""} on the ${state.timezone} clock.`;
    }
    const next = localClock(state.next_starts_at, state.timezone);
    return `Not quiet now${next ? ` — the next quiet hours start at ${next}` : ""} on the ${state.timezone} clock.`;
  });
  const quietZone = $derived(delivery.current?.quiet_hours.timezone ?? null);

  let testState = $state<"idle" | "sending" | "error">("idle");
  let testResult = $state<string | null>(null);

  async function sendTest() {
    testState = "sending";
    testResult = null;
    try {
      const { notification } = await api.sendTestNotice();
      const zone = delivery.current?.quiet_hours.timezone ?? "UTC";
      const until = localClock(notification.quiet_until, zone);
      testResult =
        notification.in_app_presentation === "quiet_hours"
          ? `Sent and held: quiet hours are on${until ? ` until ${until}` : ""}. It is in the record now and will be in the summary when they end.`
          : notification.in_app_presentation === "muted"
            ? "Sent and recorded without interrupting."
            : "Sent. It is in the corner of the page and in the record.";
      testState = "idle";
      announceNoticesChanged();
      void refreshDelivery();
    } catch {
      testState = "error";
      testResult = "The test notice could not be sent. Nothing was changed.";
    }
  }

  /** The sentence beside the desktop switch when it cannot do what it says. */
  const desktopBlocked = $derived(
    !desktop
      ? null
      : permission === "unsupported"
        ? "This browser has no notification support, so nothing will be shown outside Raiker. The in-app notices and the record are unaffected."
        : permission === "denied"
          ? "This browser has blocked notifications for Raiker, so nothing will be shown outside the window. Allow them in the browser's site settings to turn this on for real."
          : permission === "default"
            ? "This browser has not been asked yet. It will ask the first time a notice would be shown."
            : null,
  );
</script>

<h2>Notifications</h2>

<section class="card">
  <h3>Where a notice reaches you</h3>
  <p class="sub">
    A notice is raised when something you were not watching happens — a
    background run finishing, a decision arriving, a security finding. Both
    switches below decide where you <em>see</em> it. Neither decides anything:
    an approval nobody is alerted about still waits for you.
  </p>

  <label class="toggle">
    <input
      type="checkbox"
      checked={inApp}
      onchange={(e) => save({ "notification.in_app": e.currentTarget.checked })}
    />
    Show unread notices inside Raiker
  </label>
  <p class="sub detail">
    The newest unread notice, docked in the corner of whatever page you are on.
    Opening it marks it read and takes you to what it is about. The bell in the
    top bar counts them whether this is on or off.
  </p>

  <label class="toggle">
    <input type="checkbox" checked={desktop} onchange={(e) => toggleDesktop(e.currentTarget.checked)} />
    Alert me outside Raiker
  </label>
  <p class="sub detail">
    The same unread notices as a desktop notification, shown only while Raiker is
    not the window you are looking at. It uses the browser's own notifications
    and never leaves this machine.
  </p>
  {#if desktopBlocked}
    <p class="blocked" role="status">{desktopBlocked}</p>
  {/if}
</section>

<section class="card" aria-labelledby="quiet-hours-heading">
  <h3 id="quiet-hours-heading">Quiet hours</h3>
  <p class="sub">
    During quiet hours nothing interrupts you — not approvals, not routines that stop, not
    security notices. Everything is still recorded, the bell still counts it, and work that
    needs a decision waits for one. When they end you get one summary of what is still
    unread, not every notice again.
  </p>
  <label class="toggle">
    <input
      type="checkbox"
      checked={quietOn}
      onchange={(e) => save({ [`${QUIET}enabled`]: e.currentTarget.checked })}
    />
    Use quiet hours
  </label>
  {#if quietOn}
    <div class="times">
      <label>
        <span>From</span>
        <input
          type="time"
          class="input"
          value={quietStart}
          aria-label="Quiet hours start"
          onchange={(e) => e.currentTarget.value && save({ [`${QUIET}start`]: e.currentTarget.value })}
        />
      </label>
      <label>
        <span>Until</span>
        <input
          type="time"
          class="input"
          value={quietEnd}
          aria-label="Quiet hours end"
          onchange={(e) => e.currentTarget.value && save({ [`${QUIET}end`]: e.currentTarget.value })}
        />
      </label>
    </div>
    <p class="sub detail">
      Read on {quietZone ? `the ${quietZone} clock` : "your time zone's clock"} — the one set in
      <a href="#/settings?tab=general">General</a> — so 22:00 is 22:00 on both sides of a clock change.
    </p>
    {#if sameTime}
      <p class="blocked" role="alert">Quiet hours cannot start and end at the same time.</p>
    {/if}
    {#if quietNow}<p class="state" data-testid="quiet-now">{quietNow}</p>{/if}

    <h4>Exceptions</h4>
    <p class="sub detail">
      Off unless you turn them on. Only security findings and containment — a capability or
      server Raiker has stopped — can come through, and only where you allow it. What a model
      writes in a notice can never make it urgent.
    </p>
    <label class="toggle">
      <input
        type="checkbox"
        checked={criticalInApp}
        onchange={(e) => save({ [`${QUIET}critical_in_app`]: e.currentTarget.checked })}
      />
      Let security alerts through inside Raiker
    </label>
    <label class="toggle">
      <input
        type="checkbox"
        checked={criticalDesktop}
        onchange={(e) => save({ [`${QUIET}critical_desktop`]: e.currentTarget.checked })}
      />
      Let security alerts through outside Raiker
    </label>
  {/if}
</section>

<section class="card" aria-labelledby="interrupt-heading">
  <h3 id="interrupt-heading">What interrupts you</h3>
  <p class="sub">
    Any time of day. A notice you turn off here is still recorded and counted by the bell; it
    just does not appear in the corner or on the desktop. Decisions always interrupt outside
    quiet hours, because work is waiting on them.
  </p>
  {#each categories as item (item.category)}
    <label class="toggle">
      <input
        type="checkbox"
        checked={item.on}
        onchange={(e) => save({ [`notification.interrupt.${item.category}`]: e.currentTarget.checked })}
      />
      {item.label}
    </label>
  {/each}
</section>

<section class="card" aria-labelledby="test-heading">
  <h3 id="test-heading">Try it</h3>
  <p class="sub">
    A test notice takes the same path a real one does — the same record, the same quiet hours,
    the same desktop alert — using what is saved, not what is on this page.
  </p>
  <button type="button" class="btn btn-sm" disabled={testState === "sending"} onclick={() => void sendTest()}>
    {testState === "sending" ? "Sending…" : "Send a test notice"}
  </button>
  {#if testResult}<p class="state" role="status" data-testid="test-notice-result">{testResult}</p>{/if}
</section>

<section class="card">
  <h3>The record</h3>
  <p class="sub">
    Every notice is recorded whether or not either switch showed it, so turning
    both off loses nothing.
    <a href="#/observe?tab=notifications">Open notifications</a>.
  </p>
</section>

<style>
  .toggle {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-top: var(--space-3);
  }
  .sub {
    color: var(--text-2);
  }
  .detail {
    font-size: var(--text-sm);
    margin: 0.25rem 0 0 1.6rem;
  }
  .times {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
    margin: var(--space-2) 0 0 1.6rem;
  }
  .times label { display: grid; gap: 0.2rem; font-size: var(--text-sm); color: var(--text-2); }
  .times input { width: 8rem; }
  h4 { margin: var(--space-4) 0 0; font-size: var(--text-sm); }
  .state {
    color: var(--text-1);
    font-size: var(--text-sm);
    margin: var(--space-2) 0 0 1.6rem;
  }
  #test-heading ~ .state { margin-left: 0; }
  .blocked {
    background: var(--warn-soft);
    border: 1px solid var(--warn-border);
    border-radius: var(--r-sm);
    color: var(--text-1);
    font-size: var(--text-sm);
    margin: var(--space-2) 0 0 1.6rem;
    padding: 0.4rem 0.6rem;
  }
</style>
