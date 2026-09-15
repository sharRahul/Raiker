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
   */
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
    Up to three unread notices as a banner at the top of whatever page you are
    on, with a link to the rest.
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
