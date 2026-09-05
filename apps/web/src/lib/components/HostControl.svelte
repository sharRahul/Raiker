<script lang="ts">
  // BUG-40 — the menu-bar control, in the app.
  //
  // `docs/architecture/DESKTOP_DISTRIBUTION_DESIGN.md` asks for a tray/menu-bar control that
  // shows running / paused / needs attention / stopped and offers Open, Pause,
  // Restart and Quit, with quitting reporting waiting work before it stops.
  // This is that control, mounted in the top bar rather than in the OS tray: a
  // native tray needs a packaged binary per platform, and the *behaviour* — an
  // honest state, in-flight work named, and a quit that tells you what it would
  // interrupt — is what the owner actually needs and does not have to wait for
  // a signed installer to get. "Open Raiker" is the one tray action with no
  // meaning here: you are already looking at it.
  //
  // BUG-44 adds the other half of "understand whether it is running": what
  // *this* Raiker is. A signed release from a channel, an unsigned test build,
  // or a source checkout — read from the record the build wrote inside the
  // artifact, so the panel cannot claim provenance the installation does not
  // have. Applying an update is deliberately not offered here: replacing the
  // tree this process runs from, from this process, is the wrong place for it.
  import Icon from "./Icon.svelte";
  import { api, ApiError } from "../api";
  import type { HostStatusView, UpdateStatusView } from "../apiTypes";

  let host = $state<HostStatusView | null>(null);
  let build = $state<UpdateStatusView | null>(null);
  let checking = $state(false);
  let open = $state(false);
  let busy = $state(false);
  let notice = $state<string | null>(null);
  // Set when an action reported work in flight. The second press is a different
  // decision from the first, made with the interruption in front of you.
  let confirming = $state<"quit" | "restart" | null>(null);
  let trigger = $state<HTMLButtonElement>();

  const TONES: Record<string, string> = {
    running: "ok",
    paused: "warn",
    "needs attention": "warn",
    stopped: "danger",
  };
  const tone = $derived(TONES[host?.state ?? ""] ?? "neutral");

  async function load() {
    try {
      host = await api.host();
    } catch {
      // A host that cannot answer is a host that is not running as far as this
      // control is concerned — but the page is still up, so say the honest
      // thing rather than blanking the control.
      host = null;
    }
    try {
      // A local read: provenance, the pinned channel, and retained recovery
      // points. It makes no outbound request, which is why it can run on open.
      build = await api.hostUpdate();
    } catch {
      build = null;
    }
  }

  // What the build line says, and how loudly. "Unsigned" is a warning because a
  // build nobody signed is a build nobody can vouch for; a source checkout is
  // neutral because that is simply what development looks like.
  const BUILD_TONES: Record<string, string> = {
    source_checkout: "neutral",
    no_channel: "neutral",
    unsigned_build: "warn",
    up_to_date: "ok",
    available: "warn",
    unreachable: "warn",
  };
  const buildTone = $derived(BUILD_TONES[build?.state ?? ""] ?? "neutral");
  const buildLabel = $derived(
    build === null
      ? "unknown"
      : build.installation.packaged
        ? build.installation.signed
          ? "signed release"
          : "unsigned build"
        : "source checkout",
  );

  async function checkForUpdates() {
    checking = true;
    notice = null;
    try {
      build = await api.checkHostUpdate();
      notice = build.message;
    } catch {
      notice = "The update check could not be carried out.";
    } finally {
      checking = false;
    }
  }

  function toggle() {
    if (open) {
      close();
      return;
    }
    open = true;
    notice = null;
    confirming = null;
    void load();
  }

  function close() {
    open = false;
    trigger?.focus();
  }

  async function act(action: "pause" | "resume" | "quit" | "restart", confirm = false) {
    busy = true;
    notice = null;
    try {
      const result =
        action === "pause"
          ? await api.pauseHost()
          : action === "resume"
            ? await api.resumeHost()
            : action === "quit"
              ? await api.quitHost(confirm)
              : await api.restartHost(confirm);
      host = result;
      if (!result.ok && result.reason_code === "waiting_work") {
        confirming = action === "quit" ? "quit" : "restart";
        return;
      }
      confirming = null;
      notice =
        action === "pause"
          ? "Paused. Scheduled work will not start until you resume."
          : action === "resume"
            ? "Resumed. Scheduled work starts again from the next tick."
            : action === "quit"
              ? "Stopping at the next safe boundary. This tab will lose its connection."
              : "Restarting. This tab will reconnect once the host is back.";
    } catch (error) {
      notice =
        error instanceof ApiError && error.reasonCode === "not_registered"
          ? "Raiker is not registered to start in the background, so nothing would start it again. Register it first, or quit and start it yourself."
          : "That action could not be carried out.";
    } finally {
      busy = false;
    }
  }

  $effect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });
</script>

<div class="host-wrap">
  <button
    type="button"
    class="btn btn-ghost host-btn"
    aria-label={host ? `Host: ${host.state}` : "Host status"}
    aria-expanded={open}
    onclick={toggle}
    bind:this={trigger}
  >
    <span class={`dot tone-${tone}`} aria-hidden="true"></span>
    <span class="host-state">{host?.state ?? "Host"}</span>
  </button>

  {#if open}
    <button type="button" class="panel-backdrop" aria-label="Close host control" tabindex="-1" onclick={close}></button>
    <section class="panel" aria-label="Host control">
      <div class="panel-head">
        <strong>Raiker host</strong>
        <span class={`state-pill tone-${tone}`}>{host?.state ?? "unknown"}</span>
      </div>
      <p class="detail">{host?.detail ?? "The host is not answering. It may be starting or already stopped."}</p>

      {#if host}
        <dl class="property-list">
          {#if host.pid !== null}<dt>Process</dt><dd class="mono">{host.pid}{host.port !== null ? ` · port ${host.port}` : ""}</dd>{/if}
          <dt>Starts on its own</dt>
          <dd>
            {host.service.registered
              ? `Yes — ${host.service.mechanism}`
              : host.service.supported
                ? `No — run “raiker-app service install” to register it with ${host.service.mechanism}`
                : host.service.note}
          </dd>
        </dl>
      {/if}

      <div class="work" aria-label="Background work">
        <h4>Background work</h4>
        {#if !host || host.waiting.length === 0}
          <p class="quiet">Nothing is in flight. Quitting interrupts no work.</p>
        {:else}
          <ul>
            {#each host.waiting as item (item.kind)}
              <li><strong>{item.label}</strong><span>{item.detail}</span></li>
            {/each}
          </ul>
        {/if}
      </div>

      <!-- BUG-44 — what this installation is. Never a claim the record does
           not support: no record means "source checkout", stated plainly. -->
      <div class="build" aria-label="Install and updates">
        <h4>Install &amp; updates</h4>
        {#if build === null}
          <p class="quiet">This build could not be identified.</p>
        {:else}
          <dl class="property-list">
            <dt>This build</dt>
            <dd>
              <span class={`state-pill tone-${buildTone}`}>{buildLabel}</span>
              <span class="mono build-version">
                {build.installation.version}{build.installation.target ? ` · ${build.installation.target}` : ""}
              </span>
            </dd>
            <dt>Update channel</dt>
            <dd>
              {build.channel
                ? `${build.channel.channel} · ${build.channel.url}`
                : "Not configured — Raiker contacts no update service."}
            </dd>
            {#if build.recovery_points.length > 0}
              <dt>Roll back to</dt>
              <dd>{build.recovery_points.map((point) => point.version).join(", ")}</dd>
            {/if}
          </dl>
          <p class="quiet build-message">{build.message}</p>
          {#if build.available}
            <!-- Settings now applies a verified update through the external
                 helper, so this panel points at that rather than at a command
                 line the owner would otherwise have to leave the app to run. -->
            <p class="confirm" role="status">
              Version {build.available.version} is available.
              <a href="#/settings?tab=updates">Install it in Settings</a>.
            </p>
          {/if}
          <button
            type="button"
            class="btn btn-ghost btn-sm check-updates"
            disabled={checking}
            onclick={() => checkForUpdates()}
          >
            <Icon name="refresh" size="sm" /> {checking ? "Checking…" : "Check for updates"}
          </button>
        {/if}
      </div>

      {#if confirming}
        <p class="confirm" role="alert">
          {confirming === "quit" ? "Quitting" : "Restarting"} now would interrupt the work above.
          Press {confirming === "quit" ? "Quit" : "Restart"} again to go ahead.
        </p>
      {/if}
      {#if notice}<p class="notice" role="status">{notice}</p>{/if}

      <div class="actions">
        {#if host?.paused}
          <button type="button" class="btn btn-soft btn-sm" disabled={busy} onclick={() => act("resume")}>
            <Icon name="play" size="sm" /> Resume
          </button>
        {:else}
          <button type="button" class="btn btn-sm" disabled={busy} onclick={() => act("pause")}>
            <Icon name="hand" size="sm" /> Pause
          </button>
        {/if}
        <button
          type="button"
          class="btn btn-sm"
          disabled={busy || !host?.restartable}
          title={host?.restartable ? undefined : "Raiker is not registered to start in the background, so nothing would start it again."}
          onclick={() => act("restart", confirming === "restart")}
        >
          <Icon name="refresh" size="sm" /> Restart
        </button>
        <button type="button" class="btn btn-danger btn-sm" disabled={busy} onclick={() => act("quit", confirming === "quit")}>
          <Icon name="stop" size="sm" /> Quit
        </button>
      </div>
      <p class="foot">Pause stops new scheduled work. A run you have already approved still finishes.</p>
    </section>
  {/if}
</div>

<style>
  .host-wrap { position: relative; }
  .host-btn { padding: 0.35rem 0.55rem; gap: 0.35rem; font-size: var(--text-xs); }
  .host-state { text-transform: capitalize; }
  .dot { width: 0.5rem; height: 0.5rem; border-radius: var(--r-pill); background: var(--text-3); }
  .dot.tone-ok { background: var(--ok); }
  .dot.tone-warn { background: var(--warn); }
  .dot.tone-danger { background: var(--danger); }
  .panel-backdrop { position: fixed; inset: 0; z-index: 55; border: 0; background: transparent; cursor: default; }
  .panel {
    position: absolute; right: 0; top: calc(100% + 6px); z-index: 60;
    width: min(23rem, 88vw);
    border: 1px solid var(--border); border-radius: var(--r-md);
    background: var(--raised); box-shadow: var(--shadow-2);
    padding: var(--space-3); display: grid; gap: var(--space-3);
  }
  .panel-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
  .state-pill {
    font-size: var(--text-2xs); font-weight: 700; text-transform: capitalize;
    padding: 0.1rem 0.5rem; border-radius: var(--r-pill);
    background: var(--neutral-soft); border: 1px solid var(--neutral-border); color: var(--text-2);
  }
  .state-pill.tone-ok { background: var(--ok-soft); border-color: var(--ok-border); color: var(--ok); }
  .state-pill.tone-warn { background: var(--warn-soft); border-color: var(--warn-border); color: var(--warn); }
  .state-pill.tone-danger { background: var(--danger-soft); border-color: var(--danger-border); color: var(--danger); }
  .detail, .quiet, .foot { margin: 0; color: var(--text-2); font-size: var(--text-sm); }
  .foot { color: var(--text-3); font-size: var(--text-xs); }
  .work h4, .build h4 { margin: 0 0 0.35rem; font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.07em; color: var(--text-3); }
  .build { display: grid; gap: 0.4rem; border-top: 1px solid var(--border); padding-top: var(--space-3); }
  .build dd { display: flex; flex-wrap: wrap; align-items: center; gap: 0.35rem; }
  .build-version { font-size: var(--text-xs); color: var(--text-2); }
  .build-message { font-size: var(--text-xs); }
  .build a { color: inherit; }
  .check-updates { justify-self: start; }
  .work ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.4rem; }
  .work li { display: grid; gap: 0.1rem; font-size: var(--text-sm); }
  .work li span { color: var(--text-2); font-size: var(--text-xs); }
  .confirm {
    margin: 0; font-size: var(--text-sm); padding: 0.45rem 0.6rem; border-radius: var(--r-sm);
    background: var(--warn-soft); border: 1px solid var(--warn-border); color: var(--text-1);
  }
  .notice { margin: 0; font-size: var(--text-sm); color: var(--text-2); }
  .actions { display: flex; flex-wrap: wrap; gap: 0.4rem; }
  @media (max-width: 720px) {
    .host-state { display: none; }
    .panel { position: fixed; left: var(--space-3); right: var(--space-3); top: calc(var(--topbar-h) + 6px); width: auto; }
  }
</style>
