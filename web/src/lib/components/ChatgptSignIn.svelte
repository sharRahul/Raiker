<script lang="ts">
  /**
   * Signing in to a ChatGPT subscription, start to finish, in one place.
   *
   * FIXED-1390/1392 — the old flow asked the *server* to open a browser and
   * then said "finish sign-in in the browser". On the desktop shell, a remote
   * browser or a headless host no browser appeared, the callback never came,
   * and the row waited forever; with Codex installed where a desktop app's
   * PATH does not reach, it said Codex was missing and stopped. This control
   * follows the pattern Hermes Agent and the Codex CLI use:
   *
   *   1. Codex missing → the one install command, copyable, and Check again.
   *   2. Browser sign-in → the ChatGPT page opens *here*, with a link in case
   *      the window was blocked.
   *   3. Device code → for a browser on another device, or when the local
   *      callback port is taken: the code, copyable, and the page to type it.
   *   4. Raiker checks every two seconds and adopts the account only once the
   *      owner's own sign-in finishes (BUG-259: a read never adopts).
   *
   * Tokens never pass through Raiker; Codex holds them.
   */
  import { onDestroy } from "svelte";
  import { api, ApiError } from "../api";
  import type { CodexLoginStarted } from "../generated/apiContract";
  import Icon from "./Icon.svelte";

  let {
    label = "Sign in with ChatGPT",
    compact = false,
    onconnected,
  }: {
    /** The primary button's words; "Switch account" while connected. */
    label?: string;
    compact?: boolean;
    /** Called once the owner's sign-in finished and the account is adopted. */
    onconnected?: (plan: string | null) => void;
  } = $props();

  const INSTALL_COMMAND = "npm install -g @openai/codex";
  const POLL_MS = 2000;
  // Ten minutes: ChatGPT's own device codes expire after fifteen.
  const POLL_LIMIT = 300;

  type Phase = "idle" | "starting" | "pending" | "missing" | "connecting";
  let phase = $state<Phase>("idle");
  let login = $state<CodexLoginStarted | null>(null);
  let failure = $state<string | null>(null);
  let copied = $state<string | null>(null);
  let polls = 0;
  let timer: ReturnType<typeof setTimeout> | null = null;

  function stopPolling() {
    if (timer !== null) clearTimeout(timer);
    timer = null;
  }
  onDestroy(stopPolling);

  function describe(error: unknown): string {
    if (error instanceof ApiError && error.reasonCode) {
      if (error.reasonCode === "codex_app_server_not_installed") return "missing";
      if (error.reasonCode === "codex_login_service_unreachable")
        return "Codex could not reach ChatGPT's sign-in service (auth.openai.com). Check this device's network, firewall or proxy, then try again.";
      return `ChatGPT sign-in could not start (${error.reasonCode}). Check that Codex runs on this device, then try again.`;
    }
    return "ChatGPT sign-in could not start. Check that Codex runs on this device, then try again.";
  }

  async function start(method: "browser" | "device_code" = "browser") {
    stopPolling();
    failure = null;
    phase = "starting";
    try {
      login = await api.startCodexSubscriptionLogin(method);
      phase = "pending";
      // A browser sign-in opens straight away. Where the window is blocked —
      // a browser that only allows popups from a click — the link below is
      // the same page.
      if (login.method === "browser" && login.url) {
        window.open(login.url, "_blank", "noopener,noreferrer");
      }
      polls = 0;
      timer = setTimeout(() => void poll(), POLL_MS);
    } catch (error) {
      const reason = describe(error);
      if (reason === "missing") {
        phase = "missing";
      } else {
        phase = "idle";
        failure = reason;
      }
    }
  }

  async function poll() {
    timer = null;
    polls += 1;
    try {
      const status = await api.codexSubscriptionStatus();
      if (status.connection_status === "available" || status.connection_status === "connected") {
        await adopt();
        return;
      }
      if (status.connection_status === "codex_missing") {
        phase = "missing";
        return;
      }
      if (status.login_error) {
        phase = "idle";
        login = null;
        failure = `ChatGPT sign-in did not finish (${status.login_error}). Try again, or use a code instead.`;
        return;
      }
    } catch {
      // A missed read is not a failed sign-in; the next one may answer.
    }
    if (polls >= POLL_LIMIT) {
      phase = "idle";
      login = null;
      failure = "The sign-in took too long and was stopped. Start it again when you are ready.";
      return;
    }
    timer = setTimeout(() => void poll(), POLL_MS);
  }

  async function adopt() {
    phase = "connecting";
    try {
      const connected = await api.connectCodexSubscription();
      phase = "idle";
      login = null;
      onconnected?.(connected.plan_type);
    } catch {
      phase = "idle";
      failure = "Signed in, but that subscription could not be connected. Try Use existing sign-in.";
    }
  }

  async function cancel() {
    stopPolling();
    phase = "idle";
    login = null;
    try {
      await api.cancelCodexSubscriptionLogin();
    } catch {
      // The sign-in ends with its process anyway; nothing to recover here.
    }
  }

  async function copy(text: string, what: string) {
    try {
      await navigator.clipboard.writeText(text);
      copied = what;
      setTimeout(() => (copied = null), 1500);
    } catch {
      copied = null;
    }
  }
</script>

<div class="chatgpt-sign-in" class:compact data-expanded={phase !== "idle" || failure !== null}>
  {#if phase === "missing"}
    <div class="panel" role="status">
      <p class="lead"><Icon name="warning" size="sm" /> Codex is not installed on this device.</p>
      <p class="detail">
        Raiker signs in to ChatGPT through OpenAI's Codex client, so your token stays with Codex. Install it
        once, then check again.
      </p>
      <div class="command">
        <code>{INSTALL_COMMAND}</code>
        <button type="button" class="btn btn-ghost btn-sm" onclick={() => void copy(INSTALL_COMMAND, "command")}
          >{copied === "command" ? "Copied" : "Copy"}</button
        >
      </div>
      <p class="detail">
        Installed somewhere Raiker does not look? Set <code>RAIKER_CODEX_PATH</code> to the <code>codex</code> launcher
        and restart Raiker.
      </p>
      <div class="actions">
        <button type="button" class="btn btn-primary btn-sm" onclick={() => void start()}>Check again</button>
        <a class="btn btn-ghost btn-sm" href="https://developers.openai.com/codex" target="_blank" rel="noopener noreferrer"
          >About Codex</a
        >
      </div>
    </div>
  {:else if (phase === "pending" || phase === "connecting") && login}
    <div class="panel" role="status" aria-live="polite">
      {#if login.method === "device_code" && login.user_code}
        <p class="lead">Enter this code on the ChatGPT sign-in page</p>
        <div class="code-row">
          <span class="code" aria-label="One-time code">{login.user_code}</span>
          <button type="button" class="btn btn-ghost btn-sm" onclick={() => void copy(login?.user_code ?? "", "code")}
            >{copied === "code" ? "Copied" : "Copy code"}</button
          >
        </div>
        {#if login.url}
          <a class="btn btn-primary btn-sm" href={login.url} target="_blank" rel="noopener noreferrer"
            >Open the sign-in page</a
          >
        {/if}
        <p class="detail">The code works once and expires in about fifteen minutes.</p>
      {:else}
        <p class="lead">Finish signing in to ChatGPT in the page that opened.</p>
        <div class="actions">
          {#if login.url}
            <a class="btn btn-primary btn-sm" href={login.url} target="_blank" rel="noopener noreferrer"
              >Open sign-in again</a
            >
          {/if}
          <button type="button" class="btn btn-ghost btn-sm" onclick={() => void start("device_code")}
            >Use a code instead</button
          >
        </div>
        <p class="detail">
          Signing in on another device, or no page appeared? Use a code instead.
        </p>
      {/if}
      <div class="footer">
        <span class="waiting"
          ><span class="dot" aria-hidden="true"></span>{phase === "connecting"
            ? "Connecting…"
            : "Waiting for ChatGPT…"}</span
        >
        <button type="button" class="btn btn-ghost btn-sm" onclick={() => void cancel()}>Cancel</button>
      </div>
    </div>
  {:else}
    <div class="actions">
      <button
        type="button"
        class="btn btn-primary btn-sm"
        disabled={phase === "starting"}
        onclick={() => void start("browser")}>{phase === "starting" ? "Opening sign-in…" : label}</button
      >
      <button
        type="button"
        class="btn btn-ghost btn-sm"
        disabled={phase === "starting"}
        onclick={() => void start("device_code")}>Sign in with a code</button
      >
    </div>
  {/if}
  {#if failure}<p class="failed" role="alert">{failure}</p>{/if}
</div>

<style>
  .chatgpt-sign-in {
    display: grid;
    gap: var(--space-2);
    min-width: 0;
  }
  .panel {
    display: grid;
    gap: var(--space-2);
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--sunken);
  }
  .lead {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    margin: 0;
    color: var(--text-1);
    font-size: var(--text-sm);
    font-weight: 600;
  }
  .detail {
    margin: 0;
    color: var(--text-2);
    font-size: var(--text-xs);
  }
  .command,
  .code-row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
  .command code {
    flex: 1 1 auto;
    padding: 0.4rem 0.6rem;
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: var(--surface);
    font-size: var(--text-xs);
    overflow-wrap: anywhere;
  }
  .code {
    padding: 0.35rem 0.75rem;
    border: 1px solid var(--accent-border);
    border-radius: var(--r-sm);
    background: var(--surface);
    color: var(--text-1);
    font-family: var(--font-mono);
    font-size: var(--text-lg);
    font-weight: 650;
    letter-spacing: 0.08em;
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
  }
  .footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
    padding-top: var(--space-2);
    border-top: 1px solid var(--border);
  }
  .waiting {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    color: var(--text-2);
    font-size: var(--text-xs);
  }
  .dot {
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 50%;
    background: var(--accent);
    animation: pulse 1.4s ease-in-out infinite;
  }
  @keyframes pulse {
    50% {
      opacity: 0.3;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .dot {
      animation: none;
    }
  }
  .failed {
    margin: 0;
    color: var(--danger);
    font-size: var(--text-xs);
  }
</style>
